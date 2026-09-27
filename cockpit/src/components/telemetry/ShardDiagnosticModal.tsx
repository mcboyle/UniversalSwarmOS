"use client";

import React, { useState } from 'react';
import type { CiShardStatus } from '@/lib/types';
import { X, Copy, Check, Terminal, BookOpen, AlertOctagon } from 'lucide-react';

interface ShardDiagnosticModalProps {
  shard: CiShardStatus;
  onClose: () => void;
}

const TAXONOMY_MAP: Record<string, {
  name: string;
  rule: string;
  signature: string;
  cause: string;
  command: string;
}> = {
  'BD-CI-01': {
    name: 'Hermetic Git Committer Identity',
    rule: 'FLEET_RULE 41',
    signature: 'fatal: empty ident name (for <runner@...>) not allowed (Exit 128)',
    cause: 'git commit invoked on ephemeral CI runner without explicit -c user.name flags.',
    command: 'python3 toolchain/bin/bd-git-hermetic-check <file.py>'
  },
  'BD-CI-02': {
    name: 'AST / Token Parse Bottlenecks & Static Sweep False Positives',
    rule: 'FLEET_RULE 42',
    signature: 'TimeoutExpired (>900s) or runner import hazard detected',
    cause: 'Full-repo AST scanning over 2,100+ files without substring pre-filters.',
    command: 'venv/bin/python -m pytest <test_file.py> --durations=10'
  },
  'BD-CI-03': {
    name: 'Subshell, Socket, Process Tree & Descriptor Leaks',
    rule: 'FLEET_RULE 45',
    signature: 'Playwright Sync API inside asyncio loop / Too many open files',
    cause: 'Unclosed browser contexts or orphan background processes surviving test failure.',
    command: 'venv/bin/python -m pytest tests/test_row816_astra_teardown.py -q'
  },
  'BD-CI-04': {
    name: 'Fixture Contamination & Shared Globals',
    rule: 'FLEET_RULE 47',
    signature: 'sites configuration path changed after runtime activation',
    cause: 'Module globals (_SITE_RUNTIME_*) leaked across test boundaries without teardown.',
    command: 'git status --porcelain'
  },
  'BD-CI-05': {
    name: 'Asynchronous Marker File Synchronization Races',
    rule: 'FLEET_RULE 44',
    signature: "ValueError: invalid literal for int() with base 10: ''",
    cause: 'Parent thread read 0-byte marker file before worker process flushed buffered child PID.',
    command: 'venv/bin/python -m pytest tests/test_marker_atomic.py -q'
  },
  'BD-CI-06': {
    name: 'CI Matrix Shard Environment & Capability Mismatches',
    rule: 'FLEET_RULE 46',
    signature: "Failed: chromium not launchable here: Executable doesn't exist",
    cause: 'Browser-dependent test placed on pure-Python shard lacking Chromium binaries.',
    command: 'venv/bin/python -m pytest tests/test_v3_66_939_ci_gate_shards_cover_every_gate.py -q'
  },
  'BD-CI-07': {
    name: 'Generated Artifact Drift & In-Sync Gate Violations',
    rule: 'FLEET_RULE 47',
    signature: 'AssertionError: FUNCTION_INDEX.md is out of sync with source',
    cause: 'Source code modified without running deterministic generator cascade.',
    command: 'venv/bin/python toolchain/bin/bd-regen-order --work "$PWD"'
  },
  'BD-CI-08': {
    name: 'Call-Phase Test Symbol Resolution',
    rule: 'FLEET_RULE 44',
    signature: 'ERROR collecting tests/test_*.py: ModuleNotFoundError (exit 2)',
    cause: 'Top-level imports of unmerged symbols aborting collection on clean base tree.',
    command: 'venv/bin/python -m pytest tests/test_behavioral_red.py -q'
  },
  'BD-CI-09': {
    name: 'Child Process Inline Script String Literal Escaping',
    rule: 'Subprocess Invariant',
    signature: 'SyntaxError: unterminated string literal (detected at line N)',
    cause: 'Unescaped raw newline in multi-line python -c string literal.',
    command: 'python3 -c "import ast; ast.parse(r\'\'\'ready\\n\'\'\')"'
  }
};

export function ShardDiagnosticModal({ shard, onClose }: ShardDiagnosticModalProps) {
  const [copied, setCopied] = useState(false);

  // Infer taxonomy code or default to BD-CI-06 if browser-related
  const code = shard.error_class || (shard.name.includes('vitest') ? 'BD-CI-06' : 'BD-CI-07');
  const details = TAXONOMY_MAP[code] || TAXONOMY_MAP['BD-CI-06'];

  const copyCommand = () => {
    navigator.clipboard.writeText(details.command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-xl rounded-lg bg-zinc-950 border border-zinc-800 shadow-2xl p-5 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <div className="flex items-center space-x-2">
            <AlertOctagon className="w-5 h-5 text-rose-400" />
            <h3 className="text-sm font-semibold text-zinc-100">
              CI Shard Diagnostic: {shard.name}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Taxonomy Metadata */}
        <div className="grid grid-cols-2 gap-3 text-xs font-mono">
          <div className="p-2.5 rounded bg-zinc-900 border border-zinc-800">
            <span className="text-zinc-500 block text-[10px]">TAXONOMY CLASS</span>
            <span className="text-rose-400 font-bold">{code}: {details.name}</span>
          </div>
          <div className="p-2.5 rounded bg-zinc-900 border border-zinc-800">
            <span className="text-zinc-500 block text-[10px]">GOVERNING RULE</span>
            <span className="text-cyan-400 font-bold">{details.rule}</span>
          </div>
        </div>

        {/* Signature Box */}
        <div className="p-3 rounded bg-zinc-900/90 border border-zinc-800 space-y-1">
          <div className="flex items-center text-xs font-semibold text-zinc-300">
            <Terminal className="w-3.5 h-3.5 mr-1.5 text-zinc-400" />
            Observed Error Signature
          </div>
          <pre className="text-[11px] font-mono text-rose-300 whitespace-pre-wrap break-all bg-black/40 p-2 rounded border border-zinc-900">
            {shard.error_summary || details.signature}
          </pre>
        </div>

        {/* Mechanism */}
        <div className="p-3 rounded bg-zinc-900 border border-zinc-800 space-y-1">
          <div className="flex items-center text-xs font-semibold text-zinc-300">
            <BookOpen className="w-3.5 h-3.5 mr-1.5 text-zinc-400" />
            Root Cause Mechanism
          </div>
          <p className="text-xs text-zinc-400 leading-relaxed">
            {details.cause}
          </p>
        </div>

        {/* Remediation Command */}
        <div className="p-3 rounded bg-zinc-900 border border-zinc-800 space-y-2">
          <div className="text-xs font-semibold text-zinc-300">
            Remediation Playbook Command
          </div>
          <div className="flex items-center justify-between p-2 rounded bg-black/60 border border-zinc-800 font-mono text-xs text-emerald-400">
            <code className="truncate mr-2">{details.command}</code>
            <button
              type="button"
              onClick={copyCommand}
              className="inline-flex items-center px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition-colors shrink-0"
            >
              {copied ? <Check className="w-3.5 h-3.5 mr-1" /> : <Copy className="w-3.5 h-3.5 mr-1" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end pt-2 border-t border-zinc-800">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded text-xs font-mono bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition-colors"
          >
            Dismiss Diagnostic
          </button>
        </div>
      </div>
    </div>
  );
}
