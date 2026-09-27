"use client";

import React from 'react';
import type { QueueItem } from '@/lib/types';
import { QueueRow } from './QueueRow';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy
} from '@dnd-kit/sortable';

interface SortableQueueTableProps {
  items: QueueItem[];
  isMutating: boolean;
  onReorder: (newItems: QueueItem[]) => void;
  onMoveUp: (index: number) => void;
  onMoveDown: (index: number) => void;
  onMoveToTop?: (index: number) => void;
}

export function SortableQueueTable({
  items,
  onReorder,
  onMoveUp,
  onMoveDown,
  onMoveToTop
}: SortableQueueTableProps) {
  // Sensor configuration: 5px distance constraint to prevent button click captures
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 }
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = items.findIndex(i => i.row === active.id);
    const newIndex = items.findIndex(i => i.row === over.id);

    if (oldIndex !== -1 && newIndex !== -1) {
      const reordered = arrayMove(items, oldIndex, newIndex);
      onReorder(reordered);
    }
  };

  if (items.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-xs font-mono text-zinc-500 border border-dashed border-zinc-800 rounded">
        No matching queue entries found.
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={items.map(i => i.row)}
        strategy={verticalListSortingStrategy}
      >
        <div className="space-y-1.5">
          {items.map((item, index) => (
            <QueueRow
              key={item.row}
              item={item}
              rank={index + 1}
              isFirst={index === 0}
              isLast={index === items.length - 1}
              onMoveUp={() => onMoveUp(index)}
              onMoveDown={() => onMoveDown(index)}
              onMoveToTop={() => onMoveToTop?.(index)}
            />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}
