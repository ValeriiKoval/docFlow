#!/usr/bin/env python3
"""Minimal Telegram Bot API stand-in for testing the n8n workflow offline.

    python n8n/mock_telegram.py --port 8081 --root eval/dataset_test

Then run n8n with TELEGRAM_API_BASE=http://host.docker.internal:8081 (see n8n/test_workflow.py).

  GET  /bot<token>/getFile?file_id=<path>  -> {"ok":true,"result":{"file_path":"documents/<path>"}}
  GET  /file/bot<token>/documents/<path>   -> bytes of <root>/<path>  (file_id = path relative to --root)
  POST /bot<token>/<method>                -> records {"method", "payload"}, returns ok + message_id
  GET  /_sent                              -> recorded calls (JSON list);  DELETE /_sent clears them
"""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SENT, LOCK, ROOT = [], threading.Lock(), [Path(".")]
COUNTER = iter(range(1000, 10**9))


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # quiet
        pass

    def do_GET(self):
        url = urlparse(self.path)
        parts = url.path.strip("/").split("/")
        if url.path == "/_sent":
            with LOCK:
                return self._json(SENT)
        if parts[0].startswith("bot") and parts[-1] == "getFile":
            fid = parse_qs(url.query).get("file_id", [""])[0]
            return self._json({"ok": True, "result": {"file_id": fid, "file_path": f"documents/{fid}"}})
        if parts[0] == "file" and len(parts) >= 4 and parts[2] == "documents":
            root = ROOT[0].resolve()
            p = (root / "/".join(parts[3:])).resolve()
            if p.is_file() and p.is_relative_to(root):
                data = p.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                return self.wfile.write(data)
            return self._json({"ok": False, "description": "file not found"}, 404)
        return self._json({"ok": False, "description": "not found"}, 404)

    def do_POST(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            payload = {"_raw": True}
        method = parts[-1]
        with LOCK:
            SENT.append({"method": method, "payload": payload})
        return self._json({"ok": True, "result": {"message_id": next(COUNTER)} if method == "sendMessage" else True})

    def do_DELETE(self):
        if self.path == "/_sent":
            with LOCK:
                SENT.clear()
            return self._json({"ok": True})
        return self._json({"ok": False}, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8081)
    ap.add_argument("--root", default="eval/dataset_test")
    a = ap.parse_args()
    ROOT[0] = Path(a.root)
    print(f"mock Telegram API on :{a.port}, files under {a.root}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
