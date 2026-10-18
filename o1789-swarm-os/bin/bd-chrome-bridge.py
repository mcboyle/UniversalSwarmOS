#!/usr/bin/env python3
import socket
import select
import threading
import json
import urllib.request
import os

TARGET_HOST = "10.0.70.181"
TARGET_PORT = 9222
LISTEN_PORT = 9222

def update_devtools_active_port():
    try:
        url = f"http://{TARGET_HOST}:{TARGET_PORT}/json/version"
        req = urllib.request.urlopen(url, timeout=3)
        data = json.loads(req.read().decode())
        ws_url = data.get("webSocketDebuggerUrl", "")
        # Extract path
        path = ws_url.replace(f"ws://{TARGET_HOST}:{TARGET_PORT}", "")
        os.makedirs(os.path.expanduser("~/.config/google-chrome"), exist_ok=True)
        active_port_file = os.path.expanduser("~/.config/google-chrome/DevToolsActivePort")
        with open(active_port_file, "w") as f:
            f.write(f"{LISTEN_PORT}\n{path}\n")
        print(f"Updated {active_port_file}: port={LISTEN_PORT}, path={path}")
    except Exception as e:
        print(f"Error updating DevToolsActivePort: {e}")

def forward(src, dst):
    try:
        while True:
            r, _, _ = select.select([src], [], [], 60)
            if not r:
                break
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass

def handle_client(client_sock):
    try:
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.connect((TARGET_HOST, TARGET_PORT))
        t1 = threading.Thread(target=forward, args=(client_sock, remote_sock), daemon=True)
        t2 = threading.Thread(target=forward, args=(remote_sock, client_sock), daemon=True)
        t1.start()
        t2.start()
    except Exception as e:
        print(f"Error handling connection: {e}")
        client_sock.close()

def main():
    update_devtools_active_port()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", LISTEN_PORT))
    server.listen(10)
    print(f"Bridge listening on 127.0.0.1:{LISTEN_PORT} -> {TARGET_HOST}:{TARGET_PORT}")
    while True:
        client, _ = server.accept()
        threading.Thread(target=handle_client, args=(client,), daemon=True).start()

if __name__ == "__main__":
    main()
