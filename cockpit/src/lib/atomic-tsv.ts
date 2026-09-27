import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';

interface LockHandle {
  lockFile: string;
  cleanup: () => Promise<void>;
}

/**
 * Checks if the system flock binary is available.
 */
function hasSystemFlock(): boolean {
  try {
    return fs.existsSync('/usr/bin/flock');
  } catch {
    return false;
  }
}

/**
 * Acquires an advisory lock on the target file.
 * Uses Linux kernel flock(2) when available for 100% interoperability with fleet scripts,
 * falling back to atomic POSIX O_CREAT|O_EXCL lockfiles.
 */
async function acquireAdvisoryLock(
  lockFile: string,
  timeoutMs: number = 5000
): Promise<LockHandle> {
  const timeoutSec = Math.max(1, Math.ceil(timeoutMs / 1000));
  const startTime = Date.now();

  if (hasSystemFlock()) {
    // Mode 1: Linux kernel flock via child process
    return new Promise<LockHandle>((resolve, reject) => {
      const child = spawn('/usr/bin/flock', [
        '-x',
        '-w',
        String(timeoutSec),
        lockFile,
        'sh',
        '-c',
        'echo READY && read line'
      ], { stdio: ['pipe', 'pipe', 'pipe'] });

      let isResolved = false;
      let errorOutput = '';

      child.stderr?.on('data', (d) => {
        errorOutput += d.toString();
      });

      child.stdout?.on('data', (d) => {
        if (d.toString().includes('READY') && !isResolved) {
          isResolved = true;
          resolve({
            lockFile,
            cleanup: async () => {
              try {
                if (child.stdin && !child.stdin.destroyed) {
                  child.stdin.write('\n');
                  child.stdin.end();
                }
              } catch {}
              if (child.exitCode !== null) {
                return;
              }
              // Send SIGTERM immediately to release kernel file lock instantly without 500ms delay
              try { child.kill('SIGTERM'); } catch {}
              await new Promise<void>((r) => {
                if (child.exitCode !== null) {
                  r();
                  return;
                }
                child.once('exit', () => r());
                setTimeout(() => {
                  try { child.kill('SIGKILL'); } catch {}
                  r();
                }, 100);
              });
            }
          });
        }
      });

      child.on('error', (err) => {
        if (!isResolved) {
          isResolved = true;
          reject(new Error(`Failed to spawn flock: ${err.message}`));
        }
      });

      child.on('exit', (code) => {
        if (!isResolved) {
          isResolved = true;
          reject(new Error(`flock timed out or exited with code ${code}: ${errorOutput}`));
        }
      });
    });
  }

  // Mode 2: Pure Node.js atomic O_CREAT | O_EXCL fallback
  while (true) {
    try {
      fs.writeFileSync(lockFile, `${process.pid}\n${Date.now()}\n`, { flag: 'wx' });
      return {
        lockFile,
        cleanup: async () => {
          try {
            if (fs.existsSync(lockFile)) {
              fs.unlinkSync(lockFile);
            }
          } catch {}
        }
      };
    } catch (err: any) {
      if (err.code === 'EEXIST') {
        if (Date.now() - startTime > timeoutMs) {
          // Check for stale lockfile (>10 seconds old)
          try {
            const stat = fs.statSync(lockFile);
            if (Date.now() - stat.mtimeMs > 10000) {
              fs.unlinkSync(lockFile);
              continue;
            }
          } catch {}
          throw new Error(`Timeout acquiring advisory lock on ${lockFile} after ${timeoutMs}ms`);
        }
        // Jittered backoff between 15ms and 35ms
        const delay = 15 + Math.floor(Math.random() * 20);
        await new Promise((r) => setTimeout(r, delay));
      } else {
        throw err;
      }
    }
  }
}

/**
 * Atomically mutates a TSV file using advisory locking, same-filesystem temporary file,
 * physical disk flush (fsync), and POSIX rename(2).
 *
 * Guarantees zero torn reads for active awk/dispatcher readers.
 */
export async function mutateTsvAtomically(
  targetFilePath: string,
  mutateFn: (currentLines: string[]) => string[],
  lockTimeoutMs: number = 5000
): Promise<void> {
  const dir = path.dirname(targetFilePath);
  const base = path.basename(targetFilePath);
  const lockFile = path.join(dir, `.${base}.lock`);

  // Ensure directory exists
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  // 1. Acquire advisory lock
  const lockHandle = await acquireAdvisoryLock(lockFile, lockTimeoutMs);
  let tempFile: string | null = null;

  try {
    // 2. Read latest lines under lock
    const content = fs.existsSync(targetFilePath) ? fs.readFileSync(targetFilePath, 'utf8') : '';
    const currentLines = content.split('\n');

    // 3. Apply caller mutation function
    const newLines = mutateFn(currentLines);
    
    // Ensure proper trailing newline if content is non-empty
    let newContent = newLines.join('\n');
    if (newLines.length > 0 && !newContent.endsWith('\n')) {
      newContent += '\n';
    }

    // 4. Write to unique temporary file on SAME filesystem
    tempFile = path.join(
      dir,
      `.${base}.tmp.${process.pid}.${Date.now()}.${crypto.randomBytes(4).toString('hex')}`
    );
    fs.writeFileSync(tempFile, newContent, 'utf8');
    const fd = fs.openSync(tempFile, 'r+');
    fs.fsyncSync(fd);
    fs.closeSync(fd);

    // 6. Atomic directory entry swap via rename(2)
    fs.renameSync(tempFile, targetFilePath);
    tempFile = null; // Successfully swapped
  } finally {
    // 7. Cleanup temp file if rename failed
    if (tempFile && fs.existsSync(tempFile)) {
      try {
        fs.unlinkSync(tempFile);
      } catch {}
    }
    // 8. Release advisory lock
    await lockHandle.cleanup();
  }
}

// ==========================================
// Helper Utilities for DISPATCH-LEDGER.tsv
// ==========================================

export interface DispatchLedgerRow {
  raw: string;
  timestamp: string;
  seat: string;
  row: string;
  status: string;
  brief: string;
  isCommentOrEmpty: boolean;
}

/**
 * Parses raw TSV lines into structured dispatch ledger row objects.
 */
export function parseDispatchLedgerLines(lines: string[]): DispatchLedgerRow[] {
  return lines.map((line) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      return {
        raw: line,
        timestamp: '',
        seat: '',
        row: '',
        status: '',
        brief: '',
        isCommentOrEmpty: true
      };
    }
    const cols = line.split('\t');
    return {
      raw: line,
      timestamp: cols[0] || '',
      seat: cols[1] || '',
      row: cols[2] || '',
      status: cols[3] || '',
      brief: cols[4] || '',
      isCommentOrEmpty: false
    };
  });
}

/**
 * Reorders dispatch ledger rows given an array of ordered row slugs.
 * Preserves completed/terminal rows and comments in place while repositioning
 * active/pending tasks according to the operator's specified order.
 */
export function reorderDispatchLedgerRows(
  lines: string[],
  orderedRowIds: string[]
): string[] {
  // 1. Sanitize lines: filter out empty/blank lines so trailing newlines from content.split('\n')
  // are never treated as comments or prepended to the top of the file
  const sanitizedLines = lines
    .map((l) => l.trimEnd())
    .filter((l) => l.trim().length > 0);

  if (sanitizedLines.length === 0) {
    return [];
  }

  // 2. Separate leading comments/headers from data rows
  const headerComments: string[] = [];
  let startIdx = 0;
  while (startIdx < sanitizedLines.length && sanitizedLines[startIdx].trim().startsWith('#')) {
    headerComments.push(sanitizedLines[startIdx]);
    startIdx++;
  }

  const dataLines = sanitizedLines.slice(startIdx);
  const orderedSet = new Set(orderedRowIds);

  // Group rows by task slug (row column, index 2)
  const taskRowsMap = new Map<string, string[]>();
  for (const line of dataLines) {
    if (line.trim().startsWith('#')) continue;
    const cols = line.split('\t');
    const slug = cols[2];
    if (slug) {
      if (!taskRowsMap.has(slug)) {
        taskRowsMap.set(slug, []);
      }
      taskRowsMap.get(slug)!.push(line);
    }
  }

  // Find index of first row targeted by orderedRowIds
  const firstOrderedIdx = dataLines.findIndex((line) => {
    if (line.trim().startsWith('#')) return false;
    const cols = line.split('\t');
    return cols[2] && orderedSet.has(cols[2]);
  });

  if (firstOrderedIdx === -1) {
    return [...headerComments, ...dataLines];
  }

  // Historical completed/terminal rows preceding reordered tasks remain in chronological place
  const beforeRows: string[] = [];
  for (let i = 0; i < firstOrderedIdx; i++) {
    const line = dataLines[i];
    if (line.trim().startsWith('#')) {
      beforeRows.push(line);
      continue;
    }
    const cols = line.split('\t');
    const slug = cols[2];
    if (!orderedSet.has(slug)) {
      beforeRows.push(line);
    }
  }

  // Reordered tasks in operator-specified order
  const reorderedRows: string[] = [];
  const emittedSlugs = new Set<string>();
  for (const slug of orderedRowIds) {
    if (emittedSlugs.has(slug)) continue;
    if (taskRowsMap.has(slug)) {
      const taskEntries = taskRowsMap.get(slug)!;
      for (const raw of taskEntries) {
        reorderedRows.push(raw);
      }
      emittedSlugs.add(slug);
    }
  }

  // Remaining rows following the reordered section
  const afterRows: string[] = [];
  for (let i = firstOrderedIdx; i < dataLines.length; i++) {
    const line = dataLines[i];
    if (line.trim().startsWith('#')) {
      afterRows.push(line);
      continue;
    }
    const cols = line.split('\t');
    const slug = cols[2];
    if (!emittedSlugs.has(slug)) {
      afterRows.push(line);
    }
  }

  return [...headerComments, ...beforeRows, ...reorderedRows, ...afterRows];
}
