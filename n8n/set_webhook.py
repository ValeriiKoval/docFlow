#!/usr/bin/env python3
"""Point the Telegram bot's webhook at n8n.

    python n8n/set_webhook.py                         # URL from the Cloudflare quick tunnel logs
    python n8n/set_webhook.py --url https://n8n.example.com
    python n8n/set_webhook.py --info                  # show current webhook status
    python n8n/set_webhook.py --delete

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET from .env. Telegram sends the secret in the
X-Telegram-Bot-Api-Secret-Token header; the workflow drops calls without it.
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BOT_TOKEN = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{30,}$")


def tunnel_url(timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        logs = subprocess.run(["docker", "compose", "logs", "tunnel"], cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout
        found = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", logs)
        if found:
            return found[-1]
        time.sleep(3)
    sys.exit("No tunnel URL found. Start it with: docker compose --profile tunnel up -d")


def call(token, method, **params):
    data = urllib.parse.urlencode({k: json.dumps(v) if isinstance(v, (list, dict)) else v
                                   for k, v in params.items()}).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/{method}", data=data or None, timeout=30) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="public base URL of n8n (default: Cloudflare quick tunnel)")
    ap.add_argument("--info", action="store_true")
    ap.add_argument("--delete", action="store_true")
    a = ap.parse_args()

    env = dotenv_values(ROOT / ".env")
    token, secret = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_WEBHOOK_SECRET")
    if not token:
        hint = " (a bot token is in TELEGRAM_WEBHOOK_SECRET: move it)" if secret and BOT_TOKEN.match(secret) else ""
        sys.exit(f"Set TELEGRAM_BOT_TOKEN in .env (from @BotFather){hint}")
    if not BOT_TOKEN.match(token):
        sys.exit("TELEGRAM_BOT_TOKEN does not look like a bot token (expected <digits>:<35 chars>)")
    if secret and not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret):
        sys.exit("TELEGRAM_WEBHOOK_SECRET may contain only A-Z a-z 0-9 _ - (Telegram rule)")
    if a.delete:
        print(call(token, "deleteWebhook"))
        return
    if not a.info:
        if not secret:
            sys.exit("Set TELEGRAM_WEBHOOK_SECRET in .env")
        hook = (a.url or tunnel_url()).rstrip("/") + "/webhook/telegram"
        res = call(token, "setWebhook", url=hook, secret_token=secret,
                   allowed_updates=["message", "callback_query"], drop_pending_updates=True)
        print("setWebhook:", res.get("description", res))
    info = call(token, "getWebhookInfo")["result"]
    me = call(token, "getMe")["result"]
    print(f"bot: @{me['username']}\nwebhook: {info.get('url') or '(none)'}\npending updates: "
          f"{info.get('pending_update_count')}\nlast error: {info.get('last_error_message') or '-'}")


if __name__ == "__main__":
    main()
