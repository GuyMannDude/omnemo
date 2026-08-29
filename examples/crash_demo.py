#!/usr/bin/env python3
"""Crash-memory demo: SIGKILL the MCP server mid-session, prove the memory survives.

Honest test: the kill is -9 (no signal handler, no atexit, no flush) and it fires
the moment the save *response* arrives — the earliest instant a client could
believe the save happened.
"""
import json
import os
import signal
import subprocess
import sys
import time

STAMP = time.strftime("%Y-%m-%d %H:%M:%S")
FACT = f"Crash demo {STAMP}: the harness was SIGKILLed right after this save returned."


def send(proc, obj):
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()


def read_until_id(proc, want_id):
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("server closed stdout before responding")
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == want_id:
            return msg


proc = subprocess.Popen(
    ["omnemo", "serve"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True,
)

send(proc, {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
               "clientInfo": {"name": "crash-demo", "version": "0"}},
})
init = read_until_id(proc, 1)
print(f"[1] session open  (server: {init['result']['serverInfo']['name']} "
      f"{init['result']['serverInfo'].get('version', '?')}, pid {proc.pid})")
send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

send(proc, {
    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
    "params": {"name": "save", "arguments": {"text": FACT, "category": "fact"}},
})
save_resp = read_until_id(proc, 2)
if save_resp.get("error") or save_resp.get("result", {}).get("isError"):
    print(f"[!] save FAILED: {save_resp}")
    sys.exit(1)
print(f"[2] save acknowledged: {json.dumps(save_resp['result'].get('structuredContent') or save_resp['result'])[:120]}")

os.kill(proc.pid, signal.SIGKILL)
proc.wait()
print(f"[3] server SIGKILLed (exit {proc.returncode}) — no shutdown, no flush, session gone")

recall = subprocess.run(
    ["omnemo", "recall", FACT.split(":")[0]],
    capture_output=True, text=True,
)
found = FACT in recall.stdout
print(f"[4] fresh process recall: {'SURVIVED — memory intact' if found else 'LOST'}")
print(recall.stdout.strip()[:300])
sys.exit(0 if found else 1)
