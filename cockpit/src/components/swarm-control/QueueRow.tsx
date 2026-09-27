"use client";

import React from 'react';
import type { QueueItem } from '@/lib/types';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, ArrowUp, ArrowDown, ChevronsUp } from 'lucide-react';

interface QueueRowProps {
  item: QueueItem;
  rank: number;
  isFirst: boolean;
  isLast: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onMoveToTop?: () => void;
}

export function QueueRow({
  item,
  rank,
  isFirst,
  isLast,
  onMoveUp,
  onMoveDown,
  onMoveToTop
}: QueueRowProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: item.row });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition
  };

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'started') {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-blue-950/80 text-blue-400 border border-blue-800">
          started
        </span>
      );
    }
    if (s === 'dispatched') {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-emerald-950/80 text-emerald-400 border border-emerald-800">
          dispatched
        </span>
      );
    }
    if (s === 'done') {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-zinc-800 text-zinc-400 border border-zinc-700">
          done
        </span>
      );
    }
    if (s.startsWith('nudge')) {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-amber-950/80 text-amber-400 border border-amber-800">
          {s}
        </span>
      );
    }
    return (
      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-zinc-800 text-zinc-400 border border-zinc-700">
        {s}
      </span>
    );
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center justify-between p-2 rounded border font-mono text-xs transition-colors ${
        isDragging
          ? 'z-50 bg-zinc-900 border-cyan-500 shadow-xl opacity-90'
          : 'bg-zinc-950/70 border-zinc-800/80 hover:border-zinc-700'
      }`}
    >
      {/* Left: Drag Handle, Rank, and Slug */}
      <div className="flex items-center space-x-2 truncate mr-2">
        <button
          type="button"
          {...attributes}
          {...listeners}
          className="cursor-grab active:cursor-grabbing p-1 text-zinc-500 hover:text-zinc-200 transition-colors"
          title="Drag to reorder"
        >
          <GripVertical className="w-3.5 h-3.5" />
        </button>

        <span className="text-[11px] font-bold text-zinc-500 w-6 text-center">
          #{rank}
        </span>

        <span className="font-semibold text-zinc-100 truncate">
          {item.row}
        </span>
      </div>

      {/* Middle: Assigned Seat & Status */}
      <div className="flex items-center space-x-3 shrink-0 mr-2">
        <span className="text-zinc-400 text-[11px] truncate max-w-[130px]">
          {item.seat}
        </span>
        {getStatusBadge(item.status)}
      </div>

      {/* Right: Up / Down / Top Buttons */}
      <div className="flex items-center space-x-1 shrink-0">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onMoveToTop?.();
          }}
          onPointerDown={(e) => e.stopPropagation()}
          disabled={isFirst}
          className="p-1 rounded bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-emerald-400 disabled:opacity-30 disabled:pointer-events-none transition-colors border border-zinc-800"
          title="Promote to Top of Queue"
        >
          <ChevronsUp className="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onMoveUp();
          }}
          onPointerDown={(e) => e.stopPropagation()}
          disabled={isFirst}
          className="p-1 rounded bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 disabled:opacity-30 disabled:pointer-events-none transition-colors border border-zinc-800"
          title="Move Priority Up"
        >
          <ArrowUp className="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onMoveDown();
          }}
          onPointerDown={(e) => e.stopPropagation()}
          disabled={isLast}
          className="p-1 rounded bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 disabled:opacity-30 disabled:pointer-events-none transition-colors border border-zinc-800"
          title="Move Priority Down"
        >
          <ArrowDown className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
