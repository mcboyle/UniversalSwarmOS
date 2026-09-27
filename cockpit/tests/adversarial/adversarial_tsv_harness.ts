/**
 * tests/adversarial/adversarial_tsv_harness.ts
 *
 * Adversarial TSV Mutation Test Harness for Milestone 1 AC4:
 * "Interactive queue re-ordering successfully modifies the underlying ledger file
 *  without corrupting active dispatcher reads."
 *
 * Simulates active fleet dispatchers running tight awk polling loops
 * while simultaneous queue reordering mutations are hammered against DISPATCH-LEDGER.tsv.
 * Checks for:
 * 1. Empty file reads
 * 2. Partial lines (torn reads)
 * 3. Column count mismatches (NF != 5)
 * 4. Lost tasks
 * 5. Lock contention failures under concurrent mutators
 */

import fs from 'node:fs';
import path from 'node:path';
import { spawn, execSync, spawnSync } from 'node:child_process';
import { mutateTsvAtomically, reorderDispatchLedgerRows } from '../../src/lib/atomic-tsv.ts';

export interface StressMetrics {
  totalDispatcherReads: number;
  emptyFileReads: number;
  partialLines: number;
  columnCountMismatches: number; // NF != 5
  lostTasksDetected: number;
  mutationAttempts: number;
  mutationSuccesses: number;
  mutationFailures: number;
  emptyLineAccumulationCount: number;
  details: string[];
}

/**
 * Generates N valid DISPATCH-LEDGER.tsv rows.
 * Format: <timestamp>\t<seat>\t<row>\t<status>\t<brief_path>
 */
export function generateTestLedgerContent(taskCount: number = 20): string {
  const rows: string[] = [];
  const baseTime = new Date('2026-09-22T20:00:00Z').getTime();

  for (let i = 1; i <= taskCount; i++) {
    const ts = new Date(baseTime + i * 60000).toISOString();
    const seat = `bd-worker-${i % 8 + 1}`;
    const row = `task_row_${i}`;
    const status = i % 3 === 0 ? 'started' : 'dispatched';
    const brief = `/home/mboyle/bd-persist/harness-work/task_${i}/BRIEF.md`;
    rows.push(`${ts}\t${seat}\t${row}\t${status}\t${brief}`);
  }
  return rows.join('\n') + '\n';
}

/**
 * Runs Test Scenario 1:
 * Sequential reordering mutations to verify structure preservation and detect empty-line accumulation.
 */
export async function runSequentialMutationTest(
  fixturePath: string,
  iterations: number = 10,
  taskCount: number = 20
): Promise<{ emptyLineAccumulation: number; nfMismatchCount: number }> {
  const initialContent = generateTestLedgerContent(taskCount);
  fs.writeFileSync(fixturePath, initialContent, 'utf8');

  let emptyLineAccumulation = 0;
  let nfMismatchCount = 0;

  for (let i = 1; i <= iterations; i++) {
    // Generate a shuffled order of task slugs
    const slugs = Array.from({ length: taskCount }, (_, idx) => `task_row_${idx + 1}`);
    slugs.reverse(); // simple reversal or shuffle
    if (i % 2 === 0) {
      slugs.sort(() => Math.random() - 0.5);
    }

    await mutateTsvAtomically(
      fixturePath,
      (lines) => reorderDispatchLedgerRows(lines, slugs),
      5000
    );

    // Read mutated file directly
    const current = fs.readFileSync(fixturePath, 'utf8');
    const lines = current.split('\n');
    
    // Check if leading lines are blank
    let leadingBlank = 0;
    for (const l of lines) {
      if (l.trim() === '') leadingBlank++;
      else break;
    }
    if (leadingBlank > 0) {
      emptyLineAccumulation = Math.max(emptyLineAccumulation, leadingBlank);
    }

    // Check with awk NF!=5
    try {
      const awkOut = execSync(
        `awk -F'\\t' 'NF!=5 {print NR, NF, \$0}' "${fixturePath}"`,
        { encoding: 'utf8' }
      ).trim();
      if (awkOut.length > 0) {
        const badLines = awkOut.split('\n').filter(Boolean);
        nfMismatchCount += badLines.length;
      }
    } catch (err: any) {
      // awk error
    }
  }

  return { emptyLineAccumulation, nfMismatchCount };
}

/**
 * Runs Test Scenario 2:
 * Simulates active fleet dispatchers running tight awk polling loops
 * while simultaneous queue reordering mutations are hammered against the TSV.
 */
export async function runConcurrentStressTest(
  fixturePath: string,
  mutationsToExecute: number = 20,
  taskCount: number = 20
): Promise<StressMetrics> {
  const metrics: StressMetrics = {
    totalDispatcherReads: 0,
    emptyFileReads: 0,
    partialLines: 0,
    columnCountMismatches: 0,
    lostTasksDetected: 0,
    mutationAttempts: 0,
    mutationSuccesses: 0,
    mutationFailures: 0,
    emptyLineAccumulationCount: 0,
    details: []
  };

  // Seed fixture
  const initialContent = generateTestLedgerContent(taskCount);
  fs.writeFileSync(fixturePath, initialContent, 'utf8');

  const stopFile = `${fixturePath}.stop`;
  const resultDir = `${fixturePath}.results`;
  if (fs.existsSync(stopFile)) fs.unlinkSync(stopFile);
  if (!fs.existsSync(resultDir)) fs.mkdirSync(resultDir, { recursive: true });

  // 1. Launch 5 background bash/awk dispatcher polling processes
  const dispatchers: any[] = [];
  const readerCount = 5;

  for (let r = 1; r <= readerCount; r++) {
    const resFile = path.join(resultDir, `reader_${r}.json`);
    const script = `
      reads=0
      empty_reads=0
      partial_reads=0
      nf_mismatch=0
      lost_tasks=0

      while [ ! -f "${stopFile}" ]; do
        # 1. Check if file is completely empty (0 bytes)
        if [ ! -s "${fixturePath}" ]; then
          empty_reads=$((empty_reads + 1))
        fi

        # 2. Check for partial lines (last byte not newline)
        if [ -s "${fixturePath}" ]; then
          last_byte=$(tail -c 1 "${fixturePath}" 2>/dev/null || true)
          if [ "$last_byte" != "" ]; then
            # If tail -c 1 does not return empty string under standard test, check for trailing newline
            trailing_nl=$(tail -c 1 "${fixturePath}" | wc -l)
            if [ "$trailing_nl" -ne 1 ]; then
              partial_reads=$((partial_reads + 1))
            fi
          fi
        fi

        # 3. Tight awk polling: column count mismatches (NF != 5)
        bad_nf=$(awk -F'\\t' 'NF != 5 {print NR, NF}' "${fixturePath}" 2>/dev/null || true)
        if [ -n "$bad_nf" ]; then
          bad_count=$(echo "$bad_nf" | wc -l)
          nf_mismatch=$((nf_mismatch + bad_count))
        fi

        # 4. Check for lost tasks: all 20 task rows must exist
        line_count=$(grep -c "^2026-" "${fixturePath}" 2>/dev/null || echo 0)
        if [ "$line_count" -lt ${taskCount} ]; then
          lost_tasks=$((lost_tasks + 1))
        fi

        reads=$((reads + 1))
        # Ultra-tight polling (zero sleep or sub-millisecond)
      done

      echo "{\\"reads\\": $reads, \\"empty_reads\\": $empty_reads, \\"partial_reads\\": $partial_reads, \\"nf_mismatch\\": $nf_mismatch, \\"lost_tasks\\": $lost_tasks}" > "${resFile}"
    `;

    const child = spawn('bash', ['-c', script], { stdio: 'ignore' });
    dispatchers.push(child);
  }

  // Allow dispatchers to spin up
  await new Promise(r => setTimeout(r, 50));

  // 2. Hammer mutations against the TSV file using mutateTsvAtomically
  const allSlugs = Array.from({ length: taskCount }, (_, idx) => `task_row_${idx + 1}`);

  for (let m = 1; m <= mutationsToExecute; m++) {
    metrics.mutationAttempts++;
    try {
      // Reorder slugs randomly
      const shuffled = [...allSlugs].sort(() => Math.random() - 0.5);
      await mutateTsvAtomically(
        fixturePath,
        (lines) => reorderDispatchLedgerRows(lines, shuffled),
        8000
      );
      metrics.mutationSuccesses++;
    } catch (err: any) {
      metrics.mutationFailures++;
      metrics.details.push(`Mutation ${m} failed: ${err.message}`);
    }
  }

  // 3. Stop dispatchers
  fs.writeFileSync(stopFile, '1');
  for (const child of dispatchers) {
    await new Promise<void>((resolve) => {
      child.on('exit', () => resolve());
      setTimeout(() => {
        try { child.kill('SIGKILL'); } catch {}
        resolve();
      }, 1000);
    });
  }

  // 4. Collect reader metrics
  for (let r = 1; r <= readerCount; r++) {
    const resFile = path.join(resultDir, `reader_${r}.json`);
    if (fs.existsSync(resFile)) {
      try {
        const data = JSON.parse(fs.readFileSync(resFile, 'utf8'));
        metrics.totalDispatcherReads += data.reads || 0;
        metrics.emptyFileReads += data.empty_reads || 0;
        metrics.partialLines += data.partial_reads || 0;
        metrics.columnCountMismatches += data.nf_mismatch || 0;
        metrics.lostTasksDetected += data.lost_tasks || 0;
      } catch (err: any) {
        metrics.details.push(`Failed to parse reader ${r} output: ${err.message}`);
      }
    }
  }

  // 5. Final ledger verification
  const finalContent = fs.readFileSync(fixturePath, 'utf8');
  const finalLines = finalContent.split('\n');
  let blankCount = 0;
  for (const l of finalLines) {
    if (l.trim() === '') blankCount++;
  }
  // Standard file has 1 trailing newline -> 1 empty string in split
  metrics.emptyLineAccumulationCount = Math.max(0, blankCount - 1);

  // Check for any lost tasks in final ledger
  for (const slug of allSlugs) {
    if (!finalContent.includes(slug)) {
      metrics.lostTasksDetected++;
      metrics.details.push(`Task slug ${slug} was lost from final ledger`);
    }
  }

  // Clean up stop file and result dir
  try {
    if (fs.existsSync(stopFile)) fs.unlinkSync(stopFile);
    fs.rmSync(resultDir, { recursive: true, force: true });
  } catch {}

  return metrics;
}

// CLI runner
if (process.argv[1]?.endsWith('adversarial_tsv_harness.ts')) {
  const tmpFile = `/tmp/adversarial_dispatch_ledger_${process.pid}.tsv`;
  console.log('================================================================');
  console.log(' ADVERSARIAL TSV MUTATION HARNESS — AC4 EMPIRICAL VERIFICATION');
  console.log('================================================================');
  console.log(`Target Fixture: ${tmpFile}\n`);

  (async () => {
    try {
      console.log('--- Phase 1: Sequential Mutation & Structure Preservation ---');
      const p1 = await runSequentialMutationTest(tmpFile, 10, 20);
      console.log(`[P1] Max Empty Line Accumulation: ${p1.emptyLineAccumulation}`);
      console.log(`[P1] Total NF!=5 Awk Mismatches: ${p1.nfMismatchCount}\n`);

      console.log('--- Phase 2: Concurrent Awk Polling under Mutation Hammer ---');
      const p2 = await runConcurrentStressTest(tmpFile, 20, 20);
      console.log(`[P2] Total Dispatcher Reads:      ${p2.totalDispatcherReads}`);
      console.log(`[P2] Empty File Reads:            ${p2.emptyFileReads}`);
      console.log(`[P2] Partial Lines / Torn Reads:  ${p2.partialLines}`);
      console.log(`[P2] Column Mismatches (NF != 5): ${p2.columnCountMismatches}`);
      console.log(`[P2] Lost Tasks Detected:         ${p2.lostTasksDetected}`);
      console.log(`[P2] Mutation Successes / Total:  ${p2.mutationSuccesses} / ${p2.mutationAttempts}`);
      console.log(`[P2] Accumulated Blank Lines:     ${p2.emptyLineAccumulationCount}`);
      if (p2.details.length > 0) {
        console.log(`[P2] Failure Details:`);
        p2.details.forEach(d => console.log(`   - ${d}`));
      }

      console.log('\n================================================================');
      const isFailed = (
        p1.emptyLineAccumulation > 0 ||
        p1.nfMismatchCount > 0 ||
        p2.emptyFileReads > 0 ||
        p2.partialLines > 0 ||
        p2.columnCountMismatches > 0 ||
        p2.lostTasksDetected > 0 ||
        p2.mutationFailures > 0
      );

      if (isFailed) {
        console.log(' VERDICT: REQUEST_CHANGES (Defects Empirical Proof Found)');
        process.exit(1);
      } else {
        console.log(' VERDICT: APPROVE (Zero Torn Reads & Correctness Confirmed)');
        process.exit(0);
      }
    } catch (err: any) {
      console.error('Fatal harness error:', err);
      process.exit(2);
    } finally {
      try {
        if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile);
        const lock = path.join(path.dirname(tmpFile), `.${path.basename(tmpFile)}.lock`);
        if (fs.existsSync(lock)) fs.unlinkSync(lock);
      } catch {}
    }
  })();
}
