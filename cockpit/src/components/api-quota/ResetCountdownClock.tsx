"use client";

import React, { useState, useEffect } from 'react';
import { Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ResetCountdownClockProps {
  resetsAt: string | null | undefined;
  className?: string;
}

export function ResetCountdownClock({ resetsAt, className }: ResetCountdownClockProps) {
  const [mounted, setMounted] = useState<boolean>(false);
  const [timeRemaining, setTimeRemaining] = useState<string>('');
  const [isImminent, setIsImminent] = useState<boolean>(false);

  useEffect(() => {
    setMounted(true);

    if (!resetsAt || resetsAt === '-' || resetsAt === 'null') {
      setTimeRemaining('Rolling 5h');
      return;
    }

    const calculateTime = () => {
      const target = new Date(resetsAt).getTime();
      const now = Date.now();
      const diff = target - now;

      if (isNaN(target)) {
        setTimeRemaining('Rolling 5h');
        setIsImminent(false);
        return;
      }

      if (diff <= 0) {
        setTimeRemaining('Reset imminent');
        setIsImminent(true);
        return;
      }

      setIsImminent(false);
      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);

      const hStr = String(hours).padStart(2, '0');
      const mStr = String(minutes).padStart(2, '0');
      const sStr = String(seconds).padStart(2, '0');

      setTimeRemaining(`In ${hStr}h ${mStr}m ${sStr}s`);
    };

    calculateTime();
    const interval = setInterval(calculateTime, 1000);
    return () => clearInterval(interval);
  }, [resetsAt]);

  // Server-side fallback / pre-hydration state: deterministic render
  if (!mounted) {
    return (
      <span className={cn("inline-flex items-center space-x-1 font-mono text-[11px] text-zinc-400", className)}>
        <Clock className="w-3 h-3 text-zinc-500" />
        <span>Rolling 5h</span>
      </span>
    );
  }

  return (
    <span className={cn(
      "inline-flex items-center space-x-1 font-mono text-[11px]",
      isImminent ? "text-emerald-400 font-bold animate-pulse" : "text-zinc-300",
      className
    )}>
      <Clock className={cn("w-3 h-3", isImminent ? "text-emerald-400" : "text-zinc-500")} />
      <span>{timeRemaining}</span>
    </span>
  );
}
