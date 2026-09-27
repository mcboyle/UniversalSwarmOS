'use client';

import React from 'react';
import { cn } from '@/lib/utils';

export type StatusVariant =
  | 'pass'
  | 'online'
  | 'ok'
  | 'up'
  | 'success'
  | 'warn'
  | 'off-pace'
  | 'flaky'
  | 'fail'
  | 'offline'
  | 'down'
  | 'critical'
  | 'running'
  | 'dispatched'
  | 'started'
  | 'idle'
  | 'queued'
  | 'isolated'
  | 'unknown';

export interface StatusBadgeProps {
  status: string;
  label?: string;
  size?: 'sm' | 'md';
  dot?: boolean;
  pulse?: boolean;
  className?: string;
}

function resolveVariant(status: string): {
  badgeClass: string;
  dotClass: string;
  defaultPulse: boolean;
} {
  const s = status.toLowerCase();

  switch (s) {
    case 'pass':
    case 'online':
    case 'ok':
    case 'up':
    case 'success':
      return {
        badgeClass: 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60',
        dotClass: 'bg-emerald-400',
        defaultPulse: false,
      };
    case 'warn':
    case 'off-pace':
    case 'flaky':
    case 'operator-only':
      return {
        badgeClass: 'bg-amber-950/40 text-amber-400 border-amber-800/60',
        dotClass: 'bg-amber-400',
        defaultPulse: false,
      };
    case 'fail':
    case 'offline':
    case 'down':
    case 'critical':
    case 'failure':
    case 'aborted':
      return {
        badgeClass: 'bg-rose-950/40 text-rose-400 border-rose-800/60',
        dotClass: 'bg-rose-400',
        defaultPulse: false,
      };
    case 'running':
    case 'dispatched':
    case 'started':
      return {
        badgeClass: 'bg-blue-950/40 text-blue-400 border-blue-800/60',
        dotClass: 'bg-blue-400',
        defaultPulse: true,
      };
    case 'idle':
    case 'queued':
    case 'isolated':
    case 'unknown':
    default:
      return {
        badgeClass: 'bg-zinc-900/80 text-zinc-400 border-zinc-700/60',
        dotClass: 'bg-zinc-500',
        defaultPulse: false,
      };
  }
}

export function StatusBadge({
  status,
  label,
  size = 'sm',
  dot = true,
  pulse,
  className,
}: StatusBadgeProps) {
  const { badgeClass, dotClass, defaultPulse } = resolveVariant(status);
  const shouldPulse = pulse ?? defaultPulse;

  const sizeClass = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs';

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded border font-mono font-medium uppercase tracking-wider',
        sizeClass,
        badgeClass,
        className
      )}
    >
      {dot && (
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full shrink-0',
            dotClass,
            shouldPulse && 'animate-pulse'
          )}
        />
      )}
      <span>{label || status}</span>
    </span>
  );
}
