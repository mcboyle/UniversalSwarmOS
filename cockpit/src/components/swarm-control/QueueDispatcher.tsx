"use client";

import React, { useState, useEffect, useMemo, useRef } from 'react';
import type { QueueItem } from '@/lib/types';
import { SortableQueueTable } from './SortableQueueTable';
import { ListOrdered, Search } from 'lucide-react';
import { toast } from 'sonner';

interface QueueDispatcherProps {
  initialItems: QueueItem[];
  isLoading: boolean;
  onQueueUpdated: () => void;
}

export function QueueDispatcher({
  initialItems,
  onQueueUpdated
}: QueueDispatcherProps) {
  const [items, setItems] = useState<QueueItem[]>(initialItems);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'completed'>('active');
  const [isMutating, setIsMutating] = useState<boolean>(false);

  // Snapshot ref for rollback on 409 conflict
  const previousItemsRef = useRef<QueueItem[]>(initialItems);

  // Synchronize when server poll arrives, but only if not currently mutating
  useEffect(() => {
    if (!isMutating) {
      setItems(initialItems);
      previousItemsRef.current = initialItems;
    }
  }, [initialItems, isMutating]);

  // Filter items based on active tabs & search query
  const filteredItems = useMemo(() => {
    return items.filter(item => {
      if (statusFilter === 'active' && !item.is_active) return false;
      if (statusFilter === 'completed' && item.is_active) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          item.row.toLowerCase().includes(q) ||
          item.seat.toLowerCase().includes(q) ||
          item.status.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [items, statusFilter, searchQuery]);

  // Handle Optimistic Reorder with 409 Conflict Rollback
  const handleReorder = async (newOrderedItems: QueueItem[]) => {
    // 1. Take snapshot
    previousItemsRef.current = items;

    // 2. Optimistic local update
    setItems(newOrderedItems);
    setIsMutating(true);

    // 3. Extract ordered task slugs
    const ordered_row_ids = newOrderedItems.map(i => i.row);

    try {
      const res = await fetch('/api/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'reorder', ordered_row_ids })
      });

      if (res.status === 409) {
        // HTTP 409 CONFLICT: Rollback state immediately
        const errorData = await res.json().catch(() => ({}));
        setItems(previousItemsRef.current);
        toast.error(`Concurrency Conflict: ${errorData.details || 'Ledger locked. Rolling back order.'}`);
        onQueueUpdated();
        return;
      }

      if (!res.ok) {
        throw new Error(`Failed with HTTP ${res.status}`);
      }

      toast.success('Queue reordered successfully with zero torn reads.');
      onQueueUpdated();
    } catch (err: any) {
      // Network or 500 error: Rollback
      setItems(previousItemsRef.current);
      toast.error(`Reorder failed: ${err.message || 'Unknown error'}. Reverting to previous state.`);
      onQueueUpdated();
    } finally {
      setIsMutating(false);
    }
  };

  // Handle drag reordering of filtered items: maps newFiltered back into items preserving non-filtered items
  const handleDragReorder = (newFiltered: QueueItem[]) => {
    if (newFiltered.length === items.length) {
      handleReorder(newFiltered);
      return;
    }
    const filteredSlugs = new Set(filteredItems.map(i => i.row));
    const newItems: QueueItem[] = [];
    let filteredIdx = 0;
    for (const item of items) {
      if (filteredSlugs.has(item.row)) {
        if (filteredIdx < newFiltered.length) {
          newItems.push(newFiltered[filteredIdx++]);
        } else {
          newItems.push(item);
        }
      } else {
        newItems.push(item);
      }
    }
    handleReorder(newItems);
  };

  // Keyboard / Button actuation for Move to Top
  const handleMoveToTop = (index: number) => {
    if (index <= 0 || index >= filteredItems.length) return;
    const targetItem = filteredItems[index];
    if (!targetItem || !items.some(i => i.row === targetItem.row)) return;

    const remaining = items.filter(i => i.row !== targetItem.row);
    const newItems = [targetItem, ...remaining];
    handleReorder(newItems);
  };

  // Keyboard / Button actuation for Up
  const handleMoveUp = (index: number) => {
    if (index <= 0 || index >= filteredItems.length) return;
    const targetItem = filteredItems[index];
    const prevItem = filteredItems[index - 1];
    if (!targetItem || !prevItem) return;

    const newItems = [...items];
    const targetFullIdx = newItems.findIndex(i => i.row === targetItem.row);
    const prevFullIdx = newItems.findIndex(i => i.row === prevItem.row);
    if (targetFullIdx === -1 || prevFullIdx === -1) return;

    newItems[targetFullIdx] = prevItem;
    newItems[prevFullIdx] = targetItem;
    handleReorder(newItems);
  };

  // Keyboard / Button actuation for Down
  const handleMoveDown = (index: number) => {
    if (index < 0 || index >= filteredItems.length - 1) return;
    const targetItem = filteredItems[index];
    const nextItem = filteredItems[index + 1];
    if (!targetItem || !nextItem) return;

    const newItems = [...items];
    const targetFullIdx = newItems.findIndex(i => i.row === targetItem.row);
    const nextFullIdx = newItems.findIndex(i => i.row === nextItem.row);
    if (targetFullIdx === -1 || nextFullIdx === -1) return;

    newItems[targetFullIdx] = nextItem;
    newItems[nextFullIdx] = targetItem;
    handleReorder(newItems);
  };

  return (
    <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 flex flex-col h-[640px]">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-zinc-800">
        <div className="flex items-center space-x-2">
          <ListOrdered className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold text-zinc-100">
            DISPATCH-LEDGER.tsv Queue Re-order
          </h3>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <button
            type="button"
            onClick={() => {
              const active = items.filter(i => i.is_active);
              const inactive = items.filter(i => !i.is_active);
              const reordered = [...active, ...inactive];
              handleReorder(reordered);
            }}
            disabled={isMutating}
            className="px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-emerald-400 border border-zinc-700 text-[11px] transition-colors disabled:opacity-50"
            title="Sort active tasks to the top of ledger"
          >
            Prioritize Active
          </button>
          <span className="text-zinc-600">|</span>
          <span className="text-zinc-400">Total:</span>
          <span className="text-zinc-200 font-bold">{items.length}</span>
          <span className="text-zinc-600">|</span>
          <span className="text-emerald-400 font-bold">
            {items.filter(i => i.is_active).length} Active
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 py-3">
        {/* Status filter tabs */}
        <div className="flex items-center space-x-1">
          {(['active', 'completed', 'all'] as const).map(tab => (
            <button
              key={tab}
              type="button"
              onClick={() => setStatusFilter(tab)}
              className={`px-2.5 py-1 rounded text-xs font-mono capitalize transition-colors ${
                statusFilter === tab
                  ? 'bg-zinc-700 text-zinc-100 font-bold border border-zinc-600'
                  : 'bg-zinc-800/80 text-zinc-400 hover:bg-zinc-800 border border-zinc-800'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative w-48 sm:w-64">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-zinc-500" />
          <input
            type="text"
            placeholder="Search task slug or seat..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1 rounded bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
          />
        </div>
      </div>

      {/* Sortable Table Container */}
      <div className="flex-1 overflow-y-auto">
        <SortableQueueTable
          items={filteredItems}
          isMutating={isMutating}
          onReorder={handleDragReorder}
          onMoveUp={handleMoveUp}
          onMoveDown={handleMoveDown}
          onMoveToTop={handleMoveToTop}
        />
      </div>
    </div>
  );
}
