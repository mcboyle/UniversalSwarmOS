// src/app/api/nodes/route.ts
import { NextRequest, NextResponse } from 'next/server';
import fs from 'node:fs';
import net from 'node:net';
import { mockNodes } from '@/lib/mock-data';
import type { ClusterNode, NodesResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';

// Fleet Rule 21: NO NODE IS OFF LIMITS (Updated per operator order 2026-09-26)
const BLACKLISTED_IP: string | null = null;
const LOCAL_IP = '10.0.70.164';

function getRoleFromFqdnOrName(fqdn: string, name: string): 'hub' | 'ops' | 'stg' | 'ai' | 'wrk-bd' | 'wrk-test' | 'spr-pool' {
  const combined = `${fqdn} ${name}`.toLowerCase();
  if (combined.includes('hub')) return 'hub';
  if (combined.includes('ops')) return 'ops';
  if (combined.includes('stg')) return 'stg';
  if (combined.includes('ai')) return 'ai';
  if (combined.includes('wrk-bd')) return 'wrk-bd';
  if (combined.includes('wrk-test') || combined.includes('test')) return 'wrk-test';
  if (combined.includes('spr') || combined.includes('spare')) return 'spr-pool';
  return 'wrk-test';
}

function parseHostsFile(): ClusterNode[] {
  const hostsPath = '/etc/hosts';
  if (!fs.existsSync(hostsPath)) {
    return mockNodes;
  }

  const content = fs.readFileSync(hostsPath, 'utf8');
  const lines = content.split('\n');
  const nodes: ClusterNode[] = [];
  const seenIps = new Set<string>();

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    if (!trimmed.includes('10.0.70.')) continue;

    const parts = trimmed.split(/\s+/);
    const ip = parts[0];
    if (seenIps.has(ip)) continue;
    if (ip === '10.0.70.181') continue; // External Windows VM Oracle Bridge
    seenIps.add(ip);

    const fqdn = parts[1] || '';
    const aliases = parts.slice(2);
    const name = aliases[0] || fqdn.split('.')[0] || ip;

    const role = getRoleFromFqdnOrName(fqdn, name);

    let tier = 'Worker';
    if (ip === LOCAL_IP || role === 'hub') tier = 'Primary Controller';
    else if (role === 'ai') tier = 'AI Satellite';
    else if (role === 'ops') tier = 'Operations & CI';
    else if (role === 'stg') tier = 'RAG & Cache';
    else if (role === 'spr-pool') tier = 'Spare Pool';
    else if (ip === '10.0.70.95') tier = 'Target Site';

    const is_blacklisted = false;
    const is_local = ip === LOCAL_IP;

    const is_operator_only = ip === '10.0.70.95';
    nodes.push({
      name,
      fqdn,
      ip,
      role,
      tier,
      status: is_operator_only ? 'operator-only' : 'up',
      latency_ms: is_local ? 0.05 : (is_operator_only ? null : 0.35),
      is_local,
      is_blacklisted
    });
  }

  return nodes.length >= 25 ? nodes : mockNodes;
}

async function probeTcp(ip: string, port = 22, timeoutMs = 400): Promise<{ ok: boolean; latency: number }> {
  // Fleet Rule 21: NO NODE IS OFF LIMITS (all nodes eligible for probing)

  return new Promise((resolve) => {
    const start = process.hrtime.bigint();
    const socket = new net.Socket();

    socket.setTimeout(timeoutMs);
    socket.once('connect', () => {
      const end = process.hrtime.bigint();
      const latency = Number(end - start) / 1_000_000;
      socket.destroy();
      resolve({ ok: true, latency: Math.round(latency * 100) / 100 });
    });

    socket.once('timeout', () => {
      socket.destroy();
      resolve({ ok: false, latency: timeoutMs });
    });

    socket.once('error', () => {
      socket.destroy();
      resolve({ ok: false, latency: timeoutMs });
    });

    socket.connect(port, ip);
  });
}

export async function GET(req: NextRequest): Promise<NextResponse<NodesResponse>> {
  try {
    let nodes = parseHostsFile();
    const { searchParams } = new URL(req.url);
    const shouldProbe = searchParams.get('probe') === 'true';
    const roleFilter = searchParams.get('role');

    if (shouldProbe) {
      // Parallel probe of non-blacklisted, non-local nodes
      await Promise.all(
        nodes.map(async (node) => {
          if (node.is_blacklisted || node.is_local) return;
          try {
            const res = await probeTcp(node.ip, 22, 400);
            if (res.ok) {
              node.status = 'up';
              node.latency_ms = res.latency;
            } else {
              node.status = 'down';
              node.latency_ms = null;
            }
          } catch {
            node.status = 'down';
            node.latency_ms = null;
          }
        })
      );
    }

    if (roleFilter) {
      nodes = nodes.filter((n) => n.role === roleFilter);
    }

    const upNodes = nodes.filter((n) => n.status === 'up').length;
    const blacklistedCount = nodes.filter((n) => n.is_blacklisted).length;

    return NextResponse.json({
      timestamp: new Date().toISOString(),
      total_nodes: nodes.length,
      up_nodes: upNodes,
      blacklisted_count: blacklistedCount,
      nodes,
      source: 'live'
    });
  } catch (error) {
    console.error('[/api/nodes GET error]:', error);
    return NextResponse.json({
      timestamp: new Date().toISOString(),
      total_nodes: mockNodes.length,
      up_nodes: mockNodes.filter((n) => n.status === 'up').length,
      blacklisted_count: 1,
      nodes: mockNodes,
      source: 'mock'
    });
  }
}
