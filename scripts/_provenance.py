#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_provenance.py -- capture execution provenance and stamp machine-readable headers into reports.

Fixes F01 (reports with untracked code origin) and F13 (non-reproducible run artifacts).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

try:
    import yfinance as yf
    YFINANCE_VERSION = yf.__version__
except Exception:
    YFINANCE_VERSION = "unavailable"


def file_sha256(path: Union[str, Path]) -> str:
    """Compute hex SHA-256 digest of a file, reading in 64 KiB chunks."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Cannot hash non-existent file: {p}")
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_git_commit(script_path: Optional[Union[str, Path]] = None) -> str:
    """Get the current git commit SHA, or fallback to file sha256 if git fails."""
    try:
        cwd = Path(script_path).parent if script_path else Path.cwd()
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    if script_path and Path(script_path).is_file():
        return f"file_sha256:{file_sha256(script_path)}"
    return "unknown"


def provenance_header(
    script_path: Union[str, Path],
    inputs: Optional[Sequence[Union[str, Path]]] = None,
) -> Dict[str, Any]:
    """Capture full environment and input provenance.
    
    Includes git commit or script hash, UTC timestamp, python/pandas/numpy/yfinance
    versions, platform, and SHA-256 for all input files.
    """
    sp = Path(script_path).resolve()
    input_hashes: Dict[str, str] = {}
    if inputs:
        for inp in inputs:
            p = Path(inp)
            if p.is_file():
                input_hashes[p.name] = file_sha256(p)
            elif p.is_dir():
                # Hash all CSVs if directory
                for child in sorted(p.glob("*.csv")):
                    input_hashes[child.name] = file_sha256(child)

    header = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": sp.name,
        "script_sha256": file_sha256(sp) if sp.is_file() else "unknown",
        "git_commit": get_git_commit(sp),
        "python_version": sys.version.split()[0],
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
        "yfinance_version": YFINANCE_VERSION,
        "platform": platform.platform(),
        "input_files_sha256": input_hashes,
    }
    return header


def format_header_markdown(header: Dict[str, Any]) -> str:
    """Format header dictionary as markdown block with embedded JSON for machine parsing."""
    json_block = json.dumps(header, indent=2)
    md = [
        "<!-- PROVENANCE_START",
        json_block,
        "PROVENANCE_END -->",
        "",
        "### Provenance & Environment",
        f"- **Generated (UTC):** `{header.get('timestamp_utc')}`",
        f"- **Script:** `{header.get('script')}` (commit/hash: `{header.get('git_commit')}`)",
        f"- **Environment:** Python `{header.get('python_version')}`, pandas `{header.get('pandas_version')}`, numpy `{header.get('numpy_version')}`, yfinance `{header.get('yfinance_version')}`",
        f"- **Tracked Input Files:** {len(header.get('input_files_sha256', {}))}",
        "",
    ]
    return "\n".join(md)


def write_report(
    path: Union[str, Path],
    title: str,
    header: Dict[str, Any],
    body: str,
) -> Path:
    """Write report to file with mandatory provenance header stamped at top."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    header_md = format_header_markdown(header)
    content = f"# {title}\n\n{header_md}\n{body}\n"
    p.write_text(content, encoding="utf-8")
    return p


# ======================================================================================
# Self-test -- SYNTHETIC in-memory / temporary files only
# ======================================================================================

def _selftest() -> int:
    import tempfile
    passed = 0
    failed = 0

    def check(name: str, cond: bool, detail: str = ""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"PASS  {name}")
        else:
            failed += 1
            print(f"FAIL  {name} -- {detail}")

    print("=" * 70)
    print("_provenance.py Self-Test (SYNTHETIC in-memory / temp files)")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        dummy_script = tdp / "dummy_script.py"
        dummy_script.write_text("print('hello')", encoding="utf-8")

        dummy_input = tdp / "input.csv"
        dummy_input.write_text("a,b,c\n1,2,3\n", encoding="utf-8")

        # 1. file_sha256
        h = file_sha256(dummy_input)
        check("file_sha256 computes 64-char hex digest", len(h) == 64 and all(c in "0123456789abcdef" for c in h))

        # 2. provenance_header
        hdr = provenance_header(dummy_script, inputs=[dummy_input])
        check("provenance_header contains script and timestamp", "script" in hdr and "timestamp_utc" in hdr)
        check("provenance_header records python/pandas versions", "python_version" in hdr and "pandas_version" in hdr)
        check("provenance_header tracks input file hash", dummy_input.name in hdr["input_files_sha256"])
        check("input file hash matches direct sha256", hdr["input_files_sha256"][dummy_input.name] == h)

        # 3. write_report
        out_report = tdp / "test_report.md"
        write_report(out_report, "Test Report Title", hdr, "## Body Section\nSome content here.")
        check("write_report creates file", out_report.is_file())
        text = out_report.read_text(encoding="utf-8")
        check("report contains machine-readable PROVENANCE_START block", "PROVENANCE_START" in text and "PROVENANCE_END" in text)
        check("report contains human-readable header", "### Provenance & Environment" in text)
        check("report contains body", "## Body Section" in text)

    print("-" * 70)
    print(f"{passed} passed, {failed} failed")
    print("-" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_selftest())
