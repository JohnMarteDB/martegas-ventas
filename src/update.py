"""One-shot nightly update: parse new reports -> rebuild dashboard -> publish.

Designed to be run by Windows Task Scheduler after the midnight Gmail script
has dropped the day's reports onto the Drive. Every step is logged to
data/update.log so you can see what happened each night.

Steps:
  1. consolidate.py  (incremental: only new/changed files are parsed)
  2. build_site.py   (regenerate docs/data/dashboard.json)
  3. git publish     (commit + push -> GitHub Pages redeploys). Skipped quietly
     if the repo / remote isn't set up yet.
"""
from __future__ import annotations
import os, sys, subprocess, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

LOG = os.path.join(config.DATA_DIR, "update.log")
PY = sys.executable or "py"


def log(msg):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(args, cwd=None):
    log("RUN: " + " ".join(args))
    p = subprocess.run(args, cwd=cwd or config.PROJECT_DIR,
                       capture_output=True, text=True)
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if out:
        for ln in out.splitlines():
            log("    " + ln)
    if p.returncode != 0 and err:
        for ln in err.splitlines():
            log("    ! " + ln)
    return p.returncode, out, err


def git_publish():
    if not os.path.isdir(os.path.join(config.PROJECT_DIR, ".git")):
        log("git: no repo yet (run scripts/setup_github.ps1) — skipping publish")
        return
    rc, *_ = run(["git", "remote"])
    rc, out, _ = run(["git", "status", "--porcelain"])
    if not out.strip():
        log("git: nothing changed — skipping commit")
        return
    run(["git", "add", "-A"])
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    run(["git", "commit", "-m", f"Actualización de datos {stamp}"])
    rc, _, err = run(["git", "push"])
    if rc == 0:
        log("git: pushed — GitHub Pages will redeploy in ~1 min")
    else:
        log("git: push failed (check auth / remote). Data is committed locally.")


def main():
    log("===== UPDATE START =====")
    # Nightly: only scan the last few months for new files (gentle on DriveFS).
    # The cache keeps all history and consolidate() rebuilds the full dataset.
    # For corrections to OLD months, run a full pass manually: py src/consolidate.py
    rc, *_ = run([PY, "-u", os.path.join("src", "consolidate.py"), "--recent", "2"])
    if rc != 0:
        log("consolidate failed — aborting"); return 1
    rc, *_ = run([PY, "-u", os.path.join("src", "build_site.py")])
    if rc != 0:
        log("build_site failed — aborting"); return 1
    git_publish()
    log("===== UPDATE DONE =====\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
