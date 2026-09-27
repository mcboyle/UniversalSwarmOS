'use client';

import React, { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode | ((error: Error, reset: () => void) => ReactNode);
  name?: string;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    const title = this.props.fallbackTitle || this.props.name || 'Anonymous';
    console.error(`[ErrorBoundary: ${title}]`, error, errorInfo);
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render(): ReactNode {
    if (this.state.hasError && this.state.error) {
      if (typeof this.props.fallback === 'function') {
        return this.props.fallback(this.state.error, this.handleReset);
      }
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const title = this.props.fallbackTitle || (this.props.name ? `${this.props.name} Failure` : 'Component Error');

      return (
        <div className="rounded-md border border-rose-900/60 bg-rose-950/20 p-4 text-zinc-200">
          <div className="flex items-start space-x-3">
            <AlertTriangle className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-medium text-rose-300">
                {title}
              </h4>
              <p className="mt-1 text-xs font-mono text-zinc-400 break-words line-clamp-2">
                {this.state.error.message || 'An unexpected runtime error occurred.'}
              </p>
              <div className="mt-3 flex items-center space-x-2">
                <button
                  type="button"
                  onClick={this.handleReset}
                  className="inline-flex items-center space-x-1.5 rounded bg-zinc-800 px-2.5 py-1 text-xs font-medium text-zinc-100 hover:bg-zinc-700 focus:outline-none focus:ring-1 focus:ring-rose-500"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  <span>Retry Component</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
