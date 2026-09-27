/**
 * tests/adversarial/test_reorder_logic.ts
 *
 * Targeted stress tests for reorderDispatchLedgerRows and parseDispatchLedgerLines
 */

import assert from 'node:assert';
import { reorderDispatchLedgerRows, parseDispatchLedgerLines } from '../../src/lib/atomic-tsv.ts';

console.log('--- Testing reorderDispatchLedgerRows Edge Cases ---');

// Case 1: Trailing newline handling
{
  const input = [
    '2026-09-22T20:00:00Z\tseat1\trow1\tdispatched\t/brief1',
    '2026-09-22T20:01:00Z\tseat2\trow2\tdispatched\t/brief2',
    '' // from content.split('\n') when file has trailing \n
  ];
  const out = reorderDispatchLedgerRows(input, ['row2', 'row1']);
  console.log('Case 1 (Trailing newline):');
  console.log('  Input line count:', input.length);
  console.log('  Output lines:', JSON.stringify(out));
  console.log('  First line is empty?:', out[0] === '');
}

// Case 2: Multi-row task history (state transitions)
{
  const input = [
    '2026-09-22T20:00:00Z\tseat1\ttaskA\tdispatched\t/briefA',
    '2026-09-22T20:05:00Z\tseat1\ttaskA\tstarted\t/briefA',
    '2026-09-22T20:01:00Z\tseat2\ttaskB\tdispatched\t/briefB',
    ''
  ];
  const out = reorderDispatchLedgerRows(input, ['taskB', 'taskA']);
  console.log('\nCase 2 (State transitions):');
  console.log('  Output lines:');
  out.forEach(l => console.log('   ', l));
}

// Case 3: Partial reorder (reordering only active, leaving completed alone)
{
  const input = [
    '2026-09-22T19:00:00Z\tseat1\told_completed_1\tdone\t/brief_old',
    '2026-09-22T19:05:00Z\tseat2\told_completed_2\tdone\t/brief_old2',
    '2026-09-22T20:00:00Z\tseat1\tactive_1\tdispatched\t/brief1',
    '2026-09-22T20:01:00Z\tseat2\tactive_2\tdispatched\t/brief2',
    ''
  ];
  // Operator wants active_2 before active_1:
  const out = reorderDispatchLedgerRows(input, ['active_2', 'active_1']);
  console.log('\nCase 3 (Partial reorder of active tasks):');
  console.log('  Output lines:');
  out.forEach(l => console.log('   ', l));
}

// Case 4: Idempotency under identical order
{
  const input = [
    '2026-09-22T20:00:00Z\tseat1\trow1\tdispatched\t/brief1',
    '2026-09-22T20:01:00Z\tseat2\trow2\tdispatched\t/brief2',
    ''
  ];
  const out1 = reorderDispatchLedgerRows(input, ['row1', 'row2']);
  const out2 = reorderDispatchLedgerRows(out1, ['row1', 'row2']);
  console.log('\nCase 4 (Idempotency):');
  console.log('  Pass 1:', JSON.stringify(out1));
  console.log('  Pass 2:', JSON.stringify(out2));
}
