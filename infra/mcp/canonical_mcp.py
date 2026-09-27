#!/usr/bin/env python3
"""Canonical MCP Tool Schema Canonicalization & Deterministic Serialization Module.

Supports Milestone 2 (R2):
- Deterministic Tool Serialization across platforms and servers
- Alphabetical tool schema sorting by tool name
- Recursive JSON key sorting for all dictionaries
- json.dumps(..., sort_keys=True, separators=(',', ':'), ensure_ascii=True)
- Pre-registration at Turn 1 and 0-byte schema diff invariance
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp import types
from mcp.server.fastmcp import FastMCP


def sort_keys_recursive(val: Any) -> Any:
    """Recursively sort dictionary keys."""
    if isinstance(val, dict):
        return {k: sort_keys_recursive(v) for k, v in sorted(val.items())}
    if isinstance(val, list):
        return [sort_keys_recursive(x) for x in val]
    return val


def canonicalize_tool(tool: dict) -> dict:
    """Canonicalize a single tool schema dictionary."""
    return sort_keys_recursive(tool)


def serialize_tools(tools: list[dict]) -> str:
    """Serialize tool schemas alphabetically by tool name with sorted JSON keys."""
    sorted_tools = sorted(
        [sort_keys_recursive(t) for t in tools],
        key=lambda x: x.get("name", "")
    )
    return json.dumps(sorted_tools, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def verify_schema_invariance(schemas_per_turn: list[str]) -> tuple[bool, str]:
    """Verify that tool schema serialization diff across turns is exactly 0 bytes."""
    if not schemas_per_turn:
        return False, "No tool schemas provided"
    ref_bytes = schemas_per_turn[0].encode("utf-8")
    ref_sha = hashlib.sha256(ref_bytes).hexdigest()
    for i, s in enumerate(schemas_per_turn[1:], start=2):
        s_bytes = s.encode("utf-8")
        if len(s_bytes) != len(ref_bytes) or s_bytes != ref_bytes:
            diff_len = abs(len(s_bytes) - len(ref_bytes))
            return False, f"Turn {i} tool schema diff is {diff_len} bytes (expected exactly 0 bytes)"
        s_sha = hashlib.sha256(s_bytes).hexdigest()
        if s_sha != ref_sha:
            return False, f"Turn {i} tool schema hash differs from Turn 1"
    return True, "Tool schema diff between consecutive turns is exactly 0 bytes"


def canonicalize_fastmcp(mcp_server: FastMCP) -> None:
    """Hook FastMCP to enforce alphabetical tool sorting and sorted JSON keys across all MCP queries and wire protocol messages."""
    orig_list_tools = mcp_server._tool_manager.list_tools

    def sorted_list_tools():
        tools = orig_list_tools()
        for t in tools:
            if hasattr(t, "parameters") and isinstance(t.parameters, dict):
                t.parameters = sort_keys_recursive(t.parameters)
            if hasattr(t, "output_schema") and isinstance(t.output_schema, dict):
                t.output_schema = sort_keys_recursive(t.output_schema)
        return sorted(tools, key=lambda t: t.name)

    mcp_server._tool_manager.list_tools = sorted_list_tools

    if hasattr(mcp_server, "_mcp_server") and hasattr(mcp_server._mcp_server, "request_handlers"):
        orig_handler = mcp_server._mcp_server.request_handlers.get(types.ListToolsRequest)
        if orig_handler:
            async def sorted_list_tools_handler(req: types.ListToolsRequest):
                result = await orig_handler(req)
                if hasattr(result, "root") and hasattr(result.root, "tools"):
                    result.root.tools.sort(key=lambda t: t.name)
                    for t in result.root.tools:
                        if hasattr(t, "inputSchema") and isinstance(t.inputSchema, dict):
                            t.inputSchema = sort_keys_recursive(t.inputSchema)
                return result

            mcp_server._mcp_server.request_handlers[types.ListToolsRequest] = sorted_list_tools_handler

    def deterministic_model_dump_json(self, *args, **kwargs):
        d = self.model_dump(by_alias=True, exclude_none=True)
        return json.dumps(sort_keys_recursive(d), sort_keys=True, separators=(',', ':'), ensure_ascii=True)

    types.JSONRPCResponse.model_dump_json = deterministic_model_dump_json
    types.JSONRPCNotification.model_dump_json = deterministic_model_dump_json
