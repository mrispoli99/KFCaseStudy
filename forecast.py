"""Forecast and reconciliation logic for the KnowFully case dashboard.

Pure pandas/numpy, no Streamlit, so it can be tested on its own.
Mirrors the formulas in KnowFully_Q4_Forecast_Workbook.xlsx: at default
assumptions it reproduces the workbook's low / base / high and P(plan).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

AS_OF = pd.Timestamp("2026-09-30")
Q4_START = pd.Timestamp("2026-10-01")
Q4_END = pd.Timestamp("2026-12-31")
BRANDS_B2B = ["Northstar", "Fieldstone"]

# Local stage -> (common stage, rank). Mapping is a labeled assumption from the Stage Notes tab.
STAGE_MAP = {
    ("Fieldstone", "Qualified"): ("Marketing qualified", 1),
    ("Northstar", "Qualified"): ("Sales accepted", 2),
    ("Fieldstone", "Customer Request"): ("Sales accepted", 2),
    ("Fieldstone", "Proposal"): ("Pricing discussed", 3),
    ("Northstar", "Proposal"): ("Proposal delivered", 4),
    ("Fieldstone", "Verbal"): ("Verbal commit", 5),
}
COMMON_STAGES = ["Marketing qualified", "Sales accepted", "Pricing discussed", "Proposal delivered", "Verbal commit"]


@dataclass
class Assumptions:
    stage_weights: dict = field(default_factory=lambda: {1: 0.5, 2: 1.0, 3: 1.2, 4: 1.3, 5: 1.6})
    cap: float = 0.90            # max probability for any single deal
    slip: float = 0.50           # multiplier when slip risk is flagged
    short_cycle: float = 0.70    # share of brand avg won cycle below which a close date looks optimistic
    near_days: int = 30          # early-stage deal closing within this many days = slip risk
    early_max_rank: int = 2      # ranks 1-2 are "early"
    big_deal: float = 30000      # large-deal threshold ($)
    plans: dict = field(default_factory=lambda: {"Northstar": 80000, "Fieldstone": 55000})
    exclude_ids: tuple = ("O-25017",)

    @property
    def plan_total(self) -> float:
        return float(sum(self.plans.values()))


# ---------------------------------------------------------------- loading
def load_case(path: str | Path) -> dict[str, pd.DataFrame]:
    """Read the synthetic case workbook (headers sit on row 4 of each sheet)."""
    xl = pd.ExcelFile(path)
    opps = pd.read_excel(xl, "B2B Opportunities", header=3)
    for c in ["Created Date", "Expected Close Date"]:
        opps[c] = pd.to_datetime(opps[c])
    channel = pd.read_excel(xl, "B2C Channel Data", header=3)
    finance = pd.read_excel(xl, "B2C Finance Totals", header=3)
    initiatives = pd.read_excel(xl, "Initiatives", header=3)
    for df in (channel, finance):
        df["Month"] = df["Month"].astype(str)
    return {"opps": opps, "channel": channel, "finance": finance, "initiatives": initiatives}


# ---------------------------------------------------------------- B2B prep
def prepare_opps(opps: pd.DataFrame, a: Assumptions) -> pd.DataFrame:
    """Add the same flags as the workbook's Opportunities tab."""
    df = opps.copy()
    df["Duplicate"] = df.duplicated(keep="first")
    df["Manual exclude"] = df["Opportunity ID"].isin(a.exclude_ids)
    df["Include in history"] = (df["Status"] != "Open") & ~df["Duplicate"] & ~df["Manual exclude"]
    df["Won (incl.)"] = df["Include in history"] & (df["Status"] == "Won")
    df["Cycle days"] = (df["Expected Close Date"] - df["Created Date"]).dt.days
    df["Close year"] = df["Expected Close Date"].dt.year
    df["Close qtr"] = df["Expected Close Date"].dt.quarter
    df["Size band"] = np.where(df["CRM Amount ($)"] >= a.big_deal, "Large", "Small")
    df["Q4-26 open pipeline"] = (
        (df["Status"] == "Open") & ~df["Duplicate"] & ~df["Manual exclude"]
        & df["Expected Close Date"].between(Q4_START, Q4_END)
    )
    keys = list(zip(df["Brand"], df["Local Stage"]))
    df["Common stage"] = [STAGE_MAP.get(k, ("", None))[0] if s == "Open" else "" for k, s in zip(keys, df["Status"])]
    df["Rank"] = [STAGE_MAP.get(k, ("", None))[1] if s == "Open" else None for k, s in zip(keys, df["Status"])]
    return df


def brand_history(df: pd.DataFrame) -> pd.DataFrame:
    """Win rates and cycle by brand from included closed deals."""
    rows = []
    for b in BRANDS_B2B:
        d = df[(df["Brand"] == b) & df["Include in history"]]
        w = d[d["Won (incl.)"]]
        big = d[d["Size band"] == "Large"]
        rows.append({
            "Brand": b,
            "Closed deals": len(d),
            "Won deals": len(w),
            "Win rate (count)": len(w) / len(d) if len(d) else 0.0,
            "Closed $": d["CRM Amount ($)"].sum(),
            "Won $": w["CRM Amount ($)"].sum(),
            "Win rate ($)": w["CRM Amount ($)"].sum() / d["CRM Amount ($)"].sum() if len(d) else 0.0,
            "Avg won cycle (days)": w["Cycle days"].mean() if len(w) else np.nan,
            "Large-deal win rate": big["Won (incl.)"].mean() if len(big) else 0.0,
            "Large deals closed": len(big),
        })
    return pd.DataFrame(rows).set_index("Brand")


def win_rate_by(df: pd.DataFrame, col: str, by_brand: bool = False) -> pd.DataFrame:
    keys = ["Brand", col] if by_brand else [col]
    d = df[df["Include in history"]]
    g = d.groupby(keys).agg(**{"Closed deals": ("Opportunity ID", "count"), "Won deals": ("Won (incl.)", "sum")}).reset_index()
    g["Win rate"] = g["Won deals"] / g["Closed deals"]
    return g.sort_values("Win rate", ascending=False)


def response_speed(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["Include in history"]]
    out = d.groupby("Status")["First Response (days)"].agg(["mean", "count"]).rename(
        columns={"mean": "Avg first response (days)", "count": "Records with a value"})
    return out.reindex(["Won", "Lost"])


def quarterly_bookings(df: pd.DataFrame) -> pd.DataFrame:
    w = df[df["Won (incl.)"]].copy()
    w["Quarter"] = w["Close year"].astype(str) + " Q" + w["Close qtr"].astype(str)
    g = w.groupby(["Quarter", "Brand"])["CRM Amount ($)"].sum().reset_index()
    quarters = [f"{y} Q{q}" for y in (2024, 2025, 2026) for q in (1, 2, 3, 4) if not (y == 2026 and q == 4)]
    full = pd.MultiIndex.from_product([quarters, BRANDS_B2B], names=["Quarter", "Brand"])
    return g.set_index(["Quarter", "Brand"]).reindex(full, fill_value=0).reset_index()


def q4_history(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for y in (2024, 2025):
        q4 = df[df["Include in history"] & (df["Close year"] == y) & (df["Close qtr"] == 4)]
        won = q4[q4["Won (incl.)"]]
        r = {"Year": str(y)}
        for b in BRANDS_B2B:
            r[b] = won.loc[won["Brand"] == b, "CRM Amount ($)"].sum()
        r["Total won"] = won["CRM Amount ($)"].sum()
        r["Q4 closed (won + lost)"] = q4["CRM Amount ($)"].sum()
        r["Q4 $ conversion"] = r["Total won"] / r["Q4 closed (won + lost)"] if r["Q4 closed (won + lost)"] else 0.0
        rows.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- forecast
def forecast(df: pd.DataFrame, a: Assumptions) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deal-level low / base / high and brand roll-up vs plan."""
    hist = brand_history(df)
    deals = df[df["Q4-26 open pipeline"]].copy()
    deals["Days to close"] = (deals["Expected Close Date"] - AS_OF).dt.days
    deals["Brand $ win rate"] = deals["Brand"].map(hist["Win rate ($)"])
    deals["Stage weight"] = deals["Rank"].map(a.stage_weights).astype(float)
    avg_cycle = deals["Brand"].map(hist["Avg won cycle (days)"])
    early = deals["Rank"] <= a.early_max_rank
    deals["Slip risk"] = (deals["Cycle days"] < a.short_cycle * avg_cycle) | (early & (deals["Days to close"] <= a.near_days))
    base = np.minimum(a.cap, deals["Brand $ win rate"] * deals["Stage weight"])
    deals["Base probability"] = base * np.where(deals["Slip risk"], a.slip, 1.0)
    big_wr = deals["Brand"].map(hist["Large-deal win rate"])
    is_big = deals["CRM Amount ($)"] >= a.big_deal
    deals["Low probability"] = np.where(early, 0.0, np.where(is_big, np.minimum(deals["Base probability"], big_wr), deals["Base probability"]))
    deals["High probability"] = deals["Brand"].map(hist["Win rate (count)"])
    for case in ("Base", "Low", "High"):
        deals[f"{case} ($)"] = deals["CRM Amount ($)"] * deals[f"{case} probability"]
    deals = deals.sort_values(["Base ($)"], ascending=False).reset_index(drop=True)

    dist = outcome_distribution(deals)
    rows = []
    for b in BRANDS_B2B + ["Total"]:
        d = deals if b == "Total" else deals[deals["Brand"] == b]
        plan = a.plan_total if b == "Total" else a.plans[b]
        tot_col = "Total" if b == "Total" else b
        rows.append({
            "Brand": b, "Plan": plan, "Open pipeline": d["CRM Amount ($)"].sum(),
            "Low": d["Low ($)"].sum(), "Base": d["Base ($)"].sum(), "High": d["High ($)"].sum(),
            "Chance of plan": float(dist.loc[dist[tot_col] >= plan, "Probability"].sum()),
        })
    roll = pd.DataFrame(rows).set_index("Brand")
    roll["Coverage"] = roll["Open pipeline"] / roll["Plan"]
    roll["Base vs plan"] = roll["Base"] - roll["Plan"]
    return deals, roll


def outcome_distribution(deals: pd.DataFrame, max_exact: int = 18, sims: int = 200_000, seed: int = 7) -> pd.DataFrame:
    """Every win/lose combination (exact for <= max_exact deals; Monte Carlo above)."""
    p = deals["Base probability"].to_numpy(float)
    amt = deals["CRM Amount ($)"].to_numpy(float)
    n = len(p)
    if n <= max_exact:
        bits = (np.arange(2 ** n)[:, None] >> np.arange(n)) & 1
        prob = np.prod(np.where(bits == 1, p, 1 - p), axis=1)
    else:
        rng = np.random.default_rng(seed)
        bits = (rng.random((sims, n)) < p).astype(int)
        prob = np.full(sims, 1 / sims)
    out = pd.DataFrame({"Probability": prob})
    for b in BRANDS_B2B:
        out[b] = bits @ (amt * (deals["Brand"].to_numpy() == b))
    out["Total"] = out[BRANDS_B2B].sum(axis=1)
    return out


def survival_curve(dist: pd.DataFrame, col: str = "Total", step: int = 2500, top: int | None = None) -> pd.DataFrame:
    top = top or int(np.ceil(dist[col].max() / step) * step)
    xs = np.arange(0, top + step, step)
    vals = dist[col].to_numpy(); pr = dist["Probability"].to_numpy()
    return pd.DataFrame({"Bookings at least": xs, "Probability": [pr[vals >= x].sum() for x in xs]})


# ---------------------------------------------------------------- B2C
def channel_summary(channel: pd.DataFrame) -> pd.DataFrame:
    g = channel.groupby("Channel")[["Spend ($)", "Platform Purchases", "Platform Revenue ($)", "GA4 Last-Click Purchases", "GA4 Revenue ($)"]].sum()
    g["Platform ROAS"] = g["Platform Revenue ($)"] / g["Spend ($)"]
    g["GA4 ROAS"] = g["GA4 Revenue ($)"] / g["Spend ($)"]
    g["Platform ÷ GA4 purchases"] = g["Platform Purchases"] / g["GA4 Last-Click Purchases"]
    g["Rank: platform"] = g["Platform ROAS"].rank(ascending=False).astype(int)
    g["Rank: GA4"] = g["GA4 ROAS"].rank(ascending=False).astype(int)
    return g.sort_values("Spend ($)", ascending=False)


def brand_month_vs_finance(channel: pd.DataFrame, finance: pd.DataFrame) -> pd.DataFrame:
    g = channel.groupby(["Month", "Brand"])[["Spend ($)", "Platform Purchases", "Platform Revenue ($)", "GA4 Revenue ($)"]].sum().reset_index()
    m = g.merge(finance, on=["Month", "Brand"], how="right")
    m["Platform rev % of Finance gross"] = m["Platform Revenue ($)"] / m["Gross Revenue ($)"]
    m["GA4 rev % of Finance gross"] = m["GA4 Revenue ($)"] / m["Gross Revenue ($)"]
    m["Platform purchases % of orders"] = m["Platform Purchases"] / m["Finance Orders"]
    m["Net revenue ÷ paid spend"] = m["Net Revenue ($)"] / m["Spend ($)"]
    m["Refunds % of gross"] = m["Refunds and Cancellations ($)"] / m["Gross Revenue ($)"]
    return m


# ---------------------------------------------------------------- data quality
DATA_ISSUES = pd.DataFrame([
    ("Stage definitions differ by brand", "All open deals", "Mapped to a 5-step common ladder (Stage Map)", "High", "Sales Ops + CRM stage-definitions initiative"),
    ("No stage or close-date history", "All", "Conversion, velocity and slippage not calculated", "High", "CRM admin"),
    ("Exact duplicate record", "O-26016", "Second row removed", "Medium", "Sales Ops"),
    ("Won with $0 closed amount; blank response", "O-25017", "Excluded from win rates (toggle in sidebar)", "Low-medium", "Northstar sales owner"),
    ("Closed amount mixes annual and multi-year values", "O-24003, O-25003", "CRM amount used as annual value", "Medium", "Finance + Sales Ops"),
    ("Fieldstone closed deals keep last active stage", "All Fieldstone closed", "Status used for outcomes", "Medium", "Sales Ops"),
    ("Lead source Unknown or blank first response", "O-24004, O-26009, O-26012, O-25017", "Kept; averages ignore blanks", "Low", "Marketing Ops"),
    ("No unconverted leads; no Meadow B2B rows", "Extract scope", "Lead-to-revenue and Meadow B2B not calculable", "Medium", "RevOps"),
    ("Plan basis not stated", "Q4 plan", "Assumed annual; all open deals are 12-month", "Low", "Finance"),
], columns=["Issue", "Records", "Treatment", "Impact", "Owner to fix"])


def flagged_records(df: pd.DataFrame) -> pd.DataFrame:
    reasons = []
    for _, r in df.iterrows():
        why = []
        if r["Duplicate"]: why.append("Duplicate")
        if r["Manual exclude"]: why.append("Manually excluded")
        if r["Status"] == "Won" and (pd.isna(r["Closed Amount ($)"]) or r["Closed Amount ($)"] == 0): why.append("Won at $0")
        if r["Lead Source"] == "Unknown" or pd.isna(r["Lead Source"]): why.append("Unknown source")
        if pd.isna(r["First Response (days)"]): why.append("No response logged")
        if r["Status"] != "Open" and pd.notna(r["Closed Amount ($)"]) and r["Closed Amount ($)"] > r["CRM Amount ($)"]: why.append("Closed > CRM (multi-year?)")
        reasons.append(", ".join(why))
    out = df.assign(Flags=reasons)
    return out[out["Flags"] != ""][["Opportunity ID", "Brand", "Status", "Local Stage", "CRM Amount ($)", "Closed Amount ($)", "Contract Term (months)", "Lead Source", "First Response (days)", "Flags"]]
