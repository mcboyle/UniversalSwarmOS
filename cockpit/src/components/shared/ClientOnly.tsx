'use client';

import React, { useSyncExternalStore } from 'react';

const emptySubscribe = () => () => {};

export interface ClientOnlyProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * Hydration-safe boundary preventing SSR layout thrashing or timestamp mismatches.
 * Uses useSyncExternalStore to guarantee matching HTML on initial hydration.
 */
export function ClientOnly({ children, fallback = null }: ClientOnlyProps) {
  const isClient = useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false
  );

  return isClient ? <>{children}</> : <>{fallback}</>;
}
