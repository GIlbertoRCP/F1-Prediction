"""Extract race + qualifying results from FastF1's HTTP cache into plain CSV files.

FastF1 caches every Jolpica/Ergast response it has fetched in a requests-cache
SQLite file. This script reads those responses (standard library only; no FastF1 or
requests-cache install needed) and writes tidy CSVs under data/results/.

Usage:  python3 scripts/extract_cached_results.py [path/to/fastf1_http_cache.sqlite]
"""
import io
import json
import pickle
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from evaluation.jolpica import dedupe, parse_payload, write_rows  # noqa: E402

DEFAULT_DB = ROOT / ".f1_cache" / "fastf1_http_cache.sqlite"
OUT_DIR = ROOT / "data" / "results"
URL_RE = re.compile(r"https://api\.jolpi\.ca/ergast/f1/\d{4}/\d+/(results|qualifying|sprint)\.json")


class _Stub:
    def __init__(self, *a, **k):
        pass

    def __setstate__(self, state):
        self.__dict__["_state"] = state


class _SafeUnpickler(pickle.Unpickler):
    """Unpickle cache entries without importing requests_cache; unknown classes become stubs."""

    _ALLOWED = {"builtins", "collections", "datetime", "copyreg", "copy_reg", "_codecs"}

    def find_class(self, module, name):
        if module in self._ALLOWED:
            return super().find_class(module, name)
        return type(name, (_Stub,), {})


def main(db_path: Path) -> None:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    collected = {"results": [], "sprint": [], "qualifying": []}
    for _key, blob, _exp in con.execute("select key, value, expires from responses"):
        try:
            entry = _SafeUnpickler(io.BytesIO(blob)).load()
            m = URL_RE.fullmatch(entry["url"])
            if not m or entry.get("status_code") != 200:
                continue
            collected[m.group(1)].extend(parse_payload(m.group(1), json.loads(entry["_content"])))
        except Exception:
            continue
    for kind, rows in collected.items():
        rows = dedupe(rows)
        if rows:
            path = write_rows(OUT_DIR, kind, rows)
            weekends = len({(r["season"], r["round"]) for r in rows})
            print(f"{kind}: {len(rows)} rows, {weekends} race weekends -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB)
