import fs from 'node:fs';
import path from 'node:path';
import Database from 'better-sqlite3';

export interface DbConfig { dbPath?: string; busyTimeoutMs?: number; }
export interface DbDiagnostics {
  resolvedPath: string; exists: boolean; sizeBytes: number; journalMode: string;
  busyTimeout: number; walFileExists: boolean; shmFileExists: boolean; lastChecked: string;
}
let instance: Database.Database | null = null;
let openedPath: string | null = null;
export function resolveDbPath(): string {
  return path.resolve(process.env.USAGE_DB_PATH?.trim() || '/home/mboyle/bd-persist/accounting/usage.sqlite');
}
export function resetDbPathCache(): void { closeDb(); }
export function getReadOnlyDb(config?: DbConfig): Database.Database {
  const filename = path.resolve(config?.dbPath || resolveDbPath());
  if (instance && openedPath !== filename) closeDb();
  if (!instance) {
    instance = new Database(filename, { readonly: true, fileMustExist: true, timeout: config?.busyTimeoutMs ?? 1000 });
    openedPath = filename;
  }
  return instance;
}
export function queryAll<T = unknown>(sql: string, params: unknown[] = []): T[] {
  return getReadOnlyDb().prepare(sql).all(...params) as T[];
}
export function queryOne<T = unknown>(sql: string, params: unknown[] = []): T | undefined {
  return getReadOnlyDb().prepare(sql).get(...params) as T | undefined;
}
export function getDbDiagnostics(): DbDiagnostics {
  const resolvedPath = resolveDbPath();
  const exists = fs.existsSync(resolvedPath);
  let journalMode = 'UNKNOWN', busyTimeout = 0;
  if (exists) {
    try {
      journalMode = String(getReadOnlyDb().pragma('journal_mode', { simple: true }));
      busyTimeout = Number(getReadOnlyDb().pragma('busy_timeout', { simple: true }));
    } catch { /* unavailable remains UNKNOWN */ }
  }
  return { resolvedPath, exists, sizeBytes: exists ? fs.statSync(resolvedPath).size : 0,
    journalMode, busyTimeout, walFileExists: fs.existsSync(resolvedPath + '-wal'),
    shmFileExists: fs.existsSync(resolvedPath + '-shm'), lastChecked: new Date().toISOString() };
}
export function closeDb(): void {
  instance?.close(); instance = null; openedPath = null;
}
