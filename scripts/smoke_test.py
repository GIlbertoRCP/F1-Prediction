"""Load the site in headless Chrome and fail if it logs anything to the console or a section did not render.

The unit tests cover the pure modules; this catches what they cannot: a page that throws on load, a missing
data file, a section left on "Loading…". The site logs nothing when it works, so any console line is a failure.

    python3 scripts/smoke_test.py                 # the site/ folder
    python3 scripts/smoke_test.py /tmp/dry/a-season-end/site
"""
from __future__ import annotations

import functools
import http.server
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]

# (what must be on the page, how to say it is missing)
EXPECT = [
    (r'<section id="forecast"[^>]*>\s*(?!<p class="loading">)', "the hero rendered"),
    (r'class="tower', "a timing tower"),
    (r'id="ch-lede">\s*\S', "the championship summary"),
    (r'class="tile', "the track record tiles"),
    (r'id="race-\d{4}-\d+"', "the race list"),
    (r'id="standings-body">(?:(?!not available).)*?<', "the standings"),
    (r'id="foot-meta">Updated', "the footer"),
]
REFUSE = [("Could not load the data", "the data failed to load"), ("is not available", "a section reported missing data")]


def find_chrome() -> str:
    for c in [os.environ.get("CHROME", "")] + CHROMES:
        if c and (shutil.which(c) or Path(c).exists()):
            return c
    sys.exit("smoke test: no Chrome found (set CHROME=/path/to/chrome)")


def check(site: Path) -> tuple[list[str], str, int]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    handler = functools.partial(Quiet, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        run = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-sandbox", "--enable-logging=stderr",
                              "--v=0", "--virtual-time-budget=15000", "--dump-dom", url],
                             capture_output=True, text=True, timeout=120)
    finally:
        server.shutdown()
    dom, log = run.stdout, run.stderr
    problems = [f"console: {line.split('CONSOLE', 1)[1].strip()}" for line in log.splitlines() if ":CONSOLE" in line]
    problems += [f"missing: {why}" for pattern, why in EXPECT if not re.search(pattern, dom, re.S)]
    problems += [f"found: {why}" for text, why in REFUSE if text in dom]
    if not dom.strip():
        problems.append(f"Chrome returned no page (exit {run.returncode})")
    return problems, url, len(dom)


def main(site: Path) -> int:
    problems, url, size = check(site)
    if problems:                      # headless Chrome now and then stalls on start-up; a real fault fails twice
        problems, url, size = check(site)
    for p in problems:
        print(f"FAIL {p}")
    print(f"smoke test {'failed' if problems else 'passed'}: {url} ({size} bytes of DOM)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"))
