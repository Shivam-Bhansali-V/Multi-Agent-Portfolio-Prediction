"""
08_snapshot_and_chartcheck.py -- regenerates the two checkpoint artefacts that were
produced in an earlier session but never reached the PC:

  1. Checkpoint 1.4: a SHA-256 frozen-snapshot manifest of the clean data and the
     labels for the 8 pilot symbols, so any later result can be tied to the exact
     bytes it was computed from.
  2. Checkpoint 2.1: the "20 labels verified by hand on charts" check -- 20 sampled
     label instances plotted with their barriers and touch points, plus the CSV of
     what was sampled, so the check is auditable rather than asserted.

Both are reproducible: the sample is drawn with a fixed seed, and the manifest is a
pure function of the files on disk.
"""

from __future__ import annotations

import hashlib
import importlib.util as _ilu
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CLEAN = ROOT / "data" / "clean"
LABELS = ROOT / "data" / "labels"
P1 = ROOT / "reports" / "phase1"
CHARTS = P1 / "chart_checks"

SYMS = ["TCS", "RELIANCE", "BAJAJFINSV", "ITC", "SIEMENS", "VEDL", "IDEA", "ADANIENT"]
SEED = 20261008
HORIZON = 10


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ======================================================================================
# Checkpoint 1.4 -- frozen snapshot manifest
# ======================================================================================

def build_manifest() -> dict:
    entries = []
    for sym in SYMS:
        for kind, d in (("clean", CLEAN), ("labels", LABELS)):
            p = d / f"{sym}.csv"
            if not p.is_file():
                entries.append({"symbol": sym, "kind": kind, "path": str(p.relative_to(ROOT)),
                                "present": False})
                continue
            df = pd.read_csv(p)
            dates = pd.to_datetime(df["Date"] if "Date" in df.columns else df["date"])
            entries.append({
                "symbol": sym, "kind": kind,
                "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                "present": True,
                "bytes": p.stat().st_size,
                "rows": int(len(df)),
                "first_date": str(dates.min().date()),
                "last_date": str(dates.max().date()),
                "sha256": sha256(p),
            })
    ref = []
    for p in sorted((ROOT / "data" / "reference").glob("*.csv")):
        ref.append({"path": str(p.relative_to(ROOT)).replace("\\", "/"),
                    "bytes": p.stat().st_size, "sha256": sha256(p)})

    manifest = {
        "checkpoint": "1.4 — quality report and frozen data snapshot",
        "scope": "8-stock pilot",
        "generated_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "frozen_spec": {
            "universe": "NIFTY100 (pilot subset of 8)",
            "date_range": "2015-01-01 to present",
            "holdout_start": "2025-04-01",
            "labels": "triple barrier +2*ATR / -1*ATR / 10-day timeout, ATR14 min_periods=14",
            "cost_per_round_trip": 0.0035,
            "execution": "next-day open",
        },
        "known_limitations": [
            "Survivorship bias: today's NIFTY100 constituents used for the whole history.",
            "296 uncaught large moves project-wide; only 4 individually web-verified.",
            "7 phantom flat zero-volume sessions in 2025-2026 remain in the calendar; the "
            "backtest marks them non-tradeable but 02c_calendar.py is not yet fixed.",
        ],
        "files": entries,
        "reference_files": ref,
    }
    manifest["manifest_digest"] = hashlib.sha256(
        json.dumps([e.get("sha256") for e in entries] + [r["sha256"] for r in ref],
                   sort_keys=True).encode()
    ).hexdigest()
    return manifest


# ======================================================================================
# Checkpoint 2.1 -- 20 hand-checkable label charts
# ======================================================================================

def chart_check(n: int = 20) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    picks = []
    for sym in SYMS:
        lab = pd.read_csv(LABELS / f"{sym}.csv")
        lab["date"] = pd.to_datetime(lab["date"])
        lab["touch_date"] = pd.to_datetime(lab["touch_date"], errors="coerce")
        kept = lab.loc[lab["dropped_reason"].isna() & lab["label"].notna()]
        kept = kept.loc[kept["date"] <= pd.Timestamp("2025-03-31")]
        if kept.empty:
            continue
        # Stratify: take one of each outcome per symbol where available, so the
        # eyeball check covers Up, Down and Sideways rather than the majority class.
        for outcome in ("Up", "Down", "Sideways"):
            sub = kept.loc[kept["label"] == outcome]
            if len(sub):
                picks.append(sub.iloc[int(rng.integers(0, len(sub)))].to_dict() | {"symbol": sym})
    rng.shuffle(picks)
    picks = picks[:n]

    cols, rows_n = 4, int(np.ceil(len(picks) / 4))
    fig, axes = plt.subplots(rows_n, cols, figsize=(4.0 * cols, 2.9 * rows_n))
    axes = np.atleast_1d(axes).ravel()
    recs = []

    for ax, rec in zip(axes, picks):
        sym = rec["symbol"]
        px = pd.read_csv(CLEAN / f"{sym}.csv", parse_dates=["Date"]).set_index("Date").sort_index()
        t = pd.Timestamp(rec["date"])
        i = px.index.searchsorted(t)
        lo, hi = max(0, i - 6), min(len(px), i + HORIZON + 4)
        w = px.iloc[lo:hi]
        x = np.arange(len(w))
        ti = list(w.index).index(t) if t in w.index else 6

        ax.vlines(x, w["AdjLow"], w["AdjHigh"], color="#898781", lw=1.1)
        ax.plot(x, w["AdjClose"], color="#0b0b0b", lw=0.9, ls=":", zorder=1)
        ax.axhline(rec["upper_barrier"], color="#2a78d6", lw=1.2, label="upper +2ATR")
        ax.axhline(rec["lower_barrier"], color="#e34948", lw=1.2, label="lower -1ATR")
        ax.axvline(ti, color="#4a3aa7", lw=1.0, alpha=0.8)
        # the 10-session resolution window
        ax.axvspan(ti + 0.5, min(ti + HORIZON + 0.5, len(w) - 0.5),
                   color="#eda100", alpha=0.10)

        touch_ok = None
        if pd.notna(rec["touch_date"]):
            td = pd.Timestamp(rec["touch_date"])
            if td in w.index:
                tj = list(w.index).index(td)
                ax.plot([tj], [w["AdjHigh"].iloc[tj] if rec["label"] == "Up"
                               else w["AdjLow"].iloc[tj]],
                        marker="o", ms=7, mfc="none",
                        mec="#2a78d6" if rec["label"] == "Up" else "#e34948", mew=1.8)
                # Verify the touch actually breaches the barrier it claims.
                touch_ok = bool(
                    (w["AdjHigh"].iloc[tj] >= rec["upper_barrier"]) if rec["label"] == "Up"
                    else (w["AdjLow"].iloc[tj] <= rec["lower_barrier"]))
        else:
            # Sideways: assert NOTHING in the window breached either barrier.
            win = w.iloc[ti + 1: ti + 1 + HORIZON]
            touch_ok = bool((win["AdjHigh"] < rec["upper_barrier"]).all()
                            and (win["AdjLow"] > rec["lower_barrier"]).all())

        ax.set_title(f"{sym}  {t.date()}  → {rec['label']}"
                     + ("  OK" if touch_ok else "  CHECK"),
                     fontsize=9, color="#0b0b0b" if touch_ok else "#d03b3b")
        ax.set_xticks([]); ax.tick_params(labelsize=7)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)

        recs.append({
            "symbol": sym, "date": str(t.date()), "label": rec["label"],
            "touch_date": str(pd.Timestamp(rec["touch_date"]).date()) if pd.notna(rec["touch_date"]) else "",
            "atr": rec["atr"], "upper_barrier": rec["upper_barrier"],
            "lower_barrier": rec["lower_barrier"],
            "barrier_consistent": touch_ok,
        })

    for ax in axes[len(picks):]:
        ax.axis("off")
    fig.suptitle("Checkpoint 2.1 — 20 sampled triple-barrier labels with barriers and "
                 "touch points (stratified across Up / Down / Sideways)", fontsize=11, y=0.998)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    CHARTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHARTS / "label_sample_20.png", dpi=130, facecolor="white")
    plt.close(fig)
    return pd.DataFrame(recs)


if __name__ == "__main__":
    P1.mkdir(parents=True, exist_ok=True)

    man = build_manifest()
    mp = P1 / "checkpoint_1_4_frozen_snapshot_8stocks.json"
    mp.write_text(json.dumps(man, indent=1), encoding="utf-8")
    present = sum(1 for e in man["files"] if e.get("present"))
    print(f"[1.4] wrote {mp.relative_to(ROOT)}")
    print(f"      {present}/{len(man['files'])} data files hashed, "
          f"{len(man['reference_files'])} reference files, "
          f"digest {man['manifest_digest'][:16]}...")

    df = chart_check()
    cp = P1 / "checkpoint_2_1_chart_check_sample.csv"
    df.to_csv(cp, index=False)
    ok = int(df["barrier_consistent"].sum())
    print(f"[2.1] wrote {CHARTS.relative_to(ROOT)}/label_sample_20.png and {cp.relative_to(ROOT)}")
    print(f"      {ok}/{len(df)} sampled labels are internally consistent with their barriers")
    print(df[["symbol", "date", "label", "touch_date", "barrier_consistent"]].to_string(index=False))
    raise SystemExit(0 if ok == len(df) else 1)
