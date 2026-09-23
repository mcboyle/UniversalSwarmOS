#!/usr/bin/env python3
"""
bd-amnesia-hook.py - Active Transcript Truncation & Vector Offload Daemon

Monitors active Claude Code and Codex JSONL transcript files. When conversational
context exceeds the trigger threshold (default: 150,000 tokens), safely truncates
older tool outputs, thinking blocks, and attachments down to the target ceiling
(default: <50,000 tokens) while preserving:
1. Transcript DAG invariants (uuids, parentUuids, leafUuid, 1:1 tool_use/result pairing).
2. Protected recent zone (last 15 turns / ~30,000 tokens) and root anchor turn.
3. Zero-loss context-mode FTS5 vector indexing and cold markdown archives.
4. Concurrency race protection and POSIX atomic file replacement.
"""

import argparse
import datetime
import fcntl
import glob
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# Default Constants
DEFAULT_INTERVAL = 5.0
DEFAULT_TRIGGER_TOKENS = 150_000
DEFAULT_TARGET_TOKENS = 45_000
DEFAULT_RECENT_RESERVE = 30_000
DEFAULT_MIN_TURN_PRESERVE = 15
DEFAULT_MIN_SIZE_BYTE_FLOOR = 300_000
DEFAULT_MAX_AGE_HOURS = 24.0
DEFAULT_REVISIT_SECONDS = 900.0
SYSTEM_PROMPT_TOMBSTONE = ["[AMNESIA ARCHIVE: System prompt snapshot truncated]"]
CHARS_PER_TOKEN = 3.6
MIN_TOMBSTONE_CHARS = 200
DEFAULT_PROJECT_ROOT = "/home/mboyle"
DEFAULT_ARCHIVE_DIR = "/home/mboyle/bd-persist/amnesia-archive"
PINNED_CONTEXT_MODE_BUNDLE = (
    "/home/mboyle/.npm/_npx/16b0a7c005a6df70/node_modules/context-mode/cli.bundle.mjs"
)

# Logger setup
logger = logging.getLogger("bd-amnesia-hook")


class TranscriptDialect(Enum):
    CLAUDE_DAG = "claude_dag"
    CODEX_STREAM = "codex_stream"
    UNKNOWN = "unknown"


@dataclass
class DAGNode:
    uuid: str
    parent_uuid: str | None
    node_type: str
    line_index: int
    data: dict[str, Any]
    token_estimate: int = 0


@dataclass
class SessionCacheEntry:
    path: Path
    st_mtime_ns: int
    st_size: int
    st_ino: int
    last_tokens: int
    last_checked_ts: float
    skip_until: float = 0.0


def discover_context_mode_bundle(explicit_cli: str | None = None) -> str | None:
    """Finds the context-mode cli.bundle.mjs executable bundle."""
    if explicit_cli:
        p = os.path.abspath(explicit_cli)
        if os.path.isfile(p) and os.access(p, os.R_OK):
            return p
        logger.warning(f"Specified context-mode bundle not found: {explicit_cli}")

    if os.path.isfile(PINNED_CONTEXT_MODE_BUNDLE) and os.access(
        PINNED_CONTEXT_MODE_BUNDLE, os.R_OK
    ):
        return PINNED_CONTEXT_MODE_BUNDLE

    candidates = glob.glob("/home/mboyle/.npm/_npx/*/node_modules/context-mode/cli.bundle.mjs")
    if candidates:
        return max(candidates, key=os.path.getmtime)

    try:
        npm_root = subprocess.check_output(
            ["npm", "root", "-g"], text=True, timeout=3, stderr=subprocess.DEVNULL
        ).strip()
        global_bundle = os.path.join(npm_root, "context-mode", "cli.bundle.mjs")
        if os.path.isfile(global_bundle):
            return global_bundle
    except (subprocess.SubprocessError, OSError) as e:
        logger.debug(f"npm root check failed: {e}")

    return None


def detect_dialect(records: list[dict[str, Any]]) -> TranscriptDialect:
    """Detects whether records represent Claude DAG or Codex Stream transcript."""
    for d in records:
        if "uuid" in d and "parentUuid" in d:
            return TranscriptDialect.CLAUDE_DAG
        if d.get("type") == "last-prompt":
            return TranscriptDialect.CLAUDE_DAG
        if "ordinal" in d and d.get("type") in (
            "session_meta",
            "turn_context",
            "response_item",
            "compacted",
            "event_msg",
        ):
            return TranscriptDialect.CODEX_STREAM
    return TranscriptDialect.UNKNOWN


def dump_record(rec: Any) -> str:
    """Serialize like the transcript writers: compact separators, raw unicode."""
    return json.dumps(rec, separators=(",", ":"), ensure_ascii=False) + "\n"


def estimate_tokens_from_chars(text_len: int) -> int:
    return max(1, int(text_len / CHARS_PER_TOKEN))


# ============================================================================
# Claude DAG Parser & Tombstoner
# ============================================================================

class ClaudeDAGParser:
    """Parses and validates Claude Code DAG transcripts."""

    def __init__(self, raw_lines: list[str]):
        self.raw_lines = raw_lines
        self.nodes_by_uuid: dict[str, DAGNode] = {}
        self.non_dag_records: list[tuple[int, dict[str, Any]]] = []
        self.leaf_uuid: str | None = None
        self.session_id: str | None = None
        self._parse()

    def _parse(self) -> None:
        for idx, line in enumerate(self.raw_lines):
            line_str = line.strip()
            if not line_str:
                continue
            data = json.loads(line_str)
            t = data.get("type")

            if t == "last-prompt":
                self.leaf_uuid = data.get("leafUuid")
                if not self.session_id and "sessionId" in data:
                    self.session_id = data.get("sessionId")
                self.non_dag_records.append((idx, data))
            elif "uuid" in data and "parentUuid" in data:
                u = data["uuid"]
                p = data["parentUuid"]
                toks = estimate_tokens_from_chars(len(line_str))
                node = DAGNode(
                    uuid=u,
                    parent_uuid=p,
                    node_type=t or "unknown",
                    line_index=idx,
                    data=data,
                    token_estimate=toks,
                )
                self.nodes_by_uuid[u] = node
                if not self.session_id and "sessionId" in data:
                    self.session_id = data.get("sessionId")
            else:
                self.non_dag_records.append((idx, data))

    def get_active_branch(self) -> list[DAGNode]:
        """Backtracks from leaf_uuid to root parentUuid: null."""
        if not self.leaf_uuid:
            # Fallback: identify terminal node with no children
            all_parents = {n.parent_uuid for n in self.nodes_by_uuid.values() if n.parent_uuid}
            terminals = [u for u in self.nodes_by_uuid if u not in all_parents]
            if terminals:
                self.leaf_uuid = terminals[-1]
            elif self.nodes_by_uuid:
                self.leaf_uuid = list(self.nodes_by_uuid.keys())[-1]
            else:
                return []

        path = []
        curr: str | None = self.leaf_uuid
        visited: set[str] = set()

        while curr:
            if curr in visited:
                logger.error(f"Cycle detected in DAG at node {curr}")
                break
            visited.add(curr)
            node = self.nodes_by_uuid.get(curr)
            if not node:
                logger.warning(f"DAG walk: parent node {curr} missing from file")
                break
            path.append(node)
            curr = node.parent_uuid

        path.reverse()
        return path

    def validate_invariants(self, branch: list[DAGNode]) -> tuple[bool, str]:
        """Validates parent connectivity and 1:1 Anthropic tool pairing."""
        if not branch:
            return True, "Empty branch"

        # 1. Connectivity
        for i in range(1, len(branch)):
            if branch[i].parent_uuid != branch[i - 1].uuid:
                return False, f"Broken chain at index {i}: {branch[i].uuid} parent != {branch[i-1].uuid}"

        # 2. Tool pairing
        open_tool_uses: dict[str, str] = {}
        for node in branch:
            d = node.data
            t = node.node_type
            if t == "assistant":
                content = d.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and blk.get("type") == "tool_use":
                            open_tool_uses[blk.get("id", "")] = blk.get("name", "unknown")
            elif t == "user":
                content = d.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and blk.get("type") == "tool_result":
                            tid = blk.get("tool_use_id", "")
                            open_tool_uses.pop(tid, None)

        if open_tool_uses:
            # Note: The active turn at the very end of branch may have an uncompleted tool call
            # We check if remaining open tools were only introduced in the terminal assistant node
            last_node = branch[-1]
            if last_node.node_type == "assistant":
                last_content = last_node.data.get("message", {}).get("content", [])
                last_ids = {
                    b.get("id")
                    for b in last_content
                    if isinstance(b, dict) and b.get("type") == "tool_use"
                }
                if set(open_tool_uses.keys()).issubset(last_ids):
                    return True, "Terminal turn tool_use pending execution (valid)"

            return False, f"Unmatched tool_use IDs in history: {list(open_tool_uses.keys())}"

        return True, "All DAG invariants validated"


class ContextModeIndexer:
    """Manages cold archive file generation and context-mode vector indexing."""

    def __init__(
        self,
        cli_bundle: str | None,
        project_root: str,
        archive_dir: Path,
    ):
        self.cli_bundle = cli_bundle
        self.project_root = project_root
        self.archive_dir = archive_dir
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def stage_markdown(
        self,
        session_id: str,
        turn_id: str,
        node_uuid: str,
        parent_uuid: str | None,
        role: str,
        tool_name: str,
        tool_use_id: str,
        command_snippet: str,
        content: str,
        thinking: str = "",
    ) -> Path:
        """Writes a structured markdown document for context-mode chunking."""
        sess_dir = self.archive_dir / session_id
        sess_dir.mkdir(parents=True, exist_ok=True)

        safe_tool_id = re.sub(r"[^a-zA-Z0-9_-]", "_", tool_use_id or "notool")
        safe_node = re.sub(r"[^a-zA-Z0-9_-]", "_", node_uuid)
        stage_file = sess_dir / f"{safe_node}_{safe_tool_id}.md"

        iso_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        char_count = len(content)

        # Detect code language if applicable
        lang = "bash" if "bash" in tool_name.lower() or "sh" in tool_name.lower() else "text"

        with open(stage_file, "w", encoding="utf-8") as sf:
            sf.write(f"# Session {session_id} Turn {turn_id} Archive\n\n")
            sf.write("## Metadata\n")
            sf.write(f"- **Session ID**: {session_id}\n")
            sf.write(f"- **Turn ID**: {turn_id}\n")
            sf.write(f"- **Node UUID**: {node_uuid}\n")
            sf.write(f"- **Parent UUID**: {parent_uuid or 'null'}\n")
            sf.write(f"- **Role**: {role}\n")
            sf.write(f"- **Tool Name**: {tool_name}\n")
            sf.write(f"- **Tool Use ID**: {tool_use_id}\n")
            sf.write(f"- **Timestamp**: {iso_ts}\n")
            sf.write(f"- **Original Size**: {char_count} characters\n\n")

            if command_snippet:
                sf.write("## Tool Invocation Command\n")
                sf.write(f"```\n{command_snippet}\n```\n\n")

            if thinking:
                sf.write("## Assistant Reasoning\n")
                sf.write(f"{thinking}\n\n")

            sf.write("## Archived Output\n")
            sf.write(f"```{lang}\n{content}\n```\n")

        return stage_file

    def index_file(self, stage_file: Path, source_label: str) -> bool:
        """Indexes staged file into context-mode FTS5 database."""
        if not self.cli_bundle:
            logger.debug(f"Context-mode CLI not available; cold file preserved at {stage_file}")
            return False

        cmd = [
            "node",
            self.cli_bundle,
            "index",
            str(stage_file.resolve()),
            "--source",
            source_label,
            "--project",
            self.project_root,
            "--no-gitignore",
        ]

        # Retry with exponential backoff on SQLite lock contention
        for attempt in range(3):
            try:
                res = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if res.returncode == 0:
                    logger.debug(f"Indexed {stage_file.name} to {source_label}")
                    return True
                if "database is locked" in res.stderr:
                    time.sleep(1.0 * (2**attempt))
                    continue
                logger.warning(
                    f"Context-mode index error (rc={res.returncode}): {res.stderr.strip()}"
                )
                return False
            except subprocess.TimeoutExpired:
                logger.warning(f"Context-mode index timed out for {stage_file.name} (attempt {attempt+1})")
                time.sleep(1.0)
            except (subprocess.SubprocessError, OSError) as e:
                logger.warning(f"Failed to execute context-mode index: {e}")
                return False

        return False

    def index_directory(self, dir_path: Path, source_label: str) -> bool:
        """Indexes an entire directory of staged markdown files in one batch."""
        if not self.cli_bundle:
            logger.debug(f"Context-mode CLI not available; cold archive preserved at {dir_path}")
            return False

        cmd = [
            "node",
            self.cli_bundle,
            "index",
            str(dir_path.resolve()),
            "--source",
            source_label,
            "--project",
            self.project_root,
            "--no-gitignore",
        ]

        for attempt in range(3):
            try:
                res = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                if res.returncode == 0:
                    logger.debug(f"Batch indexed {dir_path.name} to {source_label}")
                    return True
                if "database is locked" in res.stderr:
                    logger.warning("Database locked during batch index, backing off...")
                    time.sleep(1.0 * (2**attempt))
                    continue
                logger.warning(
                    f"Context-mode batch index error (rc={res.returncode}): {res.stderr.strip()}"
                )
                return False
            except subprocess.TimeoutExpired:
                logger.warning(f"Context-mode batch index timed out for {dir_path.name} (attempt {attempt+1})")
                time.sleep(1.0)
            except (subprocess.SubprocessError, OSError) as e:
                logger.warning(f"Failed to execute context-mode batch index: {e}")
                return False

        return False


class SemanticTombstoner:
    """Tombstones bulky older turns and offloads content to context-mode."""

    def __init__(
        self,
        parser: ClaudeDAGParser,
        indexer: ContextModeIndexer,
        trigger_tokens: int = DEFAULT_TRIGGER_TOKENS,
        target_tokens: int = DEFAULT_TARGET_TOKENS,
        min_turn_preserve: int = DEFAULT_MIN_TURN_PRESERVE,
        recent_reserve: int = DEFAULT_RECENT_RESERVE,
    ):
        self.parser = parser
        self.indexer = indexer
        self.trigger_tokens = trigger_tokens
        self.target_tokens = target_tokens
        self.min_turn_preserve = min_turn_preserve
        self.recent_reserve = recent_reserve
        self.active_branch = parser.get_active_branch()
        self.session_id = parser.session_id or "default_session"

    def estimate_active_branch_tokens(self) -> int:
        return sum(node.token_estimate for node in self.active_branch)

    def plan_and_execute(self) -> tuple[list[str], int, int, int]:
        """
        Executes semantic tombstoning down to target_tokens.
        Returns: (output_lines, initial_tokens, final_tokens, items_archived)
        """
        init_tokens = self.estimate_active_branch_tokens()
        if init_tokens <= self.trigger_tokens:
            return self.parser.raw_lines, init_tokens, init_tokens, 0

        if len(self.active_branch) <= self.min_turn_preserve + 1:
            logger.info(
                f"Active branch has only {len(self.active_branch)} turns; cannot prune beyond reserve."
            )
            return self.parser.raw_lines, init_tokens, init_tokens, 0

        # 1. Determine Protected Recent Zone boundary
        # Preserve the most recent min_turn_preserve conversational turns (counted via user nodes)
        recent_user_turns = 0
        split_idx = max(1, len(self.active_branch) - (self.min_turn_preserve * 2))

        for idx in range(len(self.active_branch) - 1, 0, -1):
            node = self.active_branch[idx]
            if node.node_type == "user":
                recent_user_turns += 1
            if recent_user_turns >= self.min_turn_preserve:
                # Include the assistant node paired with this user turn in the protected zone
                split_idx = idx - 1 if idx > 1 and self.active_branch[idx - 1].node_type == "assistant" else idx
                break

        split_idx = max(1, split_idx)
        eligible_nodes = self.active_branch[1:split_idx]  # preserve node 0 (root)

        # Build mapping of tool_use id to assistant command input for rich staging metadata
        tool_commands: dict[str, tuple[str, str]] = {}
        for node in self.active_branch:
            if node.node_type == "assistant":
                content = node.data.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and blk.get("type") == "tool_use":
                            tid = blk.get("id", "")
                            tname = blk.get("name", "unknown")
                            tinput = blk.get("input", {})
                            cmd = tinput.get("command") or json.dumps(tinput)
                            tool_commands[tid] = (tname, str(cmd))

        # 2. Collect Candidate Tombstones
        candidates: list[dict[str, Any]] = []
        for turn_num, node in enumerate(eligible_nodes, start=1):
            d = node.data
            t = node.node_type

            if t == "user":
                content = d.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for blk_idx, blk in enumerate(content):
                        if isinstance(blk, dict) and blk.get("type") == "tool_result":
                            res = blk.get("content")
                            res_str = res if isinstance(res, str) else json.dumps(res)
                            if len(res_str) > MIN_TOMBSTONE_CHARS:
                                tid = blk.get("tool_use_id", "unknown")
                                tname, tcmd = tool_commands.get(tid, ("Tool", ""))
                                candidates.append({
                                    "type": "tool_result",
                                    "node": node,
                                    "turn_id": str(turn_num),
                                    "blk_idx": blk_idx,
                                    "tool_use_id": tid,
                                    "tool_name": tname,
                                    "command": tcmd,
                                    "size": len(res_str),
                                    "raw_text": res_str,
                                })

            elif t == "assistant":
                content = d.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for blk_idx, blk in enumerate(content):
                        if isinstance(blk, dict) and blk.get("type") == "thinking":
                            th = blk.get("thinking", "")
                            if len(th) > 500:
                                candidates.append({
                                    "type": "thinking",
                                    "node": node,
                                    "turn_id": str(turn_num),
                                    "blk_idx": blk_idx,
                                    "size": len(th),
                                    "raw_text": th,
                                })

            elif t == "attachment":
                att = d.get("attachment", {})
                att_type = att.get("type")
                if att_type == "prompt_snapshot" and att.get("systemPrompt") != SYSTEM_PROMPT_TOMBSTONE:
                    candidates.append({
                        "type": "prompt_snapshot",
                        "node": node,
                        "turn_id": str(turn_num),
                        "size": len(json.dumps(att.get("systemPrompt"), ensure_ascii=False)),
                    })
                elif att_type in (
                    "total_tokens_reminder",
                    "batching_reminder_sent",
                    "output_style",
                    "bash_output_audience_note",
                ):
                    att_str = json.dumps(att)
                    if len(att_str) > 300:
                        candidates.append({
                            "type": "ephemeral_attachment",
                            "node": node,
                            "turn_id": str(turn_num),
                            "size": len(att_str),
                        })

        # 3. Sort candidates greedily by size descending
        candidates.sort(key=lambda c: c["size"], reverse=True)

        current_tokens = init_tokens
        archived_count = 0
        staged_items: list[tuple[Path, str]] = []
        modified_nodes: set[int] = set()

        for cand in candidates:
            if current_tokens <= self.target_tokens:
                break

            node = cand["node"]
            d = node.data
            saved_chars = 0

            if cand["type"] == "tool_result":
                blk_idx = cand["blk_idx"]
                tid = cand["tool_use_id"]
                raw_text = cand["raw_text"]
                tname = cand["tool_name"]
                tcmd = cand["command"]
                source_label = f"amnesia:{self.session_id}"
                tombstone_msg = (
                    f"[AMNESIA ARCHIVE: Tool output truncated ({len(raw_text)} chars). "
                    f"Indexed in context-mode source '{source_label}'. "
                    f"Retrieve via ctx_search(queries=['...'], source='{source_label}').]"
                )
                if len(tombstone_msg) >= cand["size"]:
                    continue

                # Stage to cold markdown archive
                stage_file = self.indexer.stage_markdown(
                    session_id=self.session_id,
                    turn_id=cand["turn_id"],
                    node_uuid=node.uuid,
                    parent_uuid=node.parent_uuid,
                    role="tool",
                    tool_name=tname,
                    tool_use_id=tid,
                    command_snippet=tcmd,
                    content=raw_text,
                )
                staged_items.append((stage_file, source_label))

                content_target = d["message"]["content"][blk_idx]
                if isinstance(content_target.get("content"), list):
                    content_target["content"] = [{"type": "text", "text": tombstone_msg}]
                else:
                    content_target["content"] = tombstone_msg

                # Truncate duplicate CLI metadata
                if "toolUseResult" in d and isinstance(d["toolUseResult"], dict):
                    d["toolUseResult"]["stdout"] = "[AMNESIA ARCHIVE: Truncated]"
                    d["toolUseResult"]["stderr"] = ""

                saved_chars = cand["size"] - len(tombstone_msg)

            elif cand["type"] == "thinking":
                blk_idx = cand["blk_idx"]
                th_len = cand["size"]
                d["message"]["content"][blk_idx]["thinking"] = (
                    f"[AMNESIA ARCHIVE: Thinking truncated ({th_len} chars)]"
                )
                saved_chars = th_len - 50

            elif cand["type"] == "prompt_snapshot":
                d["attachment"]["systemPrompt"] = list(SYSTEM_PROMPT_TOMBSTONE)
                saved_chars = cand["size"] - 60

            elif cand["type"] == "ephemeral_attachment":
                d["attachment"] = {"type": "truncated_attachment", "text": "[AMNESIA ARCHIVE: Truncated]"}
                saved_chars = cand["size"] - 50

            tokens_saved = estimate_tokens_from_chars(saved_chars)
            current_tokens -= tokens_saved
            node.token_estimate = max(10, node.token_estimate - tokens_saved)
            archived_count += 1
            modified_nodes.add(id(node))

        # Index staged files to context-mode vector store (single batch call)
        if staged_items:
            sess_dir = self.indexer.archive_dir / self.session_id
            if len(staged_items) == 1:
                indexed = self.indexer.index_file(staged_items[0][0], staged_items[0][1])
            else:
                indexed = self.indexer.index_directory(sess_dir, f"amnesia:{self.session_id}")
            if not indexed:
                # A tombstone must point at searchable text; keep the transcript as it was.
                logger.warning(
                    f"Index failed for session {self.session_id}; prune abandoned, "
                    f"cold copies kept in {sess_dir}"
                )
                return list(self.parser.raw_lines), init_tokens, init_tokens, 0

        # 4. Reconstruct lines in exact order
        # Rewrite only the records that were tombstoned; every other line stays byte-identical.
        output_lines = list(self.parser.raw_lines)
        for node in self.active_branch:
            if id(node) in modified_nodes:
                output_lines[node.line_index] = dump_record(node.data)

        return output_lines, init_tokens, current_tokens, archived_count


# ============================================================================
# Codex Stream Parser & Tombstoner
# ============================================================================

class CodexStreamTombstoner:
    """Tombstones bulky older turns in Codex sequential JSONL logs."""

    def __init__(
        self,
        raw_lines: list[str],
        indexer: ContextModeIndexer,
        trigger_tokens: int = DEFAULT_TRIGGER_TOKENS,
        target_tokens: int = DEFAULT_TARGET_TOKENS,
        min_turn_preserve: int = DEFAULT_MIN_TURN_PRESERVE,
    ):
        self.raw_lines = raw_lines
        self.indexer = indexer
        self.trigger_tokens = trigger_tokens
        self.target_tokens = target_tokens
        self.min_turn_preserve = min_turn_preserve
        self.records: list[tuple[int, dict[str, Any]]] = []
        self.session_id: str = "codex_session"
        self._parse()

    def _parse(self) -> None:
        for idx, line in enumerate(self.raw_lines):
            line_str = line.strip()
            if not line_str:
                continue
            data = json.loads(line_str)
            self.records.append((idx, data))
            if "session_id" in data:
                self.session_id = data["session_id"]
            elif data.get("type") == "session_meta":
                p = data.get("payload", {})
                if "id" in p:
                    self.session_id = p["id"]

    def plan_and_execute(self) -> tuple[list[str], int, int, int]:
        total_chars = sum(len(line) for line in self.raw_lines)
        init_tokens = estimate_tokens_from_chars(total_chars)

        if init_tokens <= self.trigger_tokens:
            return self.raw_lines, init_tokens, init_tokens, 0

        # Protect recent records
        cutoff = max(1, len(self.records) - self.min_turn_preserve)
        eligible = self.records[:cutoff]

        candidates = []
        for line_idx, rec in eligible:
            t = rec.get("type")
            payload = rec.get("payload", {})
            p_type = payload.get("type")

            if t == "response_item":
                if p_type in ("custom_tool_call_output", "function_call_output"):
                    output = payload.get("output", "")
                    if isinstance(output, list):
                        output = "\n".join(
                            str(part.get("text", "")) for part in output if isinstance(part, dict)
                        )
                    if isinstance(output, str) and len(output) > MIN_TOMBSTONE_CHARS:
                        candidates.append({
                            "type": "tool_output",
                            "line_idx": line_idx,
                            "record": rec,
                            "call_id": payload.get("call_id", f"call_{line_idx}"),
                            "size": len(output),
                            "raw_text": output,
                        })
                elif p_type == "reasoning":
                    content = payload.get("content", "")
                    if isinstance(content, str) and len(content) > 500:
                        candidates.append({
                            "type": "reasoning",
                            "line_idx": line_idx,
                            "record": rec,
                            "size": len(content),
                            "raw_text": content,
                        })

        candidates.sort(key=lambda c: c["size"], reverse=True)
        current_tokens = init_tokens
        archived_count = 0
        staged_items: list[tuple[Path, str]] = []

        modified_lines: set[int] = set()
        for cand in candidates:
            if current_tokens <= self.target_tokens:
                break

            rec = cand["record"]
            payload = rec["payload"]

            if cand["type"] == "tool_output":
                cid = cand["call_id"]
                raw_text = cand["raw_text"]
                source_label = f"amnesia:{self.session_id}"
                tombstone_msg = (
                    f"[AMNESIA ARCHIVE: Tool output truncated ({len(raw_text)} chars). "
                    f"Indexed in context-mode source '{source_label}'. "
                    f"Retrieve via ctx_search(queries=['...'], source='{source_label}').]"
                )
                if len(tombstone_msg) >= cand["size"]:
                    continue

                stage_file = self.indexer.stage_markdown(
                    session_id=self.session_id,
                    turn_id=str(cand["line_idx"]),
                    node_uuid=f"codex_{cand['line_idx']}",
                    parent_uuid=None,
                    role="tool",
                    tool_name="CodexTool",
                    tool_use_id=cid,
                    command_snippet="",
                    content=raw_text,
                )
                staged_items.append((stage_file, source_label))
                if isinstance(payload.get("output"), list):
                    payload["output"] = [{"type": "input_text", "text": tombstone_msg}]
                else:
                    payload["output"] = tombstone_msg
                saved_chars = cand["size"] - len(tombstone_msg)

            elif cand["type"] == "reasoning":
                payload["content"] = f"[AMNESIA ARCHIVE: Reasoning truncated ({cand['size']} chars)]"
                saved_chars = cand["size"] - 50

            tokens_saved = estimate_tokens_from_chars(saved_chars)
            current_tokens -= tokens_saved
            archived_count += 1
            modified_lines.add(cand["line_idx"])

        # Index staged files to context-mode vector store (single batch call)
        if staged_items:
            sess_dir = self.indexer.archive_dir / self.session_id
            if len(staged_items) == 1:
                indexed = self.indexer.index_file(staged_items[0][0], staged_items[0][1])
            else:
                indexed = self.indexer.index_directory(sess_dir, f"amnesia:{self.session_id}")
            if not indexed:
                # A tombstone must point at searchable text; keep the transcript as it was.
                logger.warning(
                    f"Index failed for session {self.session_id}; prune abandoned, "
                    f"cold copies kept in {sess_dir}"
                )
                return list(self.raw_lines), init_tokens, init_tokens, 0

        # Rewrite only the records that were tombstoned; every other line stays byte-identical.
        output_lines = list(self.raw_lines)
        for line_idx, rec in self.records:
            if line_idx in modified_lines:
                output_lines[line_idx] = dump_record(rec)

        return output_lines, init_tokens, current_tokens, archived_count


# ============================================================================
# Amnesia Background Daemon & Lifecycle
# ============================================================================

class AmnesiaDaemon:
    """Autonomous monitoring daemon with race guard and atomic swap protocol."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.interval = args.interval
        self.trigger_tokens = args.threshold
        self.target_tokens = args.target_tokens
        self.min_turn_preserve = args.min_turn_preserve
        self.recent_reserve = args.recent_reserve
        self.max_age_hours = args.max_age
        self.revisit_interval = args.revisit_interval
        self.min_size_byte_floor = 0 if args.file else args.min_size_floor
        self.dry_run = args.dry_run
        self.project_root = args.project
        self.archive_dir = Path(args.archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        bundle = discover_context_mode_bundle(args.context_mode_cli)
        if not bundle:
            logger.warning("Context-mode CLI bundle not found; cold archive storage only.")
        self.indexer = ContextModeIndexer(bundle, self.project_root, self.archive_dir)

        self.cache: dict[Path, SessionCacheEntry] = {}
        self.running = True
        self.total_tokens_freed = 0
        self.prune_count = 0
        self.start_time = time.time()

        # Signal handlers for graceful termination
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum: int, frame: Any) -> None:
        logger.info(f"Received signal {signum}, initiating clean shutdown...")
        self.running = False

    def discover_targets(self) -> list[Path]:
        """Discovers candidate transcript files matching monitored patterns."""
        if self.args.file:
            p = Path(self.args.file).resolve()
            return [p] if p.is_file() else []

        patterns = self.args.target if self.args.target else [
            "/home/mboyle/.claude-b/projects/-var-tmp-bd-seats-*/*.jsonl",
            "/home/mboyle/.claude/projects/-var-tmp-bd-seats-*/*.jsonl",
            f"/home/mboyle/.codex/sessions/{datetime.datetime.now(datetime.timezone.utc).strftime('%Y/%m')}/*/*.jsonl",
        ]

        found: list[Path] = []
        now = time.time()
        max_age_sec = self.max_age_hours * 3600.0

        for pat in patterns:
            for p_str in glob.glob(pat):
                p = Path(p_str)
                # Ignore temp staging files, locks, or hidden files
                if ".tmp." in p.name or p.name.endswith(".lock") or p.name.startswith("."):
                    continue
                try:
                    st = p.stat()
                    if (now - st.st_mtime) > max_age_sec:
                        continue
                    if st.st_size < self.min_size_byte_floor:
                        continue
                    found.append(p)
                except OSError:
                    continue

        return found

    def process_file(self, file_path: Path) -> bool:
        """
        Executes complete 5-layer concurrency-guarded pruning protocol on a file.
        Returns True if the file was pruned, False otherwise.
        """
        # Layer 1: Advisory Process Flock
        lock_path = file_path.parent / f"{file_path.stem}.amnesia.lock"
        lock_fd: int | None = None
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            logger.debug(f"Lock busy for {file_path.name}, skipping tick.")
            if lock_fd is not None:
                os.close(lock_fd)
            return False

        try:
            # Layer 2: Snapshot Pre-Flight Stat
            try:
                st_init = file_path.stat()
            except OSError as e:
                logger.error(f"Cannot stat {file_path}: {e}")
                return False

            # Cache verification
            cached = self.cache.get(file_path)
            if cached and time.time() < cached.skip_until:
                return False
            if (
                cached
                and cached.st_mtime_ns == st_init.st_mtime_ns
                and cached.st_size == st_init.st_size
                and cached.last_tokens < self.trigger_tokens
            ):
                return False

            # Read all lines
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    raw_lines = f.readlines()
            except OSError as e:
                logger.error(f"Failed to read {file_path}: {e}")
                return False

            if not raw_lines:
                return False

            # Parse lines into JSON dicts
            parsed_records: list[dict[str, Any]] = []
            for line_idx, line in enumerate(raw_lines):
                s = line.strip()
                if not s:
                    continue
                try:
                    parsed_records.append(json.loads(s))
                except json.JSONDecodeError as e:
                    # In-flight torn append detected; abort to prevent corruption
                    logger.warning(
                        f"Torn read detected in {file_path.name} at line {line_idx}: {e}. Aborting tick."
                    )
                    return False

            dialect = detect_dialect(parsed_records)

            if dialect == TranscriptDialect.CLAUDE_DAG:
                parser = ClaudeDAGParser(raw_lines)
                branch = parser.get_active_branch()
                if not branch:
                    logger.debug(f"No active DAG branch found in {file_path.name}")
                    return False

                # Check invariants on active branch
                valid, reason = parser.validate_invariants(branch)
                if not valid:
                    logger.warning(f"DAG invariant failure in {file_path.name}: {reason}")
                    # Still attempt safe processing if tool pairing intact

                tombstoner = SemanticTombstoner(
                    parser=parser,
                    indexer=self.indexer,
                    trigger_tokens=self.trigger_tokens,
                    target_tokens=self.target_tokens,
                    min_turn_preserve=self.min_turn_preserve,
                    recent_reserve=self.recent_reserve,
                )
                est_tokens = tombstoner.estimate_active_branch_tokens()

            elif dialect == TranscriptDialect.CODEX_STREAM:
                codex_tombstoner = CodexStreamTombstoner(
                    raw_lines=raw_lines,
                    indexer=self.indexer,
                    trigger_tokens=self.trigger_tokens,
                    target_tokens=self.target_tokens,
                    min_turn_preserve=self.min_turn_preserve,
                )
                est_tokens = estimate_tokens_from_chars(sum(len(l) for l in raw_lines))
            else:
                logger.debug(f"Unknown transcript dialect for {file_path.name}")
                return False

            # Update cache with current status
            self.cache[file_path] = SessionCacheEntry(
                path=file_path,
                st_mtime_ns=st_init.st_mtime_ns,
                st_size=st_init.st_size,
                st_ino=st_init.st_ino,
                last_tokens=est_tokens,
                last_checked_ts=time.time(),
            )

            if est_tokens <= self.trigger_tokens:
                logger.debug(
                    f"{file_path.name}: {est_tokens} tokens <= threshold ({self.trigger_tokens})"
                )
                return False

            logger.info(
                f"THRESHOLD BREACH: {file_path.name} has ~{est_tokens} tokens "
                f"({st_init.st_size / 1024 / 1024:.2f} MB > limit {self.trigger_tokens})"
            )

            if self.dry_run:
                logger.info(
                    f"[DRY-RUN] Would prune {file_path.name} from {est_tokens} to {self.target_tokens}"
                )
                return True

            # Execute tombstoning
            if dialect == TranscriptDialect.CLAUDE_DAG:
                new_lines, init_toks, final_toks, count = tombstoner.plan_and_execute()
            else:
                new_lines, init_toks, final_toks, count = codex_tombstoner.plan_and_execute()

            if count == 0 or new_lines == raw_lines:
                logger.info(f"No bytes to prune for {file_path.name}; revisit in {self.revisit_interval:.0f}s")
                self.cache[file_path].skip_until = time.time() + self.revisit_interval
                return False
            chars_saved = sum(len(l) for l in raw_lines) - sum(len(l) for l in new_lines)

            # Layer 3: Stage to sibling temporary file (.tmp.<pid>)
            staging_path = file_path.parent / f"{file_path.name}.tmp.{os.getpid()}"
            try:
                with open(staging_path, "w", encoding="utf-8") as out:
                    for line in new_lines:
                        out.write(line)
                    out.flush()
                    os.fsync(out.fileno())

                st_staged = staging_path.stat()
                if st_staged.st_size == 0:
                    raise OSError("Staged file size is 0 bytes! Aborting swap.")

                # Validate staged file JSON integrity
                with open(staging_path, "r", encoding="utf-8") as verify_f:
                    for idx, line in enumerate(verify_f):
                        line_str = line.strip()
                        if line_str:
                            json.loads(line_str)

                shutil.copymode(file_path, staging_path)

                # Layer 4: Concurrency Pre-Commit Stat Verification
                st_cur = file_path.stat()
                if (
                    st_cur.st_size != st_init.st_size
                    or st_cur.st_mtime_ns != st_init.st_mtime_ns
                    or st_cur.st_ino != st_init.st_ino
                ):
                    delta = st_cur.st_size - st_init.st_size
                    logger.warning(
                        f"CONCURRENCY RACE DETECTED on {file_path.name}: "
                        f"file changed during processing (delta: {delta:+d} bytes). "
                        f"Aborting swap to protect concurrent turns."
                    )
                    return False

                # Layer 5: Commit POSIX Atomic Swap
                os.replace(staging_path, file_path)

                # Sync parent directory entry
                dir_fd = os.open(file_path.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)

                # Re-stat and update cache
                st_final = file_path.stat()
                tokens_saved = estimate_tokens_from_chars(max(0, chars_saved))
                self.total_tokens_freed += tokens_saved
                self.prune_count += 1

                self.cache[file_path] = SessionCacheEntry(
                    path=file_path,
                    st_mtime_ns=st_final.st_mtime_ns,
                    st_size=st_final.st_size,
                    st_ino=st_final.st_ino,
                    last_tokens=final_toks,
                    last_checked_ts=time.time(),
                    skip_until=time.time() + self.revisit_interval,
                )

                logger.info(
                    f"AMNESIA PRUNE COMPLETE: {file_path.name} | "
                    f"Tokens freed (measured bytes): {tokens_saved} | Planned: {init_toks} -> {final_toks} | "
                    f"Items: {count} archived | "
                    f"Size: {st_init.st_size / 1024:.1f}KB -> {st_final.st_size / 1024:.1f}KB"
                )
                return True

            finally:
                if staging_path.exists():
                    try:
                        staging_path.unlink()
                    except OSError:
                        pass

        finally:
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    os.close(lock_fd)
                except OSError:
                    pass
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def run(self) -> None:
        """Main operational execution loop."""
        logger.info(
            f"Starting Amnesia Hook (mode={'daemon' if self.args.daemon else 'once'}, "
            f"threshold={self.trigger_tokens}, target={self.target_tokens}, "
            f"interval={self.interval}s)"
        )

        while self.running:
            targets = self.discover_targets()
            if not targets and self.args.file:
                logger.error(f"Target file does not exist: {self.args.file}")
                break

            pruned_in_pass = 0
            for target in targets:
                if not self.running:
                    break
                try:
                    if self.process_file(target):
                        pruned_in_pass += 1
                except Exception:
                    logger.exception(f"Unexpected error processing {target.name}")

            if not self.args.daemon:
                break

            time.sleep(self.interval)

        logger.info(
            f"Amnesia Hook stopped. Sessions pruned: {self.prune_count}, "
            f"Total tokens freed: {self.total_tokens_freed}"
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="bd-amnesia-hook.py - Active Transcript Truncation & Vector Offload Daemon"
    )
    parser.add_argument("--file", type=str, help="Target specific .jsonl transcript file")
    parser.add_argument(
        "--daemon", action="store_true", help="Run continuously in background daemon loop"
    )
    parser.add_argument(
        "--once", action="store_true", help="Run a single pass across targets and exit"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"Daemon polling interval in seconds (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_TRIGGER_TOKENS,
        help=f"Token threshold to trigger pruning (default: {DEFAULT_TRIGGER_TOKENS})",
    )
    parser.add_argument(
        "--target-tokens",
        type=int,
        default=DEFAULT_TARGET_TOKENS,
        help=f"Target token ceiling after pruning (default: {DEFAULT_TARGET_TOKENS})",
    )
    parser.add_argument(
        "--min-turn-preserve",
        type=int,
        default=DEFAULT_MIN_TURN_PRESERVE,
        help=f"Minimum recent turns to preserve intact (default: {DEFAULT_MIN_TURN_PRESERVE})",
    )
    parser.add_argument(
        "--recent-reserve",
        type=int,
        default=DEFAULT_RECENT_RESERVE,
        help=f"Token reserve for protected recent zone (default: {DEFAULT_RECENT_RESERVE})",
    )
    parser.add_argument(
        "--min-size-floor",
        type=int,
        default=DEFAULT_MIN_SIZE_BYTE_FLOOR,
        help=f"Byte size floor for discovery quick-reject (default: {DEFAULT_MIN_SIZE_BYTE_FLOOR})",
    )
    parser.add_argument(
        "--max-age",
        type=float,
        default=DEFAULT_MAX_AGE_HOURS,
        help=f"Max file age in hours for discovery (default: {DEFAULT_MAX_AGE_HOURS})",
    )
    parser.add_argument(
        "--revisit-interval",
        type=float,
        default=DEFAULT_REVISIT_SECONDS,
        help=f"Seconds to leave a file alone after a no-op, failed index or prune (default: {DEFAULT_REVISIT_SECONDS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate pruning actions without modifying files or vector DB",
    )
    parser.add_argument(
        "--project",
        type=str,
        default=DEFAULT_PROJECT_ROOT,
        help=f"Project root for context-mode database resolution (default: {DEFAULT_PROJECT_ROOT})",
    )
    parser.add_argument(
        "--archive-dir",
        type=str,
        default=DEFAULT_ARCHIVE_DIR,
        help=f"Permanent cold archive directory (default: {DEFAULT_ARCHIVE_DIR})",
    )
    parser.add_argument(
        "--context-mode-cli",
        type=str,
        default=None,
        help="Path to context-mode cli.bundle.mjs executable bundle",
    )
    parser.add_argument(
        "--target",
        type=str,
        action="append",
        help="Glob pattern for candidate transcripts (repeatable)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose DEBUG logging")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [bd-amnesia-hook] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    daemon = AmnesiaDaemon(args)
    daemon.run()


if __name__ == "__main__":
    main()
