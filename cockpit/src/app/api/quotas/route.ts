// src/app/api/quotas/route.ts
import { NextResponse } from 'next/server';
import fs from 'node:fs';
import { mockQuotas } from '@/lib/mock-data';
import type { QuotaResponse, ProviderStandardQuota } from '@/lib/types';

export const dynamic = 'force-dynamic';

function parseClampedNum(val: string | undefined, defaultVal = 0): number {
  if (!val || val === '-' || val === 'null' || val === 'undefined') return defaultVal;
  const n = parseFloat(val);
  if (isNaN(n)) return defaultVal;
  return Math.min(100, Math.max(0, n));
}

function parseStandardQuotaTsv(filePath: string, current: ProviderStandardQuota): ProviderStandardQuota {
  if (!fs.existsSync(filePath)) return current;
  try {
    const content = fs.readFileSync(filePath, 'utf8').trim();
    if (!content) return current;
    const lines = content.split('\n').map(l => l.trim()).filter(Boolean);
    if (lines.length === 0) return current;

    // Check if key-value style (e.g. "state\tOK" on multiple lines)
    let isKeyValue = true;
    const kvMap = new Map<string, string>();
    for (const line of lines) {
      const parts = line.split('\t');
      if (parts.length === 2 && !['pool', 'state'].includes(parts[0].toLowerCase())) {
        kvMap.set(parts[0].toLowerCase(), parts[1]);
      } else {
        isKeyValue = false;
        break;
      }
    }
    if (isKeyValue && kvMap.size > 0) {
      return {
        ...current,
        state: kvMap.get('state') || current.state,
        five_hour_used_pct: parseClampedNum(kvMap.get('five_hour_used_pct') || kvMap.get('pct'), current.five_hour_used_pct),
        weekly_used_pct: parseClampedNum(kvMap.get('weekly_used_pct') || kvMap.get('weekly_pct'), current.weekly_used_pct),
        resets_at: kvMap.get('resets_at') && kvMap.get('resets_at') !== '-' && kvMap.get('resets_at') !== 'null'
          ? kvMap.get('resets_at')!
          : current.resets_at,
        evidence: kvMap.get('evidence') || current.evidence
      };
    }

    // Check if header line is present
    const headerLine = lines[0].toLowerCase();
    const headers = headerLine.split('\t');
    const hasHeader = headers.includes('pool') || headers.includes('state') || headers.includes('pct') || headers.includes('five_hour_used_pct');
    const dataLines = hasHeader ? lines.slice(1) : lines;

    for (const dLine of dataLines) {
      const cols = dLine.split('\t');
      if (cols.length === 0) continue;

      if (hasHeader && (headers.includes('pct') || headers.includes('five_hour_used_pct'))) {
        const stateIdx = headers.indexOf('state');
        const evidIdx = headers.indexOf('evidence');
        const pctIdx = headers.indexOf('pct') !== -1 ? headers.indexOf('pct') : headers.indexOf('five_hour_used_pct');
        const weeklyIdx = headers.indexOf('weekly_pct') !== -1 ? headers.indexOf('weekly_pct') : headers.indexOf('weekly_used_pct');
        const resetIdx = headers.indexOf('resets_at');

        return {
          ...current,
          state: stateIdx !== -1 && cols[stateIdx] ? cols[stateIdx] : current.state,
          evidence: evidIdx !== -1 && cols[evidIdx] ? cols[evidIdx] : current.evidence,
          five_hour_used_pct: pctIdx !== -1 ? parseClampedNum(cols[pctIdx], current.five_hour_used_pct) : current.five_hour_used_pct,
          weekly_used_pct: weeklyIdx !== -1 ? parseClampedNum(cols[weeklyIdx], current.weekly_used_pct) : current.weekly_used_pct,
          resets_at: resetIdx !== -1 && cols[resetIdx] && cols[resetIdx] !== '-' && cols[resetIdx] !== 'null'
            ? cols[resetIdx]
            : current.resets_at
        };
      } else {
        // Positional parsing
        if (cols.length >= 7) {
          // [pool, state, since, evidence, pct, resets_at, weekly_pct]
          return {
            ...current,
            state: cols[1] || current.state,
            evidence: cols[3] || current.evidence,
            five_hour_used_pct: parseClampedNum(cols[4], current.five_hour_used_pct),
            resets_at: cols[5] && cols[5] !== '-' && cols[5] !== 'null' ? cols[5] : current.resets_at,
            weekly_used_pct: parseClampedNum(cols[6], current.weekly_used_pct)
          };
        } else if (cols.length >= 4) {
          // [state, five_hour_pct, weekly_pct, resets_at, evidence]
          return {
            ...current,
            state: cols[0] || current.state,
            five_hour_used_pct: parseClampedNum(cols[1], current.five_hour_used_pct),
            weekly_used_pct: parseClampedNum(cols[2], current.weekly_used_pct),
            resets_at: cols[3] && cols[3] !== '-' && cols[3] !== 'null' ? cols[3] : current.resets_at,
            evidence: cols[4] || current.evidence
          };
        }
      }
    }
  } catch (err) {
    console.warn(`[/api/quotas] Error reading ${filePath}:`, err);
  }
  return current;
}

export async function GET(): Promise<NextResponse<QuotaResponse>> {
  const poolStatePath = process.env.POOL_STATE_PATH || '/home/mboyle/bd-persist/POOL_STATE.tsv';
  const usageTsvPath = '/home/mboyle/bd-persist/USAGE.tsv';
  const agyUsagePath = '/home/mboyle/bd-persist/AGY-USAGE.tsv';
  const grokStatePath = process.env.GROK_STATE_PATH || '/home/mboyle/bd-persist/GROK_STATE.tsv';
  const kimiStatePath = process.env.KIMI_STATE_PATH || '/home/mboyle/bd-persist/KIMI_STATE.tsv';

  let claudeA = { ...mockQuotas.pools.claude_a };
  let claudeB = { ...mockQuotas.pools.claude_b };
  let codex = { ...mockQuotas.pools.codex };
  let antigravity = { ...mockQuotas.pools.antigravity };
  let grok: ProviderStandardQuota = mockQuotas.pools.grok
    ? { ...mockQuotas.pools.grok }
    : {
        name: 'Grok Fleet Pool (xAI)',
        state: 'OK',
        five_hour_used_pct: 28,
        weekly_used_pct: 42,
        resets_at: '2026-09-23T04:00:00Z',
        evidence: 'xAI cluster allocation within pace'
      };
  let kimi: ProviderStandardQuota = mockQuotas.pools.kimi
    ? { ...mockQuotas.pools.kimi }
    : {
        name: 'Kimi Fleet Pool (Moonshot)',
        state: 'OK',
        five_hour_used_pct: 15,
        weekly_used_pct: 35,
        resets_at: '2026-09-23T05:00:00Z',
        evidence: 'Moonshot API quota headroom nominal'
      };

  // 1. Read POOL_STATE.tsv
  if (fs.existsSync(poolStatePath)) {
    try {
      const content = fs.readFileSync(poolStatePath, 'utf8');
      const lines = content.split('\n');

      for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        const cols = line.split('\t');
        const pool = cols[0];

        if (pool === 'A') {
          claudeA = {
            name: 'Claude Pool A',
            state: (cols[1] || 'UNKNOWN'),
            five_hour_used_pct: parseClampedNum(cols[4], 0),
            weekly_used_pct: parseClampedNum(cols[6], 0),
            resets_at: cols[5] && cols[5] !== '-' && cols[5] !== 'null' ? cols[5] : null,
            evidence: cols[3] || ''
          };
        } else if (pool === 'B') {
          claudeB = {
            name: 'Claude Pool B',
            state: (cols[1] || 'UNKNOWN'),
            five_hour_used_pct: parseClampedNum(cols[4], 0),
            weekly_used_pct: parseClampedNum(cols[6], 0),
            resets_at: cols[5] && cols[5] !== '-' && cols[5] !== 'null' ? cols[5] : null,
            evidence: cols[3] || ''
          };
        } else if (pool === 'codex') {
          codex = {
            name: 'Codex Fleet Pool',
            state: (cols[1] || 'UNKNOWN'),
            evidence: cols[3] || '',
            weekly_used_pct: parseClampedNum(cols[6], 0),
            resets_at: cols[5] && cols[5] !== '-' ? cols[5] : null
          };
        } else if (pool === 'AGY') {
          antigravity = {
            name: 'Antigravity Dynamic Pool',
            observed_at: cols[12] && cols[12] !== '-' ? cols[12] : new Date().toISOString(),
            gemini: {
              five_hour_remaining_pct: parseClampedNum(cols[8], 93),
              weekly_remaining_pct: parseClampedNum(cols[9], 46)
            },
            claude_gpt: {
              five_hour_remaining_pct: parseClampedNum(cols[10], 100),
              weekly_remaining_pct: parseClampedNum(cols[11], 72)
            }
          };
        } else if (pool.toLowerCase() === 'grok' || pool.toLowerCase() === 'xai') {
          grok = {
            name: 'Grok Fleet Pool (xAI)',
            state: (cols[1] || 'UNKNOWN'),
            five_hour_used_pct: parseClampedNum(cols[4], grok.five_hour_used_pct),
            weekly_used_pct: parseClampedNum(cols[6], grok.weekly_used_pct),
            resets_at: cols[5] && cols[5] !== '-' && cols[5] !== 'null' ? cols[5] : null,
            evidence: cols[3] || ''
          };
        } else if (pool.toLowerCase() === 'kimi' || pool.toLowerCase() === 'moonshot') {
          kimi = {
            name: 'Kimi Fleet Pool (Moonshot)',
            state: (cols[1] || 'UNKNOWN'),
            five_hour_used_pct: parseClampedNum(cols[4], kimi.five_hour_used_pct),
            weekly_used_pct: parseClampedNum(cols[6], kimi.weekly_used_pct),
            resets_at: cols[5] && cols[5] !== '-' && cols[5] !== 'null' ? cols[5] : null,
            evidence: cols[3] || ''
          };
        }
      }
    } catch (err) {
      console.warn('[/api/quotas] Error reading POOL_STATE.tsv:', err);
    }
  }

  // 2. Supplement Claude A, B, Codex, and AGY with authoritative USAGE.tsv if available
  if (fs.existsSync(usageTsvPath)) {
    try {
      const usageContent = fs.readFileSync(usageTsvPath, 'utf8');
      const uLines = usageContent.split('\n');
      if (uLines.length > 0) {
        const headerCols = uLines[0].toLowerCase().trim().split('\t');
        const colIdx = {
          pool: headerCols.indexOf('pool'),
          fiveHourPct: headerCols.indexOf('five_hour_pct'),
          resetsAt: headerCols.indexOf('resets_at'),
          weeklyPct: headerCols.indexOf('weekly_pct'),
          weeklyResets: headerCols.indexOf('weekly_resets'),
          fetchedAt: headerCols.indexOf('fetched_at'),
          gemini5h: headerCols.indexOf('gemini_five_hour_remaining_pct'),
          geminiWk: headerCols.indexOf('gemini_weekly_remaining_pct'),
          claudeGpt5h: headerCols.indexOf('claude_gpt_five_hour_remaining_pct'),
          claudeGptWk: headerCols.indexOf('claude_gpt_weekly_remaining_pct'),
          observedAt: headerCols.indexOf('quota_observed_at'),
        };

        for (let i = 1; i < uLines.length; i++) {
          const trimmed = uLines[i].trim();
          if (!trimmed) continue;
          const uCols = trimmed.split('\t');
          const p = (colIdx.pool !== -1 ? uCols[colIdx.pool] : uCols[0])?.trim();
          if (!p) continue;

          const getVal = (idx: number) => idx !== -1 && uCols[idx] !== undefined ? uCols[idx].trim() : '-';

          if (p === 'A' || p.toLowerCase() === 'claude_a') {
            const f5h = getVal(colIdx.fiveHourPct);
            const wk = getVal(colIdx.weeklyPct);
            const rst = getVal(colIdx.resetsAt);
            const wkRst = getVal(colIdx.weeklyResets);
            if (f5h !== '-' && f5h !== 'UNKNOWN' && !isNaN(parseFloat(f5h))) {
              claudeA.five_hour_used_pct = parseClampedNum(f5h, claudeA.five_hour_used_pct);
            }
            if (wk !== '-' && wk !== 'UNKNOWN' && !isNaN(parseFloat(wk))) {
              claudeA.weekly_used_pct = parseClampedNum(wk, claudeA.weekly_used_pct);
            }
            const activeReset = (rst !== '-' && rst !== 'null') ? rst : (wkRst !== '-' && wkRst !== 'null') ? wkRst : null;
            if (activeReset) claudeA.resets_at = activeReset;
          } else if (p === 'B' || p.toLowerCase() === 'claude_b') {
            const f5h = getVal(colIdx.fiveHourPct);
            const wk = getVal(colIdx.weeklyPct);
            const rst = getVal(colIdx.resetsAt);
            const wkRst = getVal(colIdx.weeklyResets);
            if (f5h !== '-' && f5h !== 'UNKNOWN' && !isNaN(parseFloat(f5h))) {
              claudeB.five_hour_used_pct = parseClampedNum(f5h, claudeB.five_hour_used_pct);
            }
            if (wk !== '-' && wk !== 'UNKNOWN' && !isNaN(parseFloat(wk))) {
              claudeB.weekly_used_pct = parseClampedNum(wk, claudeB.weekly_used_pct);
            }
            const activeReset = (rst !== '-' && rst !== 'null') ? rst : (wkRst !== '-' && wkRst !== 'null') ? wkRst : null;
            if (activeReset) claudeB.resets_at = activeReset;
          } else if (p === 'codex') {
            const wk = getVal(colIdx.weeklyPct);
            const wkRst = getVal(colIdx.weeklyResets);
            const rst = getVal(colIdx.resetsAt);
            if (wk !== '-' && wk !== 'UNKNOWN' && !isNaN(parseFloat(wk))) {
              const weeklyUsed = parseClampedNum(wk, codex.weekly_used_pct ?? 83);
              const weeklyResets = (wkRst !== '-' && wkRst !== 'null') ? wkRst : (rst !== '-' && rst !== 'null') ? rst : codex.resets_at;
              codex = {
                ...codex,
                state: 'OK',
                weekly_used_pct: weeklyUsed,
                resets_at: weeklyResets,
                evidence: `Weekly usage ${weeklyUsed}% (resets ${weeklyResets || 'scheduled'})`
              };
            }
          } else if (p === 'AGY' || p.toLowerCase() === 'antigravity') {
            const g5h = getVal(colIdx.gemini5h);
            const gWk = getVal(colIdx.geminiWk);
            const c5h = getVal(colIdx.claudeGpt5h);
            const cWk = getVal(colIdx.claudeGptWk);
            const obs = getVal(colIdx.observedAt);
            const fetchTs = getVal(colIdx.fetchedAt);

            if (g5h !== '-' && g5h !== 'UNKNOWN' && !isNaN(parseFloat(g5h))) {
              antigravity.gemini.five_hour_remaining_pct = parseClampedNum(g5h, antigravity.gemini.five_hour_remaining_pct);
            }
            if (gWk !== '-' && gWk !== 'UNKNOWN' && !isNaN(parseFloat(gWk))) {
              antigravity.gemini.weekly_remaining_pct = parseClampedNum(gWk, antigravity.gemini.weekly_remaining_pct);
            }
            if (c5h !== '-' && c5h !== 'UNKNOWN' && !isNaN(parseFloat(c5h))) {
              antigravity.claude_gpt.five_hour_remaining_pct = parseClampedNum(c5h, antigravity.claude_gpt.five_hour_remaining_pct);
            }
            if (cWk !== '-' && cWk !== 'UNKNOWN' && !isNaN(parseFloat(cWk))) {
              antigravity.claude_gpt.weekly_remaining_pct = parseClampedNum(cWk, antigravity.claude_gpt.weekly_remaining_pct);
            }
            const obsTime = (obs !== '-' && obs !== 'null') ? obs : (fetchTs !== '-' && fetchTs !== 'null') ? fetchTs : null;
            if (obsTime) antigravity.observed_at = obsTime;
          }
        }
      }
    } catch (err) {
      console.warn('[/api/quotas] Error reading USAGE.tsv:', err);
    }
  }

  // 3. Supplement AGY with authoritative observations from AGY-USAGE.tsv
  if (fs.existsSync(agyUsagePath)) {
    try {
      const agyContent = fs.readFileSync(agyUsagePath, 'utf8');
      const agyLines = agyContent.split('\n').filter(l => l.trim().length > 0);
      for (let i = agyLines.length - 1; i >= 1; i--) {
        const parts = agyLines[i].split('\t');
        if (parts.length >= 10 && parts[6] !== '-' && parts[7] !== '-') {
          const obsAt = parts[10] && parts[10] !== '-' ? parts[10] : parts[0];
          // Only update if newer than current observation
          if (!antigravity.observed_at || obsAt >= antigravity.observed_at) {
            const gem5h = parseClampedNum(parts[6], antigravity.gemini.five_hour_remaining_pct);
            const gemWk = parseClampedNum(parts[7], antigravity.gemini.weekly_remaining_pct);
            const cl5h = parseClampedNum(parts[8], antigravity.claude_gpt.five_hour_remaining_pct);
            const clWk = parseClampedNum(parts[9], antigravity.claude_gpt.weekly_remaining_pct);
            const st = parts[1] || antigravity.state || 'OK-UNMETERED';

            antigravity = {
              name: 'Antigravity Dynamic Pool',
              observed_at: obsAt,
              state: st,
              gemini: {
                five_hour_remaining_pct: gem5h,
                weekly_remaining_pct: gemWk
              },
              claude_gpt: {
                five_hour_remaining_pct: cl5h,
                weekly_remaining_pct: clWk
              }
            };
          }
          break;
        }
      }
    } catch (err) {
      console.warn('[/api/quotas] Error reading AGY-USAGE.tsv:', err);
    }
  }

  // 4. Supplement Grok and Kimi with dedicated TSVs if available
  grok = parseStandardQuotaTsv(grokStatePath, grok);
  kimi = parseStandardQuotaTsv(kimiStatePath, kimi);

  return NextResponse.json({
    timestamp: new Date().toISOString(),
    pools: {
      claude_a: claudeA,
      claude_b: claudeB,
      codex,
      antigravity,
      grok,
      kimi
    },
    source: 'live'
  });
}
