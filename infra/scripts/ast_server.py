#!/usr/bin/env python3
"""Tree-sitter and AST Query Server on port 8095."""
import ast
import hashlib
import json
import logging
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST = "0.0.0.0"
PORT = 8095
LOG_FILE = Path("/home/mboyle/infra/support-layer/ast_server.log")
SKEL_CACHE_DIR = Path("/var/tmp/bd-skel-cache")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ast_server")


class SkeletonTransformer(ast.NodeTransformer):
    """Folds function and method bodies to Ellipsis (...), preserving docstrings and interfaces."""

    def visit_Module(self, node: ast.Module) -> ast.Module:
        new_body = []
        for stmt in node.body:
            if isinstance(
                stmt,
                (
                    ast.Import,
                    ast.ImportFrom,
                    ast.ClassDef,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.Assign,
                    ast.AnnAssign,
                ),
            ):
                res = self.visit(stmt)
                if res is not None:
                    new_body.append(res)
            elif (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                # Module-level docstring
                new_body.append(stmt)
            elif isinstance(stmt, ast.If):
                res = self.visit(stmt)
                if res is not None:
                    new_body.append(res)
        node.body = new_body
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        return self._fold_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        return self._fold_func(node)

    def _fold_func(self, node):
        doc = ast.get_docstring(node, clean=False)
        ellipsis_stmt = ast.Expr(value=ast.Constant(value=Ellipsis))
        if doc is not None and node.body:
            node.body = [node.body[0], ellipsis_stmt]
        else:
            node.body = [ellipsis_stmt]
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        doc = ast.get_docstring(node, clean=False)
        new_body = []
        start_idx = 0
        if doc is not None and node.body:
            new_body.append(node.body[0])
            start_idx = 1

        for item in node.body[start_idx:]:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                new_body.append(self.visit(item))
            elif isinstance(item, (ast.AnnAssign, ast.Assign)):
                new_body.append(item)
            elif isinstance(item, ast.Pass):
                pass
        if not new_body:
            new_body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
        node.body = new_body
        return node


def get_ast_skeleton(code: str) -> str:
    """Parses code, folds bodies, and returns the formatted skeleton string."""
    tree = ast.parse(code)
    transformer = SkeletonTransformer()
    transformed_tree = transformer.visit(tree)
    ast.fix_missing_locations(transformed_tree)
    return ast.unparse(transformed_tree)


def get_symbol_def(code: str, symbol: str) -> dict:
    """Finds a symbol definition in the given code and returns start/end lines and snippet."""
    tree = ast.parse(code)
    parts = symbol.strip().split(".")
    found_node = None

    if len(parts) == 1:
        target = parts[0]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == target:
                found_node = node
                break
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Name) and t.id == target:
                        found_node = node
                        break
                if found_node:
                    break
    elif len(parts) == 2:
        class_target, member_target = parts
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_target:
                for sub in node.body:
                    if (
                        isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and sub.name == member_target
                    ):
                        found_node = sub
                        break
                if found_node:
                    break

    if found_node is not None:
        seg = ast.get_source_segment(code, found_node)
        if not seg:
            seg = ast.unparse(found_node)
        start_line = getattr(found_node, "lineno", 1)
        end_line = getattr(found_node, "end_lineno", start_line)
        return {
            "status": "ok",
            "symbol": symbol,
            "symbol_def": seg,
            "start_line": start_line,
            "end_line": end_line,
        }

    return {
        "status": "not_found",
        "error": f"Symbol '{symbol}' not found",
        "symbol": symbol,
    }


class ASTServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/health") or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "service": "tree-sitter-ast-server",
                "port": PORT,
                "ast_grep": "0.45.3"
            }).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Invalid JSON: {e}"}).encode("utf-8"))
            return

        if self.path.startswith("/parse"):
            code = payload.get("code", "")
            try:
                tree = ast.parse(code)
                nodes = sum(1 for _ in ast.walk(tree))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "valid_syntax": True,
                    "ast_dump": ast.dump(tree),
                    "node_count": nodes
                }).encode("utf-8"))
            except SyntaxError as se:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "syntax_error",
                    "valid_syntax": False,
                    "error": str(se),
                    "lineno": se.lineno,
                    "offset": se.offset
                }).encode("utf-8"))
            return

        if self.path.startswith("/query"):
            pattern = payload.get("pattern", "")
            code = payload.get("code", "")
            lang = payload.get("lang", "python")
            try:
                proc = subprocess.run(
                    ["/home/mboyle/.local/bin/ast-grep", "run", "--pattern", pattern, "--lang", lang, "--stdin"],
                    input=code.encode("utf-8"),
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "matches": proc.stdout.decode("utf-8"),
                    "returncode": proc.returncode
                }).encode("utf-8"))
            except (OSError, subprocess.SubprocessError) as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        if self.path.startswith("/skeleton"):
            file_path = payload.get("file_path", "")
            code = payload.get("code", "")

            if not code and file_path:
                p = Path(file_path)
                if not p.is_file():
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "error",
                        "error": f"File not found: {file_path}"
                    }).encode("utf-8"))
                    return
                try:
                    code = p.read_text(encoding="utf-8", errors="replace")
                except OSError as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "error",
                        "error": f"Failed to read file: {e}"
                    }).encode("utf-8"))
                    return

            if not code and not file_path:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "error": "Either 'code' or 'file_path' must be provided."
                }).encode("utf-8"))
                return

            sha256 = hashlib.sha256(code.encode("utf-8")).hexdigest()
            SKEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file = SKEL_CACHE_DIR / f"{sha256}.skel"

            cached = False
            if cache_file.is_file():
                try:
                    skeleton = cache_file.read_text(encoding="utf-8")
                    cached = True
                except OSError:
                    cached = False

            if not cached:
                try:
                    skeleton = get_ast_skeleton(code)
                    cache_file.write_text(skeleton, encoding="utf-8")
                except SyntaxError as se:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "syntax_error",
                        "valid_syntax": False,
                        "error": str(se),
                        "lineno": se.lineno
                    }).encode("utf-8"))
                    return
                except (ValueError, TypeError) as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "error",
                        "error": str(e)
                    }).encode("utf-8"))
                    return

            tokens = len(skeleton.split())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "skeleton": skeleton,
                "sha256": sha256,
                "tokens": tokens,
                "cached": cached,
                "file_path": file_path
            }).encode("utf-8"))
            return

        if self.path.startswith("/symbol"):
            symbol = payload.get("symbol", "").strip()
            if not symbol:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "error": "Parameter 'symbol' is required."
                }).encode("utf-8"))
                return

            file_path = payload.get("file_path", "")
            code = payload.get("code", "")

            if not code and file_path:
                p = Path(file_path)
                if not p.is_file():
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "error",
                        "error": f"File not found: {file_path}"
                    }).encode("utf-8"))
                    return
                try:
                    code = p.read_text(encoding="utf-8", errors="replace")
                except OSError as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "error",
                        "error": f"Failed to read file: {e}"
                    }).encode("utf-8"))
                    return

            if not code and not file_path:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "error": "Either 'code' or 'file_path' must be provided."
                }).encode("utf-8"))
                return

            try:
                res = get_symbol_def(code, symbol)
                if file_path:
                    res["file_path"] = file_path
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except SyntaxError as se:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "syntax_error",
                    "valid_syntax": False,
                    "error": str(se),
                    "lineno": se.lineno
                }).encode("utf-8"))
            except (ValueError, TypeError) as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "error": str(e)
                }).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format_str, *args):
        logger.info(f"{self.client_address[0]} - - [{self.log_date_time_string()}] {format_str % args}")


def main():
    server = HTTPServer((HOST, PORT), ASTServerHandler)
    logger.info(f"Tree-sitter AST Server listening on {HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
