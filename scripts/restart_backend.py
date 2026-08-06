"""Restart the backend uvicorn server on a given port (Windows).

Usage: python scripts/restart_backend.py [port]
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
LOG = ROOT / "backend" / "uvicorn.log"
ERR = ROOT / "backend" / "uvicorn.log.err"


def find_pids(port: int) -> set:
    pids = set()
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == "TCP" and ":%d" % port in parts[1] and parts[3] == "LISTENING":
                pids.add(int(parts[4]))
    except Exception as exc:  # noqa: BLE001
        print("netstat failed:", exc)
    return pids


def kill(pids) -> None:
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print("killed pid", pid)
        except Exception as exc:  # noqa: BLE001
            print("kill failed", pid, exc)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    for _ in range(10):
        pids = find_pids(port)
        if not pids:
            break
        kill(pids)
        time.sleep(0.5)
    with open(LOG, "w", encoding="utf-8") as out, open(ERR, "w", encoding="utf-8") as err:
        subprocess.Popen(
            [str(PY), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(ROOT / "backend"),
            stdout=out,
            stderr=err,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    print("started uvicorn on", port)


if __name__ == "__main__":
    main()
