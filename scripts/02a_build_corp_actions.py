"""
02a_build_corp_actions.py -- RECONSTRUCTED 8 Oct 2026.

The original 02a_build_corp_actions.py (referenced by 03_labels.py and listed in
CLAUDE.md's Phase 1.1 status line) is missing from this sandbox -- only present, if at
all, on the user's PC. Rather than guess at its internals, this reconstruction derives
the same `load_corp_actions(root) -> DataFrame[symbol, action_type, ex_date]` contract
directly from data already verified and on disk: every data/clean/<symbol>.csv file
carries its own `CorpActionTypes` (semicolon-joined string, e.g. "dividend;split") and
`CorpActionExDate` (bool) columns, which 02_clean_adjust.py (whatever produced them)
already populated per bar. This is not a guess at unseen logic -- it reads real,
already-verified columns that both the old 8 pilot symbols and the full 103-symbol
universe already have.

Scope note, stated plainly: this reads corp actions for every symbol with a file in
data/clean/ -- for this sandbox, that's currently the pilot symbols only (not the
sandbox-missing full 103, which only exist on the PC). 03_labels.py's purge_windows()
call works correctly for any symbol whose clean CSV is present; it was previously
blocked for ALL symbols (not just the 4 new ones) because 03_labels.py couldn't even
import without this file -- that is now fixed, the dependency gap being specifically
this missing file, not a problem with 03_labels.py's own logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

RELEVANT_TYPES = {"split", "bonus", "demerger", "rights"}


def load_corp_actions(root: Path) -> pd.DataFrame:
    clean_dir = Path(root) / "data" / "clean"
    rows: List[dict] = []
    if not clean_dir.is_dir():
        return pd.DataFrame(columns=["symbol", "action_type", "ex_date"])

    for path in sorted(clean_dir.glob("*.csv")):
        symbol = path.stem
        df = pd.read_csv(path, usecols=lambda c: c in {
            "Date", "CorpActionTypes", "CorpActionExDate"
        })
        if "CorpActionTypes" not in df.columns or "CorpActionExDate" not in df.columns:
            continue
        df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
        flagged = df[df["CorpActionExDate"] == True]  # noqa: E712
        for _, r in flagged.iterrows():
            types_str = r.get("CorpActionTypes")
            if not isinstance(types_str, str) or not types_str:
                continue
            for t in types_str.split(";"):
                t = t.strip().lower()
                if t in RELEVANT_TYPES:
                    rows.append({"symbol": symbol, "action_type": t, "ex_date": r["Date"]})

    return pd.DataFrame(rows, columns=["symbol", "action_type", "ex_date"])


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    out = load_corp_actions(root)
    print(f"{len(out)} relevant corp-action rows across {out['symbol'].nunique() if len(out) else 0} symbols")
    print(out.groupby(["symbol", "action_type"]).size() if len(out) else "no rows")
