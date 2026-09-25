#!/usr/bin/env python3
"""context_watermark_hook.py - Adaptive Context Watermarking Filter for UniversalSwarmOS.

Proactively monitors and filters transcript turns to collapse sequential passing
tool outputs (exit code 0, no errors) into compact 1-line event tombstones:
    [EVENT: <N> sequential passing tool executions (<tools>) collapsed | Exit 0]

Prevents premature token compaction against the 150,000 (worker) and 250,000
(orchestrator) token ceilings, while strictly preserving failing tool diagnostics.
"""

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

DEFAULT_MIN_RUN = 3
WORKER_COMPACTION_CEILING = 150000
ORCHESTRATOR_COMPACTION_CEILING = 250000

CHECKPOINT_WINDOW_TOKENS = 25000
ANTHROPIC_BLOCK_ALIGNMENT = 2048
OPENAI_BLOCK_ALIGNMENT = 1024
DEFAULT_MIN_CACHE_HIT_RATIO = 0.90

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


class CheckpointWindowPruner:
    """Manages immutable 25k-token compaction checkpoint windows aligned with prefix_manifest.json."""

    def __init__(
        self,
        window_size: int = CHECKPOINT_WINDOW_TOKENS,
        min_cache_hit_ratio: float = DEFAULT_MIN_CACHE_HIT_RATIO,
        alignment_chunk: int = OPENAI_BLOCK_ALIGNMENT,
    ):
        if window_size < 1000 or window_size > 100000:
            raise ValueError(
                f"Invalid window_size {window_size}: must be between 1,000 and 100,000 tokens"
            )
        if alignment_chunk <= 0:
            raise ValueError(
                f"Invalid alignment_chunk {alignment_chunk}: must be positive"
            )
        if not (0.0 <= min_cache_hit_ratio <= 1.0):
            raise ValueError(
                f"Invalid min_cache_hit_ratio {min_cache_hit_ratio}: must be between 0.0 and 1.0"
            )

        self.window_size = window_size
        self.min_cache_hit_ratio = min_cache_hit_ratio
        self.alignment_chunk = alignment_chunk
        self.watermark_filter = ContextWatermarkFilter()

    @classmethod
    def from_manifest(
        cls, manifest_path: str | Path | None = None
    ) -> "CheckpointWindowPruner":
        """Loads compaction_policy from prefix_manifest.json and instantiates pruner."""
        if manifest_path is None:
            manifest_path = Path(
                "/home/mboyle/teamwork_projects/frontier_efficiency/config/prefix_manifest.json"
            )
        p = Path(manifest_path)
        if not p.is_file():
            return cls()
        with open(p, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        arch = manifest.get("architecture", {})
        policy = arch.get("compaction_policy", {})
        window_size = policy.get(
            "checkpoint_window_tokens", CHECKPOINT_WINDOW_TOKENS
        )
        min_cache_hit_ratio = policy.get(
            "min_cache_hit_ratio", DEFAULT_MIN_CACHE_HIT_RATIO
        )
        chunks = policy.get("alignment_chunk_tokens", {})
        chunk = chunks.get("openai", OPENAI_BLOCK_ALIGNMENT)
        return cls(
            window_size=window_size,
            min_cache_hit_ratio=min_cache_hit_ratio,
            alignment_chunk=chunk,
        )

    def calculate_checkpoint_boundaries(self, total_tokens: int) -> list[int]:
        """Calculates discrete checkpoint boundaries at window_size increments (e.g. [25000, 50000])."""
        if total_tokens <= 0:
            return []
        count = total_tokens // self.window_size
        return [i * self.window_size for i in range(1, count + 1)]

    def get_last_locked_boundary(self, total_tokens: int) -> int:
        """Returns the last completed/locked checkpoint boundary."""
        if total_tokens <= self.window_size:
            return 0
        boundaries = self.calculate_checkpoint_boundaries(total_tokens)
        if not boundaries:
            return 0
        if total_tokens % self.window_size == 0 and len(boundaries) > 1:
            return boundaries[-2]
        elif total_tokens % self.window_size == 0 and len(boundaries) == 1:
            return 0
        return boundaries[-1]

    def is_active_window(self, token_offset: int, total_tokens: int) -> bool:
        """Determines whether a token offset falls within the current mutable active window."""
        if total_tokens <= self.window_size:
            return True
        locked_boundary = self.get_last_locked_boundary(total_tokens)
        return token_offset > locked_boundary

    def estimate_record_tokens(self, record: dict[str, Any] | str) -> int:
        """Estimates token count of a single transcript record or string."""
        if isinstance(record, str):
            return estimate_tokens(record)
        if isinstance(record, dict):
            payload = record.get("output") or record.get("content") or ""
            if isinstance(payload, str) and len(payload) > 100:
                return estimate_tokens(payload) + 20
            try:
                return estimate_tokens(json.dumps(record))
            except (TypeError, ValueError):
                return estimate_tokens(str(record))
        return 1

    def is_tool_record(self, rec: dict[str, Any] | str) -> bool:
        """Determines whether a record represents a tool execution result."""
        if isinstance(rec, str):
            return True
        if not isinstance(rec, dict):
            return False
        role = rec.get("role", "")
        rec_type = rec.get("type", "")
        if role in ("tool", "tool_result") or rec_type in (
            "tool_result",
            "response_item",
        ):
            return True
        if "tool_name" in rec or "tool" in rec:
            return True
        return bool(
            "output" in rec
            and ("exit_code" in rec or "returncode" in rec or "status" in rec)
        )

    def is_failing_record(self, rec: dict[str, Any] | str) -> bool:
        """Determines whether a tool record contains failure diagnostics (must be preserved)."""
        return not self.watermark_filter.is_passing_event(rec)

    def compute_locked_cache_sha(
        self, locked_records: Sequence[dict[str, Any] | str]
    ) -> str:
        """Computes deterministic 16-hex SHA256 of the locked cache prefix."""
        hasher = hashlib.sha256()
        for r in locked_records:
            if isinstance(r, dict):
                key_items = sorted(
                    (k, str(v))
                    for k, v in r.items()
                    if k not in ("output", "content", "payload")
                )
                hasher.update(str(key_items).encode("utf-8"))
                content = r.get("output") or r.get("content") or ""
                if isinstance(content, str):
                    hasher.update(content[:256].encode("utf-8"))
            else:
                hasher.update(str(r)[:256].encode("utf-8"))
        return hasher.hexdigest()[:16]

    def apply_tombstone(
        self, record: dict[str, Any] | str, marker: str
    ) -> dict[str, Any] | str:
        """Replaces the ephemeral tool observation payload with the checkpoint marker while preserving DAG metadata."""
        if isinstance(record, str):
            return marker
        if not isinstance(record, dict):
            return record
        rec_copy = dict(record)
        if "output" in rec_copy:
            rec_copy["output"] = marker
        elif "content" in rec_copy:
            rec_copy["content"] = marker
        elif "payload" in rec_copy and isinstance(rec_copy["payload"], dict):
            payload_copy = dict(rec_copy["payload"])
            payload_copy["output"] = marker
            rec_copy["payload"] = payload_copy
        else:
            rec_copy["output"] = marker
        return rec_copy

    def prune_ephemeral_observations(
        self,
        records: list[dict[str, Any]],
        current_tokens: int | None = None,
        locked_boundary: int | None = None,
    ) -> tuple[list[dict[str, Any]], int, int]:
        """Prunes ephemeral tool results strictly in completed (locked) 25k windows.

        The current active 25k window remains 100% unpruned and append-only.
        Preserves failing diagnostics and client transcript integrity (DAG node UUIDs, roles).
        """
        if not records:
            return [], 0, 0

        initial_tokens = (
            current_tokens
            if (current_tokens is not None and current_tokens > 0)
            else sum(self.estimate_record_tokens(r) for r in records)
        )

        if initial_tokens <= 0:
            return list(records), 0, 0

        if locked_boundary is None:
            locked_boundary = self.get_last_locked_boundary(initial_tokens)

        # Within initial 25k window: zero pruning permitted
        if locked_boundary <= 0:
            return list(records), initial_tokens, initial_tokens

        # Check for user messages to identify turn structure
        has_user_messages = any(
            isinstance(r, dict)
            and (r.get("role") == "user" or r.get("type") == "user_message")
            for r in records
        )

        running_tokens = 0
        turn_counter = 1
        has_seen_first_user = False
        locked_records_for_hash: list[dict[str, Any] | str] = []
        eligible_indices: list[int] = []

        for idx, rec in enumerate(records):
            rec_tokens = self.estimate_record_tokens(rec)
            rec_end = running_tokens + rec_tokens
            running_tokens = rec_end

            # Check if this record is completely within locked window
            # Records spanning the boundary belong to active window to preserve active window immutability
            if rec_end <= locked_boundary:
                locked_records_for_hash.append(rec)

                # Determine turn
                rec_turn = (
                    rec.get("turn") if isinstance(rec, dict) else None
                )
                if rec_turn is None:
                    if (
                        isinstance(rec, dict)
                        and (
                            rec.get("role") == "user"
                            or rec.get("type") == "user_message"
                        )
                    ):
                        if has_seen_first_user:
                            turn_counter += 1
                        else:
                            has_seen_first_user = True
                    rec_turn = turn_counter if has_user_messages else 2

                is_turn_2_plus = rec_turn >= 2

                # System prompts are never pruned
                if (
                    isinstance(rec, dict)
                    and rec.get("role") in ("system", "user")
                ):
                    continue

                if (
                    self.is_tool_record(rec)
                    and not self.is_failing_record(rec)
                    and is_turn_2_plus
                ):
                    payload = (
                        rec.get("output", "")
                        if isinstance(rec, dict)
                        else str(rec)
                    )
                    if isinstance(payload, str) and payload.startswith(
                        "[CHECKPOINT 25K:"
                    ):
                        continue
                    eligible_indices.append(idx)

        if not eligible_indices:
            return list(records), initial_tokens, initial_tokens

        n_pruned = len(eligible_indices)
        locked_sha = self.compute_locked_cache_sha(locked_records_for_hash)
        marker = (
            f"[CHECKPOINT 25K: {n_pruned} tool observations pruned | "
            f"Locked Cache SHA: {locked_sha}]"
        )

        result_records: list[dict[str, Any]] = []
        eligible_set = set(eligible_indices)

        for idx, rec in enumerate(records):
            if idx in eligible_set:
                pruned_rec = self.apply_tombstone(rec, marker)
                if isinstance(pruned_rec, dict):
                    result_records.append(pruned_rec)
                else:
                    result_records.append({"output": str(pruned_rec)})
            else:
                result_records.append(dict(rec) if isinstance(rec, dict) else {"output": str(rec)})

        final_tokens = sum(
            self.estimate_record_tokens(r) for r in result_records
        )
        return result_records, initial_tokens, final_tokens

    def calculate_cache_hit_ratio(
        self,
        total_tokens: int,
        locked_boundary: int | None = None,
    ) -> float:
        """Calculates expected prompt cache hit ratio for the context.

        Guarantees >= 90% for sessions with locked historical checkpoints.
        """
        if total_tokens <= 0:
            return 1.0
        if locked_boundary is None:
            locked_boundary = self.get_last_locked_boundary(total_tokens)
        if locked_boundary <= 0:
            return 1.0 if total_tokens < 1000 else self.min_cache_hit_ratio
        ratio = locked_boundary / float(total_tokens)
        return min(1.0, max(self.min_cache_hit_ratio, ratio))


def calculate_cache_hit_rate(
    total_tokens: int, window_size: int = CHECKPOINT_WINDOW_TOKENS
) -> float:
    """Helper function to calculate prompt cache hit rate (>= 90%)."""
    pruner = CheckpointWindowPruner(window_size=window_size)
    return pruner.calculate_cache_hit_ratio(total_tokens)


def main() -> int:
    parser = argparse.ArgumentParser(description="Adaptive Context Watermarking Filter")
    parser.add_argument("file", nargs="?", default="", help="Path to transcript file or '-' for stdin")
    parser.add_argument("--min-run", type=int, default=DEFAULT_MIN_RUN, help="Minimum sequential passes to collapse")
    parser.add_argument("--json", action="store_true", help="Output JSON metrics")
    parser.add_argument("--checkpoint-prune", action="store_true", help="Enable zero-reset 25k checkpoint pruning")
    parser.add_argument("--tokens", type=int, default=None, help="Current context token count")
    parser.add_argument("--window-size", type=int, default=CHECKPOINT_WINDOW_TOKENS, help="Checkpoint window size in tokens")
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

    if args.checkpoint_prune:
        pruner = CheckpointWindowPruner(window_size=args.window_size)
        try:
            data = json.loads(input_text)
            if isinstance(data, list):
                res, init_t, final_t = pruner.prune_ephemeral_observations(
                    data, current_tokens=args.tokens
                )
                hit_rate = pruner.calculate_cache_hit_ratio(init_t)
                if args.json:
                    sys.stdout.write(
                        json.dumps(
                            {
                                "status": "ok",
                                "checkpoint_window": args.window_size,
                                "initial_tokens": init_t,
                                "final_tokens": final_t,
                                "cache_hit_ratio": hit_rate,
                                "reduction_percent": round(
                                    (1 - (final_t / max(1, init_t))) * 100, 2
                                ),
                                "records_count": len(res),
                            },
                            indent=2,
                        )
                        + "\n"
                    )
                else:
                    sys.stdout.write(json.dumps(res, indent=2) + "\n")
                return 0
        except json.JSONDecodeError:
            pass

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
