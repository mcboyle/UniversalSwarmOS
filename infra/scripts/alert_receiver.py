#!/usr/bin/env python3
import json
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

LOG_FILE = Path("/home/mboyle/infra/support-layer/alerts.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

class AlertWebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "service": "alert-receiver"}')
            return

        if self.path.startswith("/alerts"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            if LOG_FILE.exists():
                self.wfile.write(LOG_FILE.read_bytes())
            else:
                self.wfile.write(b"No alerts logged yet.\n")
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        route_path = self.path

        try:
            payload = json.loads(body.decode("utf-8"))
            status = payload.get("status", "unknown")
            alerts = payload.get("alerts", [])
            group_labels = payload.get("groupLabels", {})

            for alert in alerts:
                labels = alert.get("labels", {})
                annotations = alert.get("annotations", {})
                alertname = labels.get("alertname", "UnknownAlert")
                severity = labels.get("severity", "unknown")
                tier = labels.get("tier", "unknown")
                summary = annotations.get("summary", "")
                desc = annotations.get("description", "")
                starts_at = alert.get("startsAt", "")

                log_entry = (
                    f"[{route_path}] STATUS={status.upper()} ALERT={alertname} "
                    f"SEVERITY={severity} TIER={tier} SUMMARY=\"{summary}\" "
                    f"DESC=\"{desc}\" TIME={starts_at}"
                )
                logging.info(log_entry)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "received"}')
        except Exception as e:
            logging.error(f"Error parsing alert payload: {e}")
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def main():
    server_address = ("0.0.0.0", 9095)
    httpd = HTTPServer(server_address, AlertWebhookHandler)
    logging.info("Starting mesh alert receiver daemon on 0.0.0.0:9095")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()

if __name__ == "__main__":
    main()
