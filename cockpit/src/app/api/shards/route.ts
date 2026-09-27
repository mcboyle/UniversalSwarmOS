// src/app/api/shards/route.ts
import { NextResponse } from 'next/server';
import fs from 'node:fs';
import { mockShardsResponse } from '@/lib/mock-data';
import type { ShardsResponse, HarnessRunRecord, GateYieldRecord } from '@/lib/types';

export const dynamic = 'force-dynamic';

export async function GET(): Promise<NextResponse<ShardsResponse>> {
  const harnessLedgerPath = '/home/mboyle/bd-persist/harness/HARNESS_RUN_LEDGER.tsv';
  const gateYieldLedgerPath = '/home/mboyle/bd-persist/GATE_YIELD_LEDGER.tsv';

  try {
    const recentHarness: HarnessRunRecord[] = [];
    if (fs.existsSync(harnessLedgerPath)) {
      const content = fs.readFileSync(harnessLedgerPath, 'utf8');
      const lines = content.trim().split('\n').slice(-20);
      for (const line of lines) {
        const [timestamp, status, test, exit_code, duration_s] = line.split('\t');
        if (test) {
          recentHarness.push({
            timestamp: timestamp || '',
            status: (status as any) || 'PASS',
            test: test.split('/').pop() || test,
            exit_code: parseInt(exit_code || '0', 10),
            duration_s: parseFloat(duration_s || '0')
          });
        }
      }
    }

    const recentGates: GateYieldRecord[] = [];
    if (fs.existsSync(gateYieldLedgerPath)) {
      const content = fs.readFileSync(gateYieldLedgerPath, 'utf8');
      const lines = content.trim().split('\n').slice(-20);
      for (const line of lines) {
        const [timestamp, tool, verdict, cut_or_test, details] = line.split('\t');
        if (cut_or_test) {
          recentGates.push({
            timestamp: timestamp || '',
            tool: tool || '',
            verdict: (verdict as any) || 'pass',
            cut_or_test: cut_or_test || '',
            details: details || ''
          });
        }
      }
    }

    // Try fetching live Gitea Actions API with a 1.5-second timeout
    let giteaData: any = null;
    try {
      const res = await fetch('http://10.0.70.162:3000/api/v1/repos/Mboyle/BD-ci/actions/runs/latest/jobs', {
        signal: AbortSignal.timeout(1500)
      });
      if (res.ok) {
        giteaData = await res.json();
      }
    } catch {}

    if (giteaData && Array.isArray(giteaData.jobs)) {
      return NextResponse.json({
        timestamp: new Date().toISOString(),
        repo: 'Mboyle/BD-ci',
        run_id: String(giteaData.run_id || '16'),
        total_shards: giteaData.jobs.length,
        status: {
          completed: giteaData.jobs.filter((j: any) => j.status === 'completed').length,
          running: giteaData.jobs.filter((j: any) => j.status === 'running').length,
          queued: giteaData.jobs.filter((j: any) => j.status === 'queued').length
        },
        conclusion: {
          success: giteaData.jobs.filter((j: any) => j.conclusion === 'success').length,
          failure: giteaData.jobs.filter((j: any) => j.conclusion === 'failure').length
        },
        failed_shards: giteaData.jobs.filter((j: any) => j.conclusion === 'failure').map((j: any) => j.name),
        shards: mockShardsResponse.shards,
        recent_harness_runs: recentHarness.length > 0 ? recentHarness : mockShardsResponse.recent_harness_runs,
        recent_gate_yields: recentGates.length > 0 ? recentGates : mockShardsResponse.recent_gate_yields,
        source: 'gitea'
      });
    }

    // Return baseline with real local ledger records
    return NextResponse.json({
      ...mockShardsResponse,
      timestamp: new Date().toISOString(),
      recent_harness_runs: recentHarness.length > 0 ? recentHarness : mockShardsResponse.recent_harness_runs,
      recent_gate_yields: recentGates.length > 0 ? recentGates : mockShardsResponse.recent_gate_yields,
      source: recentHarness.length > 0 || recentGates.length > 0 ? 'local_ledger' : 'mock'
    });
  } catch (error) {
    console.error('[/api/shards GET error]:', error);
    return NextResponse.json({
      ...mockShardsResponse,
      timestamp: new Date().toISOString(),
      source: 'mock'
    });
  }
}
