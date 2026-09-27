import fs from 'node:fs';
import path from 'node:path';
import Database from 'better-sqlite3';

export interface DbConfig {
  dbPath?: string;
  busyTimeoutMs?: number;
}

export interface DbDiagnostics {
  resolvedPath: string;
  exists: boolean;
  sizeBytes: number;
  journalMode: string;
  busyTimeout: number;
  walFileExists: boolean;
  shmFileExists: boolean;
  lastChecked: string;
}

const PRIMARY_DB_PATH = '/home/mboyle/bd-persist/accounting/usage.sqlite';
const FALLBACK_DB_PATH = '/home/mboyle/usage.sqlite';
const DEFAULT_BUSY_TIMEOUT_MS = 5000;

// Module-scoped singletons
let readOnlyDbInstance: Database.Database | null = null;
let cachedResolvedPath: string | null = null;
let isWalEnforced = false;

/**
 * Resolves the authoritative database path in order of precedence:
 * 1. process.env.USAGE_DB_PATH (if defined, non-empty, and file exists)
 * 2. PRIMARY_DB_PATH (/home/mboyle/bd-persist/accounting/usage.sqlite, if exists and size > 0)
 * 3. FALLBACK_DB_PATH (/home/mboyle/usage.sqlite, if exists)
 * 4. Defaults to PRIMARY_DB_PATH
 */
export function resolveDbPath(): string {
  if (cachedResolvedPath) {
    return cachedResolvedPath;
  }

  const envPath = process.env.USAGE_DB_PATH?.trim();
  if (envPath && fs.existsSync(envPath)) {
    cachedResolvedPath = path.resolve(envPath);
    return cachedResolvedPath;
  }

  if (fs.existsSync(PRIMARY_DB_PATH)) {
    try {
      const stat = fs.statSync(PRIMARY_DB_PATH);
      if (stat.size > 0) {
        cachedResolvedPath = PRIMARY_DB_PATH;
        return cachedResolvedPath;
      }
    } catch {
      // Fall through to secondary check
    }
  }

  if (fs.existsSync(FALLBACK_DB_PATH)) {
    cachedResolvedPath = FALLBACK_DB_PATH;
    return cachedResolvedPath;
  }

  // Default fallback
  cachedResolvedPath = PRIMARY_DB_PATH;
  return cachedResolvedPath;
}

/**
 * Resets the cached database path (useful for testing and environment switches).
 */
export function resetDbPathCache(): void {
  cachedResolvedPath = null;
}

/**
 * Ensures that the target database is operating in WAL journal mode with a 5000ms busy timeout.
 * Note: PRAGMA journal_mode = WAL writes to the SQLite database header and CANNOT be executed
 * on a connection opened with mode=ro. This initialization step opens a brief read-write
 * handle to set the header pragma if not already in WAL mode.
 */
export function ensureWalMode(targetPath?: string): void {
  if (isWalEnforced && !targetPath) {
    return;
  }

  const resolved = targetPath || resolveDbPath();

  if (!fs.existsSync(resolved)) {
    console.warn(`[db] Target database does not exist at ${resolved}; skipping WAL enforcement.`);
    return;
  }

  try {
    // Open briefly in read-write mode to inspect/set WAL mode
    const initDb = new Database(resolved, {
      timeout: DEFAULT_BUSY_TIMEOUT_MS,
      fileMustExist: true,
    });

    try {
      const modeResult = initDb.pragma('journal_mode', { simple: true }) as string;
      if (String(modeResult).toLowerCase() !== 'wal') {
        const setWal = initDb.pragma('journal_mode = WAL', { simple: true }) as string;
        console.log(`[db] Switched ${resolved} journal_mode from ${modeResult} to ${setWal}`);
      }

      initDb.pragma(`busy_timeout = ${DEFAULT_BUSY_TIMEOUT_MS}`);
      isWalEnforced = true;
    } finally {
      initDb.close();
    }
  } catch (err: any) {
    console.warn(`[db] Warning during WAL mode enforcement on ${resolved}: ${err.message}`);
    // If the file is mounted read-only on the filesystem, don't crash startup
  }
}

/**
 * Retrieves the cached read-only Database instance for dashboard queries.
 * Enforces WAL mode on startup, PRAGMA busy_timeout = 5000, and mode=ro.
 */
export function getReadOnlyDb(config?: DbConfig): Database.Database {
  if (readOnlyDbInstance) {
    return readOnlyDbInstance;
  }

  const dbPath = config?.dbPath || resolveDbPath();
  const timeoutMs = config?.busyTimeoutMs ?? DEFAULT_BUSY_TIMEOUT_MS;

  // Enforce WAL mode on startup using read-write handle
  ensureWalMode(dbPath);

  // Open read-only connection using direct resolved filesystem path
  const resolvedDbPath = path.resolve(dbPath);

  readOnlyDbInstance = new Database(resolvedDbPath, {
    readonly: true,
    fileMustExist: true,
    timeout: timeoutMs,
  });

  // Configure busy timeout on the read-only connection
  readOnlyDbInstance.pragma(`busy_timeout = ${timeoutMs}`);

  return readOnlyDbInstance;
}

/**
 * Type-safe query helper executing a prepared statement returning all rows.
 */
export function queryAll<T = any>(sql: string, params: any[] = []): T[] {
  const db = getReadOnlyDb();
  const stmt = db.prepare(sql);
  return stmt.all(...params) as T[];
}

/**
 * Type-safe query helper executing a prepared statement returning the first row.
 */
export function queryOne<T = any>(sql: string, params: any[] = []): T | undefined {
  const db = getReadOnlyDb();
  const stmt = db.prepare(sql);
  return stmt.get(...params) as T | undefined;
}

/**
 * Returns diagnostic metadata about the current database connection and storage files.
 */
export function getDbDiagnostics(): DbDiagnostics {
  const resolved = resolveDbPath();
  const exists = fs.existsSync(resolved);
  let sizeBytes = 0;
  let journalMode = 'UNKNOWN';
  let busyTimeout = 0;

  if (exists) {
    try {
      sizeBytes = fs.statSync(resolved).size;
      const db = getReadOnlyDb();
      journalMode = String(db.pragma('journal_mode', { simple: true }));
      busyTimeout = Number(db.pragma('busy_timeout', { simple: true }));
    } catch {
      // Diagnostic query failure fallback
    }
  }

  return {
    resolvedPath: resolved,
    exists,
    sizeBytes,
    journalMode,
    busyTimeout,
    walFileExists: fs.existsSync(`${resolved}-wal`),
    shmFileExists: fs.existsSync(`${resolved}-shm`),
    lastChecked: new Date().toISOString(),
  };
}

/**
 * Gracefully closes the cached read-only database instance.
 */
export function closeDb(): void {
  if (readOnlyDbInstance) {
    try {
      readOnlyDbInstance.close();
    } catch (err: any) {
      console.warn(`[db] Error closing database connection: ${err.message}`);
    } finally {
      readOnlyDbInstance = null;
      isWalEnforced = false;
    }
  }
}
