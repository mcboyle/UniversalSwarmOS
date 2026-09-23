#!/usr/bin/env python3
"""Tree-sitter and AST Query Server on port 8095."""
import ast
import json
import logging
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

HOST = "0.0.0.0"
PORT = 8095
LOG_FILE = Path("/home/mboyle/infra/support-layer/ast_server.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

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
        except Exception as e:
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
                    timeout=5
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "matches": proc.stdout.decode("utf-8"),
                    "returncode": proc.returncode
                }).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        logging.info("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))

def main():
    server = HTTPServer((HOST, PORT), ASTServerHandler)
    logging.info(f"Tree-sitter AST Server listening on {HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
