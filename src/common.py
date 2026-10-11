"""Shared paths, configuration loading, logging and raw-data provenance helpers.

Every raw download goes through :func:`fetch_raw`, which saves the response bytes
unmodified and appends a row to ``data/raw/source_register_log.csv`` recording the
URL, retrieval timestamp, file hash and size. Raw files are never edited afterwards.
"""
from __future__ import annotations

import csv
import hashlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
TABLES = RESULTS / "tables"
DIAGNOSTICS = RESULTS / "diagnostics"
LOGS = RESULTS / "logs"

USER_AGENT = "capital-flows-political-economy/1.0 (academic research; reproducible pipeline)"
REGISTER_LOG = RAW / "source_register_log.csv"


def load_config() -> dict:
    with open(CONFIG / "analysis_config.yaml") as f:
        return yaml.safe_load(f)


def get_logger(name: str) -> logging.Logger:
    LOGS.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        fh = logging.FileHandler(LOGS / "pipeline.log")
        fh.setFormatter(fmt)
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(sh)
    return logger


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def register(source: str, url: str, path: Path, note: str = "") -> None:
    """Append a provenance record for a raw file."""
    REGISTER_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not REGISTER_LOG.exists()
    with open(REGISTER_LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["retrieved_utc", "source", "url", "file", "bytes", "sha256", "note"])
        w.writerow([
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            source, url, str(path.relative_to(ROOT)), path.stat().st_size, _sha256(path), note,
        ])


def fetch_raw(url: str, dest: Path, source: str, *, params: dict | None = None,
              headers: dict | None = None, refresh: bool = False, note: str = "",
              retries: int = 4, timeout: int = 300, use_curl: bool = False,
              validator=None) -> Path:
    """Download ``url`` to ``dest`` unless it already exists (raw archive is immutable).

    Raises on HTTP failure after retries; never writes a partial or synthetic file.
    ``validator(bytes) -> str | None`` may reject a 200 response whose body is an API
    error message; the rejection reason is raised rather than archived.
    """
    log = get_logger("fetch")
    if dest.exists() and not refresh:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    if use_curl:
        # Some public endpoints (IMF DataMapper, FRED) reject or stall python-requests
        # connections but serve curl normally; the request itself is identical.
        return _fetch_curl(url, dest, source, params, headers or {}, note, retries, timeout)
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=hdrs, timeout=timeout)
            if r.status_code == 200 and r.content:
                problem = validator(r.content) if validator else None
                if problem:
                    raise RuntimeError(f"{source}: invalid response: {problem}")
                tmp = dest.with_suffix(dest.suffix + ".part")
                tmp.write_bytes(r.content)
                tmp.rename(dest)
                full_url = r.url
                register(source, full_url, dest, note)
                log.info("fetched %s -> %s (%d bytes)", source, dest.name, len(r.content))
                return dest
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
        except requests.RequestException as e:  # network errors are retried, then raised
            last_err = repr(e)
        time.sleep(2 ** attempt)
    log.error("FAILED %s %s: %s", source, url, last_err)
    raise RuntimeError(f"Download failed for {source}: {last_err}")


def _fetch_curl(url, dest, source, params, headers, note, retries, timeout):
    import subprocess
    from urllib.parse import urlencode
    log = get_logger("fetch")
    full = url + ("?" + urlencode(params) if params else "")
    tmp = dest.with_suffix(dest.suffix + ".part")
    cmd = ["curl", "-sSL", "--fail", "-m", str(timeout), "-o", str(tmp)]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    last = None
    for attempt in range(retries):
        r = subprocess.run(cmd + [full], capture_output=True, text=True)
        if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
            tmp.rename(dest)
            register(source, full, dest, note)
            log.info("fetched (curl) %s -> %s (%d bytes)", source, dest.name, dest.stat().st_size)
            return dest
        last = r.stderr.strip()
        time.sleep(2 ** attempt)
    tmp.unlink(missing_ok=True)
    log.error("FAILED %s %s: %s", source, full, last)
    raise RuntimeError(f"Download failed for {source}: {last}")
