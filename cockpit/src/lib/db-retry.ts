export interface RetryOptions {
  /** Maximum number of retry attempts before giving up (default: 5). */
  maxRetries?: number;
  /** Initial base delay in milliseconds (default: 25). */
  baseDelayMs?: number;
  /** Maximum cap for the delay in milliseconds (default: 1000). */
  maxDelayMs?: number;
  /** Optional callback invoked on each retry attempt for logging and telemetry. */
  onRetry?: (error: unknown, attempt: number, delayMs: number) => void;
}

const DEFAULT_MAX_RETRIES = 5;
const DEFAULT_BASE_DELAY_MS = 25;
const DEFAULT_MAX_DELAY_MS = 1000;

/**
 * Evaluates whether an unknown error represents an SQLite transient lock/contention condition.
 */
export function isSqliteBusyError(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false;
  }

  const err = error as Record<string, any>;
  const code = String(err.code || '').toUpperCase();
  const message = String(err.message || '').toLowerCase();

  return (
    code === 'SQLITE_BUSY' ||
    code === 'SQLITE_LOCKED' ||
    code.startsWith('SQLITE_BUSY') ||
    message.includes('database is locked') ||
    message.includes('database table is locked') ||
    message.includes('sqlite_busy') ||
    message.includes('sqlite_locked') ||
    message.includes('busy') ||
    message.includes('resource temporarily unavailable')
  );
}

/**
 * Calculates exponential backoff with full random jitter (AWS Decorrelated/Full Jitter algorithm).
 *
 * delay = random(floor, min(maxDelayMs, baseDelayMs * 2^(attempt - 1)))
 */
export function calculateFullJitterDelay(
  attempt: number,
  baseDelayMs: number = DEFAULT_BASE_DELAY_MS,
  maxDelayMs: number = DEFAULT_MAX_DELAY_MS
): number {
  const exponentialDelay = Math.min(maxDelayMs, baseDelayMs * Math.pow(2, attempt - 1));
  const floorMs = Math.min(5, Math.floor(baseDelayMs / 2));
  const randomRange = Math.max(0, exponentialDelay - floorMs);
  return floorMs + Math.floor(Math.random() * (randomRange + 1));
}

/**
 * Wraps a synchronous or asynchronous database query in a resilient retry loop
 * using exponential backoff with full random jitter.
 *
 * @template T Return type of the database operation.
 * @param operation Function executing the query or transaction.
 * @param options Configuration options for retries and backoff.
 * @returns Promise resolving to the operation result.
 * @throws The original error if non-retryable or if maxRetries is exceeded.
 */
export async function withDbRetry<T>(
  operation: () => T | Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const maxRetries = options.maxRetries ?? DEFAULT_MAX_RETRIES;
  const baseDelayMs = options.baseDelayMs ?? DEFAULT_BASE_DELAY_MS;
  const maxDelayMs = options.maxDelayMs ?? DEFAULT_MAX_DELAY_MS;
  let attempt = 0;

  while (true) {
    try {
      return await operation();
    } catch (error: unknown) {
      attempt++;

      if (!isSqliteBusyError(error) || attempt > maxRetries) {
        throw error;
      }

      const delayMs = calculateFullJitterDelay(attempt, baseDelayMs, maxDelayMs);

      if (options.onRetry) {
        try {
          options.onRetry(error, attempt, delayMs);
        } catch {
          // Prevent onRetry hook exceptions from hijacking the retry loop
        }
      }

      // Asynchronous sleep releases Node.js event loop
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
}
