#!/usr/bin/env python3
"""context_watermark_hook.py - Adaptive Context Watermarking Filter for UniversalSwarmOS.

Proactively monitors and filters transcript turns to collapse sequential passing
tool outputs (exit code 0, no errors) into compact 1-line event tombstones:
    [EVENT: <N> sequential passing tool executions (<tools>) collapsed | Exit 0]

Prevents premature token compaction against the 150,000 (worker) and 250,000
(orchestrator) token ceilings, while strictly preserving failing tool diagnostics.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

DEFAULT_MIN_RUN = 3
WORKER_COMPACTION_CEILING = 150000
ORCHESTRATOR_COMPACTION_CEILING = 250000

ERROR_PATTERNS = [
    re.compile(r"\b(AssertionError|Traceback|SyntaxError|TypeError|ValueError|KeyError|IndexError)\b"),
    re.compile(r"\b(FAIL|FAILED|FATAL|CRITICAL)\b"),
    re.compile(r"\b(exit (?:code )?[1-9]\d*|returncode=[1-9]\d*)\b"),
]


def estimate_tokens(text: str) -> int:
    """Estimates tokens based on character count (~4 chars per token)."""
    return max(1, len(text) // 4)


class ContextWatermarkFilter:
    """Filter engine that identifies and collapses runs of passing tool outputs."""

    def __init__(
        self,
        min_run: int = DEFAULT_MIN_RUN,
        worker_ceiling: int = WORKER_COMPACTION_CEILING,
        orchestrator_ceiling: int = ORCHESTRATOR_COMPACTION_CEILING,
    ):
        self.min_run = min_run
        self.worker_ceiling = worker_ceiling
        self.orchestrator_ceiling = orchestrator_ceiling

    def is_passing_event(self, event: dict[str, Any] | str) -> bool:
        """Determines whether a tool execution event was successful (Exit 0, no errors)."""
        if isinstance(event, str):
            for pat in ERROR_PATTERNS:
                if pat.search(event):
                    return False
            return True

        if not isinstance(event, dict):
            return False

        # Explicit exit code check
        exit_code = event.get("exit_code")
        if exit_code is not None and exit_code != 0:
            return False

        returncode = event.get("returncode")
        if returncode is not None and returncode != 0:
            return False

        if event.get("is_error") is True:
            return False

        status = str(event.get("status", "")).lower()
        if status in ("fail", "failed", "error", "syntax_error"):
            return False

        output = event.get("output") or event.get("content") or ""
        if isinstance(output, list):
            output = "\n".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in output
            )
        elif not isinstance(output, str):
            output = str(output)

        for pat in ERROR_PATTERNS:
            if pat.search(output):
                return False

        return True

    def collapse_events(
        self, events: Sequence[dict[str, Any] | str]
    ) -> list[dict[str, Any] | str]:
        """Collapses consecutive passing tool executions into 1-line event tombstones."""
        collapsed: list[dict[str, Any] | str] = []
        passing_streak: list[dict[str, Any] | str] = []

        def flush_streak():
            nonlocal passing_streak, collapsed
            if not passing_streak:
                return

            if len(passing_streak) >= self.min_run:
                tools_list = []
                for e in passing_streak:
                    if isinstance(e, dict):
                        tname = e.get("tool") or e.get("name") or e.get("tool_name")
                        if tname:
                            tools_list.append(str(tname))
                    elif isinstance(e, str):
                        match = re.search(r"^\s*([a-zA-Z0-9_\-\.]+)", e)
                        if match:
                            tools_list.append(match.group(1))

                tool_summary = ", ".join(dict.fromkeys(tools_list))
                if tool_summary:
                    tombstone = f"[EVENT: {len(passing_streak)} sequential passing tool executions ({tool_summary}) collapsed | Exit 0]"
                else:
                    tombstone = f"[EVENT: {len(passing_streak)} sequential passing tool executions collapsed | Exit 0]"

                collapsed.append(tombstone)
            else:
                for item in passing_streak:
                    collapsed.append(item["output"] if isinstance(item, dict) and "output" in item else item)

            passing_streak = []

        for ev in events:
            if self.is_passing_event(ev):
                passing_streak.append(ev)
            else:
                flush_streak()
                collapsed.append(ev["output"] if isinstance(ev, dict) and "output" in ev else ev)

        flush_streak()
        return collapsed

    def filter_transcript_records(
        self, records: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], int, int]:
        """Processes structured transcript records, tombstoning runs of successful tool results."""
        initial_tokens = estimate_tokens(json.dumps(records))

        filtered_records: list[dict[str, Any]] = []
        streak_nodes: list[dict[str, Any]] = []

        def flush_record_streak():
            nonlocal streak_nodes, filtered_records
            if not streak_nodes:
                return

            if len(streak_nodes) >= self.min_run:
                tools = []
                for n in streak_nodes:
                    name = n.get("tool_name") or n.get("name") or "tool"
                    tools.append(name)
                summary = ", ".join(dict.fromkeys(tools))
                tombstone = f"[EVENT: {len(streak_nodes)} sequential passing tool executions ({summary}) collapsed | Exit 0]"

                first = dict(streak_nodes[0])
                if "content" in first:
                    first["content"] = tombstone
                elif "payload" in first and isinstance(first["payload"], dict):
                    first["payload"]["output"] = tombstone
                elif "output" in first:
                    first["output"] = tombstone
                filtered_records.append(first)
            else:
                filtered_records.extend(streak_nodes)

            streak_nodes = []

        for rec in records:
            # Check if this record is a tool result
            is_tool = False
            rec_type = rec.get("type", "")
            role = rec.get("role", "")

            if role in ("tool", "tool_result") or rec_type in ("tool_result", "response_item"):
                is_tool = True

            if is_tool and self.is_passing_event(rec):
                streak_nodes.append(rec)
            else:
                flush_record_streak()
                filtered_records.append(rec)

        flush_record_streak()

        final_tokens = estimate_tokens(json.dumps(filtered_records))
        return filtered_records, initial_tokens, final_tokens


def main() -> int:
    parser = argparse.ArgumentParser(description="Adaptive Context Watermarking Filter")
    parser.add_argument("file", nargs="?", default="", help="Path to transcript file or '-' for stdin")
    parser.add_argument("--min-run", type=int, default=DEFAULT_MIN_RUN, help="Minimum sequential passes to collapse")
    parser.add_argument("--json", action="store_true", help="Output JSON metrics")
    args = parser.parse_args()

    input_text = ""
    if args.file and args.file != "-":
        p = Path(args.file)
        if not p.is_file():
            sys.stderr.write(f"Error: File not found: {args.file}\n")
            return 1
        input_text = p.read_text(encoding="utf-8")
    else:
        if not sys.stdin.isatty():
            input_text = sys.stdin.read()
        else:
            parser.print_help(sys.stderr)
            return 0

    filter_engine = ContextWatermarkFilter(min_run=args.min_run)

    # Check if input is JSON or lines of text
    try:
        data = json.loads(input_text)
        if isinstance(data, list):
            res, init_t, final_t = filter_engine.filter_transcript_records(data)
            if args.json:
                sys.stdout.write(json.dumps({
                    "status": "ok",
                    "initial_tokens": init_t,
                    "final_tokens": final_t,
                    "reduction_percent": round((1 - (final_t / max(1, init_t))) * 100, 2),
                    "records_count": len(res),
                }, indent=2) + "\n")
            else:
                sys.stdout.write(json.dumps(res, indent=2) + "\n")
            return 0
    except json.JSONDecodeError:
        pass

    # Process line-based events
    lines = [line.strip() for line in input_text.splitlines() if line.strip()]
    collapsed = filter_engine.collapse_events(lines)
    for line in collapsed:
        sys.stdout.write(str(line) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
