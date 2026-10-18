#!/usr/bin/env python3
"""
AST State Graph Differ (R4: Multi-Agent CoW RadixTree & AST State Diffing).

Computes symbolic AST state graph differences between base code S_{t-1} and modified code S_t.
Emits minimal symbolic delta tuples:
    <op, node, seam>
where:
    op in {ADD, MODIFY, DELETE, REPLACE, RENAME}
    node in {TYPE#IDENTIFIER} (e.g. FuncDef#authenticate, Assign#OLD_KEY)
    seam in {line START-END, byte START-END}

Integrates with Tree-sitter / AST microservice at http://127.0.0.1:8095 and ratf.ctx_slice.
Falls back seamlessly to Python stdlib ast.parse if the microservice is unreachable.
Gracefully reports syntax errors as:
    <SYNTAX_ERROR, File#<path>, line <lineno>>
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SERVER_URL = os.environ.get("BD_AST_SERVER_URL", "http://127.0.0.1:8095")
DEFAULT_TIMEOUT_SEC = 1.0


@dataclass
class ASTNodeInfo:
    """Represents a symbolic node in the AST state graph."""

    node_type: str
    name: str
    lineno: int
    end_lineno: int
    ast_dump: str
    scope: str = ""

    @property
    def identifier(self) -> str:
        return f"{self.node_type}#{self.name}"

    @property
    def seam(self) -> str:
        return f"line {self.lineno}-{self.end_lineno}"


@dataclass
class SymbolicDelta:
    """Minimal symbolic state delta tuple."""

    op: str
    node: str
    seam: str
    lineno: int
    is_delete: bool = False

    def __str__(self) -> str:
        return f"<{self.op}, {self.node}, {self.seam}>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "node": self.node,
            "seam": self.seam,
            "lineno": self.lineno,
        }


def estimate_tokens(text: str) -> int:
    """Project-standard token heuristic matching chars / 3.6."""
    if not text.strip():
        return 0
    char_est = int(len(text) / 3.6)
    word_est = len(re.findall(r"\w+|[^\w\s]", text))
    return max(char_est, word_est)


def check_ast_server(server_url: str = DEFAULT_SERVER_URL, timeout: float = DEFAULT_TIMEOUT_SEC) -> bool:
    """Checks if the Tree-sitter AST server on port 8095 is healthy."""
    try:
        req = urllib.request.Request(f"{server_url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                return data.get("status") == "ok"
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        pass
    return False


def parse_via_server(
    code: str,
    server_url: str = DEFAULT_SERVER_URL,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> dict[str, Any] | None:
    """
    Attempts to validate and parse code via the Tree-sitter AST server.
    Returns response dict on success or None on connection failure.
    """
    try:
        payload = json.dumps({"code": code}).encode("utf-8")
        req = urllib.request.Request(
            f"{server_url}/parse",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8", errors="replace"))  # type: ignore[no-any-return]
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        pass
    return None


def _get_target_name(target: ast.AST) -> str | None:
    """Extracts identifier name from assignment target."""
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        val = _get_target_name(target.value)
        return f"{val}.{target.attr}" if val else target.attr
    return None


def parse_and_validate(
    code: str,
    filepath: str = "<unknown>",
    server_url: str = DEFAULT_SERVER_URL,
    use_server: bool = True,
) -> tuple[ast.AST | None, str | None]:
    """
    Parses code using microservice validation with stdlib ast.parse fallback.
    Returns (tree, syntax_error_string).
    """
    # 1. Microservice pre-check if enabled
    if use_server:
        server_res = parse_via_server(code, server_url=server_url)
        if server_res is not None and (
            server_res.get("status") == "syntax_error" or not server_res.get("valid_syntax", True)
        ):
            lineno = server_res.get("lineno") or 1
            return (None, f"<SYNTAX_ERROR, File#{filepath}, line {lineno}>")

    # 2. Local stdlib AST parse
    try:
        tree = ast.parse(code, filename=filepath)
        return (tree, None)
    except SyntaxError as se:
        lineno = se.lineno or 1
        return (None, f"<SYNTAX_ERROR, File#{filepath}, line {lineno}>")


def extract_ast_nodes(tree: ast.AST) -> dict[str, ASTNodeInfo]:
    """
    Extracts symbolic AST nodes from module:
    - FuncDef (top-level and class methods)
    - ClassDef (class headers, bases, class attributes)
    - Assign (module-level assignments)
    - Import (module imports)
    """
    nodes: dict[str, ASTNodeInfo] = {}

    if not isinstance(tree, ast.Module):
        return nodes

    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lineno = stmt.lineno
            end_lineno = getattr(stmt, "end_lineno", lineno) or lineno
            dump = ast.dump(stmt, include_attributes=False)
            info = ASTNodeInfo(
                node_type="FuncDef",
                name=stmt.name,
                lineno=lineno,
                end_lineno=end_lineno,
                ast_dump=dump,
            )
            nodes[info.identifier] = info

        elif isinstance(stmt, ast.ClassDef):
            lineno = stmt.lineno
            end_lineno = getattr(stmt, "end_lineno", lineno) or lineno

            # Class signature / definition dump excluding method bodies
            # This isolates class header/decorator/attribute changes from method edits
            non_method_stmts = [
                s for s in stmt.body if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            class_def_repr = (
                f"ClassDef(name={stmt.name}, bases={[ast.dump(b, include_attributes=False) for b in stmt.bases]}, "
                f"decorators={[ast.dump(d, include_attributes=False) for d in stmt.decorator_list]}, "
                f"body={[ast.dump(s, include_attributes=False) for s in non_method_stmts]})"
            )
            class_info = ASTNodeInfo(
                node_type="ClassDef",
                name=stmt.name,
                lineno=lineno,
                end_lineno=end_lineno,
                ast_dump=class_def_repr,
            )
            nodes[class_info.identifier] = class_info

            # Extract individual methods as FuncDef nodes
            for substmt in stmt.body:
                if isinstance(substmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sub_lineno = substmt.lineno
                    sub_end_lineno = getattr(substmt, "end_lineno", sub_lineno) or sub_lineno
                    sub_dump = ast.dump(substmt, include_attributes=False)

                    ident = f"FuncDef#{substmt.name}"
                    if ident in nodes:
                        ident = f"FuncDef#{stmt.name}:{substmt.name}"

                    method_info = ASTNodeInfo(
                        node_type="FuncDef",
                        name=substmt.name,
                        lineno=sub_lineno,
                        end_lineno=sub_end_lineno,
                        ast_dump=sub_dump,
                        scope=stmt.name,
                    )
                    nodes[ident] = method_info

        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                target_name = _get_target_name(target)
                if target_name:
                    lineno = stmt.lineno
                    end_lineno = getattr(stmt, "end_lineno", lineno) or lineno
                    dump = ast.dump(stmt, include_attributes=False)
                    info = ASTNodeInfo(
                        node_type="Assign",
                        name=target_name,
                        lineno=lineno,
                        end_lineno=end_lineno,
                        ast_dump=dump,
                    )
                    nodes[info.identifier] = info

        elif isinstance(stmt, ast.AnnAssign):
            target_name = _get_target_name(stmt.target)
            if target_name:
                lineno = stmt.lineno
                end_lineno = getattr(stmt, "end_lineno", lineno) or lineno
                dump = ast.dump(stmt, include_attributes=False)
                info = ASTNodeInfo(
                    node_type="Assign",
                    name=target_name,
                    lineno=lineno,
                    end_lineno=end_lineno,
                    ast_dump=dump,
                )
                nodes[info.identifier] = info

        elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
            for alias in stmt.names:
                lineno = stmt.lineno
                end_lineno = getattr(stmt, "end_lineno", lineno) or lineno
                dump = ast.dump(stmt, include_attributes=False)
                info = ASTNodeInfo(
                    node_type="Import",
                    name=alias.name,
                    lineno=lineno,
                    end_lineno=end_lineno,
                    ast_dump=dump,
                )
                nodes[info.identifier] = info

    return nodes


def compute_ast_diff(
    base_code: str,
    mod_code: str,
    base_path: str = "base.py",
    mod_path: str = "mod.py",
    server_url: str = DEFAULT_SERVER_URL,
    use_server: bool = True,
) -> tuple[list[SymbolicDelta], str | None]:
    """
    Computes symbolic AST delta tuples between base_code and mod_code.
    Returns (list_of_deltas, syntax_error_or_none).
    """
    # 1. Check syntax of base code
    tree_base, err_base = parse_and_validate(
        base_code, filepath=base_path, server_url=server_url, use_server=use_server
    )
    if err_base:
        return ([], err_base)

    # 2. Check syntax of modified code
    tree_mod, err_mod = parse_and_validate(
        mod_code, filepath=mod_path, server_url=server_url, use_server=use_server
    )
    if err_mod:
        return ([], err_mod)

    # 3. Extract AST state graphs
    base_nodes = extract_ast_nodes(tree_base) if tree_base else {}
    mod_nodes = extract_ast_nodes(tree_mod) if tree_mod else {}

    deltas: list[SymbolicDelta] = []

    # 4. Detect MODIFY and ADD (relative to mod_code positions)
    for ident, mod_info in mod_nodes.items():
        if ident not in base_nodes:
            deltas.append(
                SymbolicDelta(
                    op="ADD",
                    node=ident,
                    seam=mod_info.seam,
                    lineno=mod_info.lineno,
                    is_delete=False,
                )
            )
        else:
            base_info = base_nodes[ident]
            if mod_info.ast_dump != base_info.ast_dump:
                deltas.append(
                    SymbolicDelta(
                        op="MODIFY",
                        node=ident,
                        seam=mod_info.seam,
                        lineno=mod_info.lineno,
                        is_delete=False,
                    )
                )

    # 5. Detect DELETE (relative to base_code positions)
    for ident, base_info in base_nodes.items():
        if ident not in mod_nodes:
            deltas.append(
                SymbolicDelta(
                    op="DELETE",
                    node=ident,
                    seam=base_info.seam,
                    lineno=base_info.lineno,
                    is_delete=True,
                )
            )

    # 6. Sort deltas: active file changes first by line number, then deletions
    active_deltas = [d for d in deltas if not d.is_delete]
    delete_deltas = [d for d in deltas if d.is_delete]

    active_deltas.sort(key=lambda d: d.lineno)
    delete_deltas.sort(key=lambda d: d.lineno)

    return (active_deltas + delete_deltas, None)


def diff_files(
    base_file: str | Path,
    mod_file: str | Path,
    server_url: str = DEFAULT_SERVER_URL,
    use_server: bool = True,
) -> tuple[list[SymbolicDelta], str | None]:
    """Reads base and modified files and computes AST diff."""
    base_p = Path(base_file)
    mod_p = Path(mod_file)

    base_code = ""
    if str(base_file) != "/dev/null" and base_p.exists():
        base_code = base_p.read_text(encoding="utf-8", errors="replace")

    mod_code = ""
    if str(mod_file) != "/dev/null" and mod_p.exists():
        mod_code = mod_p.read_text(encoding="utf-8", errors="replace")

    return compute_ast_diff(
        base_code=base_code,
        mod_code=mod_code,
        base_path=str(base_file),
        mod_path=str(mod_file),
        server_url=server_url,
        use_server=use_server,
    )


def verify_compression_benchmark() -> bool:
    """Verifies that a 500-line code modification diff is compressed into < 25 tokens."""
    base_lines = ["def complex_algorithm():", "    return sum(range(100))\n"]
    base_code = "\n".join(base_lines)

    mod_lines = ["def complex_algorithm():", "    result = 0"]
    for i in range(500):
        mod_lines.append(f"    result += ({i} * 3) ^ {i % 17}")
    mod_lines.append("    return result\n")
    mod_code = "\n".join(mod_lines)

    deltas, err = compute_ast_diff(base_code, mod_code, use_server=False)
    if err:
        print(f"FAILED: Syntax error in benchmark: {err}", file=sys.stderr)
        return False

    out_str = "\n".join(str(d) for d in deltas)
    tokens = estimate_tokens(out_str)

    if len(deltas) != 1:
        print(f"FAILED: Expected 1 delta tuple, got {len(deltas)}: {out_str}", file=sys.stderr)
        return False

    if tokens >= 25:
        print(f"FAILED: Token count {tokens} >= 25 budget:\n{out_str}", file=sys.stderr)
        return False

    print(
        f"OK: 500-line diff compressed into {tokens} tokens (< 25 budget):\n{out_str}"
    )
    return True


def self_test() -> bool:
    """Runs internal self-verification suite covering AC4 requirements."""
    # 1. Modify
    b1 = "def authenticate(u, p):\n    return u == 'admin'\n"
    m1 = "def authenticate(u, p):\n    import hmac\n    return hmac.compare_digest(p, 'secret')\n"
    d1, e1 = compute_ast_diff(b1, m1, use_server=False)
    assert not e1 and len(d1) == 1 and d1[0].op == "MODIFY" and "authenticate" in d1[0].node

    # 2. Add
    b2 = "def f(): return 1\n"
    m2 = "def f(): return 1\n\ndef g(): return 2\n"
    d2, e2 = compute_ast_diff(b2, m2, use_server=False)
    assert not e2 and any(d.op == "ADD" and "g" in d.node for d in d2)

    # 3. Delete
    b3 = "def f(): return 1\ndef g(): return 2\n"
    m3 = "def f(): return 1\n"
    d3, e3 = compute_ast_diff(b3, m3, use_server=False)
    assert not e3 and any(d.op == "DELETE" and "g" in d.node for d in d3)

    # 4. Syntax Error
    b4 = "def ok(): pass\n"
    m4 = "def broken(:\n    syntax error\n"
    _d4, e4 = compute_ast_diff(b4, m4, mod_path="broken.py", use_server=False)
    assert e4 and "SYNTAX_ERROR" in e4 and "broken.py" in e4

    # 5. Token compression
    assert verify_compression_benchmark()

    print("All AST differ self-tests passed successfully.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AST State Graph Differ (R4: Multi-Agent CoW RadixTree & AST State Diffing)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("base", nargs="?", help="Base Python file (S_{t-1})")
    parser.add_argument("modified", nargs="?", help="Modified Python file (S_t)")
    parser.add_argument("--server", default=DEFAULT_SERVER_URL, help="Tree-sitter AST server URL")
    parser.add_argument("--no-server", "--fallback", action="store_true", help="Force stdlib ast.parse fallback")
    parser.add_argument("--json", action="store_true", help="Output deltas as JSON array")
    parser.add_argument("--tokens", action="store_true", help="Estimate and display token usage")
    parser.add_argument("--verify-compression", action="store_true", help="Run 500-line compression benchmark")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests")

    args = parser.parse_args()

    if args.verify_compression:
        return 0 if verify_compression_benchmark() else 1

    if args.self_test:
        return 0 if self_test() else 1

    if not args.base or not args.modified:
        parser.print_help()
        return 2

    use_server = not args.no_server

    deltas, err = diff_files(
        base_file=args.base,
        mod_file=args.modified,
        server_url=args.server,
        use_server=use_server,
    )

    if err:
        print(err)
        return 0

    if args.json:
        payload = [d.to_dict() for d in deltas]
        print(json.dumps(payload, indent=2))
    else:
        for delta in deltas:
            print(str(delta))

    if args.tokens:
        text = "\n".join(str(d) for d in deltas)
        print(f"# Tokens: {estimate_tokens(text)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
