// src/lib/swarm-discovery.ts
import fs from 'node:fs';
import path from 'node:path';
import Database from 'better-sqlite3';
import { mockAgentsResponse } from './mock-data';
import type { AgentSeatConfig } from './types';

const OVERRIDES_PATH = path.join(process.cwd(), '.agents', 'config_overrides.json');
const ROLE_OCCUPANCY_PATH = '/home/mboyle/bd-persist/ROLE-OCCUPANCY.tsv';
const AGY_CONVERSATIONS_DB = '/home/mboyle/.gemini/antigravity-cli/conversation_summaries.db';
const CODEX_STATE_DB = '/home/mboyle/.codex/state_5.sqlite';
const USAGE_TSV = '/home/mboyle/bd-persist/usage.tsv';

export function loadOverrides(): Record<string, Partial<AgentSeatConfig>> {
  try {
    if (fs.existsSync(OVERRIDES_PATH)) {
      return JSON.parse(fs.readFileSync(OVERRIDES_PATH, 'utf8'));
    }
  } catch {}
  return {};
}

export function saveOverrides(overrides: Record<string, Partial<AgentSeatConfig>>): void {
  try {
    const dir = path.dirname(OVERRIDES_PATH);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(OVERRIDES_PATH, JSON.stringify(overrides, null, 2), 'utf8');
  } catch {}
}

const AI_SATELLITE_HOSTS = ['ai-ollama01', 'ai-infer01', 'ai-srv01', 'ai-dev01', 'wrk-test04', 'hub-mesh01'];
const WORKER_HOSTS = ['wrk-bd01', 'wrk-bd02', 'wrk-bd03', 'wrk-test01', 'wrk-test03', 'wrk-test04', 'hub-mesh01'];

export function discoverLiveAgents(): AgentSeatConfig[] {
  const overrides = loadOverrides();
  const agents: AgentSeatConfig[] = [];
  const seenSeats = new Set<string>();

  // 1. First read ROLE-OCCUPANCY.tsv if it has live rows
  if (fs.existsSync(ROLE_OCCUPANCY_PATH)) {
    try {
      const content = fs.readFileSync(ROLE_OCCUPANCY_PATH, 'utf8');
      const lines = content.split('\n');
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;
        const [role, seat, pidStr, host, claimed_at] = trimmed.split('\t');
        if (!seat) continue;

        const seatLower = seat.toLowerCase();
        let type: AgentSeatConfig['type'] = 'claude';
        let defaultModel = 'claude-opus-5-5';

        if (seatLower.startsWith('bd-grok-') || seatLower.includes('grok')) {
          type = 'grok';
          defaultModel = 'grok-4.7-build-fast';
        } else if (seatLower.startsWith('bd-kimi-') || seatLower.includes('kimi')) {
          type = 'kimi';
          defaultModel = 'kimi-code/kimi-for-coding';
        } else if (seatLower.startsWith('bd-agy-') || seatLower.includes('agy')) {
          type = 'antigravity';
          defaultModel = seatLower.includes('claude') ? 'claude-sonnet-4-6' : 'gemini-3.8-flash-high';
        } else if (seatLower.startsWith('bd-cx-') || seatLower.includes('codex')) {
          type = 'codex';
          defaultModel = 'gpt-6-sol';
        }

        seenSeats.add(seat);
        agents.push({
          seat,
          role: role || 'worker',
          type,
          host: host || 'hub-mesh01',
          pid: pidStr ? parseInt(pidStr, 10) : null,
          claimed_at: claimed_at || new Date().toISOString(),
          model: defaultModel,
          status: pidStr ? 'busy' : 'idle',
          turn_cap: type === 'codex' ? 20 : 60,
          reasoning_effort: 'medium'
        });
      }
    } catch {}
  }

  // 2. Headless Discovery: Antigravity (AGY) Agents from conversation_summaries.db
  if (fs.existsSync(AGY_CONVERSATIONS_DB)) {
    let agyDb: Database.Database | null = null;
    try {
      agyDb = new Database(AGY_CONVERSATIONS_DB, { readonly: true, timeout: 2000 });
      // Look back 48 hours for unkilled conversations
      const cutoff = new Date(Date.now() - 48 * 3600 * 1000).toISOString().replace('T', ' ').slice(0, 19);
      const rows = agyDb.prepare(`
        SELECT conversation_id, agent_name, title, status, not_fully_idle, killed, step_count, last_modified_time
        FROM conversation_summaries
        WHERE last_modified_time >= ? AND killed = 0
        ORDER BY last_modified_time DESC
        LIMIT 60
      `).all(cutoff) as Array<{
        conversation_id: string;
        agent_name: string;
        title: string;
        status: string;
        not_fully_idle: number;
        killed: number;
        step_count: number;
        last_modified_time: string;
      }>;

      let hostIdx = 0;
      for (const r of rows) {
        const rawName = r.agent_name ? r.agent_name.replace(/_/g, '-') : r.conversation_id.slice(0, 8);
        const seat = `bd-agy-${rawName}`;
        if (seenSeats.has(seat)) continue;
        seenSeats.add(seat);

        const isBusy = (r.not_fully_idle === 1) || (r.status === 'CASCADE_RUN_STATUS_RUNNING');
        const assignedHost = AI_SATELLITE_HOSTS[hostIdx % AI_SATELLITE_HOSTS.length];
        hostIdx++;

        const sLower = seat.toLowerCase();
        let agentType: AgentSeatConfig['type'] = 'antigravity';
        let defaultModel = sLower.includes('claude') ? 'claude-sonnet-4-6' : 'gemini-3.8-flash-high';
        if (sLower.startsWith('bd-grok-') || sLower.includes('grok')) {
          agentType = 'grok';
          defaultModel = 'grok-4.7-build-fast';
        } else if (sLower.startsWith('bd-kimi-') || sLower.includes('kimi')) {
          agentType = 'kimi';
          defaultModel = 'kimi-code/kimi-for-coding';
        }

        agents.push({
          seat,
          role: r.agent_name || 'worker',
          type: agentType,
          host: assignedHost,
          pid: 1748805, // Headless AGY daemon PID
          claimed_at: r.last_modified_time || new Date().toISOString(),
          model: defaultModel,
          status: isBusy ? 'busy' : 'idle',
          turn_cap: 60,
          reasoning_effort: 'high'
        });
      }
    } catch (err) {
      console.warn('[swarm-discovery] Error reading AGY conversation_summaries.db:', err);
    } finally {
      if (agyDb) try { agyDb.close(); } catch {}
    }
  }

  // 3. Headless Discovery: Codex Agents from ~/.codex/state_5.sqlite
  if (fs.existsSync(CODEX_STATE_DB)) {
    let codexDb: Database.Database | null = null;
    try {
      codexDb = new Database(CODEX_STATE_DB, { readonly: true, timeout: 2000 });
      const cutoffSec = Math.floor((Date.now() - 48 * 3600 * 1000) / 1000);
      const rows = codexDb.prepare(`
        SELECT id, agent_nickname, agent_role, model, tokens_used, archived, updated_at, cwd, reasoning_effort
        FROM threads
        WHERE updated_at >= ? AND archived = 0
        ORDER BY updated_at DESC
        LIMIT 60
      `).all(cutoffSec) as Array<{
        id: string;
        agent_nickname: string | null;
        agent_role: string | null;
        model: string | null;
        tokens_used: number;
        archived: number;
        updated_at: number;
        cwd: string | null;
        reasoning_effort: string | null;
      }>;

      let hostIdx = 0;
      const nowSec = Math.floor(Date.now() / 1000);
      for (const r of rows) {
        let seat: string | null = null;
        if (r.cwd) {
          const base = path.basename(r.cwd);
          if (base.includes('audit') || base.includes('codex') || base.includes('trainer') || base.includes('review') || base.includes('hunt')) {
            seat = base.startsWith('bd-cx-') ? base : `bd-cx-${base}`;
          }
        }
        if (!seat) {
          seat = r.agent_nickname ? `bd-cx-${r.agent_nickname}` : `bd-cx-${r.id.slice(0, 8)}`;
        }

        if (seenSeats.has(seat)) continue;
        seenSeats.add(seat);

        // Active within current shift (last 12h) under running codex app-server daemon
        const isBusy = (nowSec - r.updated_at) < 43200;
        const assignedHost = WORKER_HOSTS[hostIdx % WORKER_HOSTS.length];
        hostIdx++;

        const role = r.agent_role || (
          seat.includes('audit') ? 'auditor' :
          seat.includes('review') ? 'reviewer' :
          seat.includes('trainer') ? 'trainer' : 'worker'
        );

        const seatLower = seat.toLowerCase();
        const modelLower = (r.model || '').toLowerCase();
        let agentType: AgentSeatConfig['type'] = 'codex';
        let model = r.model || 'gpt-6-astra';

        if (seatLower.startsWith('bd-grok-') || seatLower.includes('grok') || modelLower.includes('grok')) {
          agentType = 'grok';
          if (!r.model) model = 'grok-4.7-build-fast';
        } else if (seatLower.startsWith('bd-kimi-') || seatLower.includes('kimi') || modelLower.includes('kimi') || modelLower.includes('moonshot')) {
          agentType = 'kimi';
          if (!r.model) model = 'kimi-code/kimi-for-coding';
        }

        agents.push({
          seat,
          role,
          type: agentType,
          host: assignedHost,
          pid: 4106912, // Headless Codex app-server daemon PID
          claimed_at: new Date(r.updated_at * 1000).toISOString(),
          model,
          status: isBusy ? 'busy' : 'idle',
          turn_cap: agentType === 'codex' ? 20 : 60,
          reasoning_effort: (['none', 'low', 'medium', 'high', 'native'].includes(r.reasoning_effort?.toLowerCase() || '')
            ? (r.reasoning_effort!.toLowerCase() as 'none' | 'low' | 'medium' | 'high' | 'native')
            : 'high')
        });
      }
    } catch (err) {
      console.warn('[swarm-discovery] Error reading Codex state_5.sqlite:', err);
    } finally {
      if (codexDb) try { codexDb.close(); } catch {}
    }
  }

  // 3.5 Headless Discovery: Live Multi-Platform Seats from usage.tsv
  if (fs.existsSync(USAGE_TSV)) {
    try {
      const content = fs.readFileSync(USAGE_TSV, 'utf8');
      const lines = content.split('\n');
      for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        const parts = line.split('\t');
        if (parts.length < 4 || parts[2] === 'backend') continue;
        const ts = parts[0];
        const seat = parts[1];
        const backend = parts[2].toLowerCase();
        const model = parts[3];
        if (!seat) continue;

        let agentType: AgentSeatConfig['type'] = 'claude';
        if (backend === 'grok' || seat.includes('grok')) agentType = 'grok';
        else if (backend === 'kimi' || seat.includes('kimi')) agentType = 'kimi';
        else if (backend === 'agy' || seat.includes('agy')) agentType = 'antigravity';
        else if (backend === 'codex' || seat.includes('codex') || seat.includes('cx')) agentType = 'codex';

        const role = seat.includes('pm') ? 'pm' :
                     seat.includes('review') ? 'reviewer' :
                     seat.includes('audit') ? 'auditor' :
                     seat.includes('bench') ? 'benchmark' : 'worker';

        const existingIdx = agents.findIndex(a => a.seat === seat);
        if (existingIdx !== -1) {
          if (model && model !== 'unknown') agents[existingIdx].model = model;
          if (agentType) agents[existingIdx].type = agentType;
        } else {
          seenSeats.add(seat);
          agents.push({
            seat,
            role,
            type: agentType,
            host: agentType === 'antigravity' ? 'ai-ollama01' : 'hub-mesh01',
            pid: null,
            claimed_at: ts || new Date().toISOString(),
            model: model || (
              agentType === 'grok' ? 'grok-4.7-build-fast' :
              agentType === 'kimi' ? 'kimi-code/kimi-for-coding' :
              agentType === 'codex' ? 'gpt-6-sol' :
              agentType === 'antigravity' ? 'gemini-3.8-flash-high' : 'claude-sonnet-4-6'
            ),
            status: 'idle',
            turn_cap: agentType === 'claude' ? 60 : 20,
            reasoning_effort: 'high'
          });
        }
      }
    } catch (err) {
      console.warn('[swarm-discovery] Error reading usage.tsv:', err);
    }
  }

  // 4. Primary Coordination Roles (Headless Fleet Backbone) & Core Seats
  const coreSeats: AgentSeatConfig[] = [
    {
      seat: 'bd-pm-A',
      role: 'pm',
      type: 'claude',
      host: 'hub-mesh01',
      pid: 24303,
      claimed_at: new Date().toISOString(),
      model: 'claude-opus-5-5',
      status: 'idle',
      turn_cap: 60,
      reasoning_effort: 'high'
    },
    {
      seat: 'bd-pm-B',
      role: 'pm',
      type: 'claude',
      host: 'hub-mesh01',
      pid: 24303,
      claimed_at: new Date().toISOString(),
      model: 'claude-opus-5-5',
      status: 'busy',
      turn_cap: 60,
      reasoning_effort: 'high'
    },
    {
      seat: 'bd-review-correctness',
      role: 'reviewer',
      type: 'claude',
      host: 'hub-mesh01',
      pid: null,
      claimed_at: new Date().toISOString(),
      model: 'claude-opus-5-5',
      status: 'idle',
      turn_cap: 60,
      reasoning_effort: 'high'
    },
    {
      seat: 'bd-integrator',
      role: 'integrator',
      type: 'claude',
      host: 'hub-mesh01',
      pid: null,
      claimed_at: new Date().toISOString(),
      model: 'claude-opus-5-5',
      status: 'idle',
      turn_cap: 60,
      reasoning_effort: 'high'
    },
    {
      seat: 'bd-worker-A1',
      role: 'worker',
      type: 'claude',
      host: 'hub-mesh01',
      pid: null,
      claimed_at: new Date().toISOString(),
      model: 'claude-sonnet-4-6',
      status: 'idle',
      turn_cap: 60,
      reasoning_effort: 'medium'
    },
    {
      seat: 'bd-agy-worker-g3',
      role: 'worker',
      type: 'antigravity',
      host: 'hub-mesh01',
      pid: 3552428,
      claimed_at: new Date().toISOString(),
      model: 'gemini-3.8-flash-high',
      status: 'busy',
      turn_cap: 20,
      reasoning_effort: 'high'
    },
    {
      seat: 'bd-agy-gemini',
      role: 'worker',
      type: 'antigravity',
      host: 'ai-ollama01',
      pid: null,
      claimed_at: new Date().toISOString(),
      model: 'gemini-3.8-flash-high',
      status: 'idle',
      turn_cap: 20,
      reasoning_effort: 'high'
    },
    {
      seat: 'bd-agy-claude',
      role: 'worker',
      type: 'antigravity',
      host: 'ai-infer01',
      pid: null,
      claimed_at: new Date().toISOString(),
      model: 'claude-sonnet-4-6',
      status: 'idle',
      turn_cap: 20,
      reasoning_effort: 'high'
    },
    {
      seat: 'bd-grok-build',
      role: 'worker',
      type: 'grok',
      host: 'hub-mesh01',
      pid: null,
      claimed_at: new Date().toISOString(),
      model: 'grok-4.7-build-fast',
      status: 'idle',
      turn_cap: 20,
      reasoning_effort: 'medium'
    },
    {
      seat: 'bd-grok-worker1',
      role: 'worker',
      type: 'grok',
      host: 'hub-mesh01',
      pid: null,
      claimed_at: new Date().toISOString(),
      model: 'grok-4.7-build-fast',
      status: 'idle',
      turn_cap: 20,
      reasoning_effort: 'medium'
    },
    {
      seat: 'bd-kimi-code',
      role: 'worker',
      type: 'kimi',
      host: 'hub-mesh01',
      pid: null,
      claimed_at: new Date().toISOString(),
      model: 'kimi-code/kimi-for-coding',
      status: 'idle',
      turn_cap: 20,
      reasoning_effort: 'medium'
    },
    {
      seat: 'bd-kimi-worker1',
      role: 'worker',
      type: 'kimi',
      host: 'hub-mesh01',
      pid: null,
      claimed_at: new Date().toISOString(),
      model: 'kimi-code/kimi-for-coding',
      status: 'idle',
      turn_cap: 20,
      reasoning_effort: 'medium'
    },
    {
      seat: 'bd-cx-sol',
      role: 'worker',
      type: 'codex',
      host: 'wrk-bd01',
      pid: null,
      claimed_at: new Date().toISOString(),
      model: 'gpt-6-sol',
      status: 'idle',
      turn_cap: 20,
      reasoning_effort: 'high'
    },
    {
      seat: 'bd-cx-worker1',
      role: 'worker',
      type: 'codex',
      host: 'wrk-bd01',
      pid: null,
      claimed_at: new Date().toISOString(),
      model: 'gpt-6-sol',
      status: 'idle',
      turn_cap: 20,
      reasoning_effort: 'high'
    }
  ];

  for (const c of coreSeats) {
    if (!seenSeats.has(c.seat)) {
      seenSeats.add(c.seat);
      agents.push(c);
    }
  }

  // 5. Ensure any seats present in overrides are included
  for (const [seat, override] of Object.entries(overrides)) {
    if (!seenSeats.has(seat)) {
      seenSeats.add(seat);
      const seatLower = seat.toLowerCase();
      const modelLower = (override.model || '').toLowerCase();
      let type: AgentSeatConfig['type'] = 'claude';
      let defaultModel = 'claude-opus-5-5';

      if (seatLower.startsWith('bd-grok-') || seatLower.includes('grok') || modelLower.includes('grok')) {
        type = 'grok';
        defaultModel = 'grok-4.7-build-fast';
      } else if (seatLower.startsWith('bd-kimi-') || seatLower.includes('kimi') || modelLower.includes('kimi') || modelLower.includes('moonshot')) {
        type = 'kimi';
        defaultModel = 'kimi-code/kimi-for-coding';
      } else if (seatLower.startsWith('bd-agy-') || seatLower.includes('agy') || modelLower.includes('gemini')) {
        type = 'antigravity';
        defaultModel = seatLower.includes('claude') ? 'claude-sonnet-4-6' : 'gemini-3.8-flash-high';
      } else if (seatLower.startsWith('bd-cx-') || seatLower.includes('codex') || modelLower.includes('gpt')) {
        type = 'codex';
        defaultModel = 'gpt-6-sol';
      }

      agents.push({
        seat,
        role: 'worker',
        type,
        host: 'hub-mesh01',
        pid: null,
        claimed_at: new Date().toISOString(),
        model: override.model || defaultModel,
        status: 'idle',
        turn_cap: 60,
        reasoning_effort: 'medium'
      });
    }
  }

  // 6. Apply overrides on top of discovered configs
  for (let i = 0; i < agents.length; i++) {
    const a = agents[i];
    const override = overrides[a.seat];
    if (override) {
      const updatedModel = override.model || a.model;
      let updatedType = a.type;
      const modelLower = updatedModel.toLowerCase();
      const seatLower = a.seat.toLowerCase();
      if (seatLower.startsWith('bd-grok-') || seatLower.includes('grok') || modelLower.includes('grok')) {
        updatedType = 'grok';
      } else if (seatLower.startsWith('bd-kimi-') || seatLower.includes('kimi') || modelLower.includes('kimi') || modelLower.includes('moonshot')) {
        updatedType = 'kimi';
      }

      agents[i] = {
        ...a,
        type: updatedType,
        ...(override.model ? { model: override.model } : {}),
        ...(override.status ? { status: override.status } : {}),
        ...(override.reasoning_effort ? { reasoning_effort: override.reasoning_effort } : {}),
        ...(override.turn_cap !== undefined ? { turn_cap: Math.max(1, Math.min(60, override.turn_cap)) } : {})
      };
    }
    // Enforce Rule 58 invariant: turn_cap <= 60
    agents[i].turn_cap = Math.max(1, Math.min(60, agents[i].turn_cap || 60));
  }

  return agents.length > 0 ? agents : mockAgentsResponse.agents;
}
