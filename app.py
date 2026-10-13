"""KnowFully case: Q4 2026 commercial view (Streamlit prototype).

Run:  streamlit run app.py
Data: data/Synthetic_Case_Data_1.xlsx (synthetic case data)
Assumptions are fixed at the workbook defaults (see forecast.Assumptions).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import forecast as F

# ---------------------------------------------------------------- brand tokens
SLATE = "#233E4F"       # brand slate: headers, reference lines (plan)
TEXT_2 = "#4A5B66"
TRACK = "#C9DCDE"       # light teal-gray track behind values
GRID = "#E1E8EA"
# Data-series colors: brand-derived, validated for colorblind separation and contrast.
BRAND_COLORS = {"Northstar": "#008A9E", "Fieldstone": "#B57F00"}
SOURCE_COLORS = {"Platform": "#5568C0", "GA4": "#B57F00"}

DATA_PATH = Path(__file__).parent / "data" / "Synthetic_Case_Data_1.xlsx"

st.set_page_config(page_title="KnowFully case · Q4 commercial view", page_icon="💡", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown(
    """
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800&family=Open+Sans:wght@400;600;700&display=swap" rel="stylesheet">
<style>
html, body, [class*="css"], .stMarkdown, .stText, p, li, label { font-family: 'Open Sans', Arial, sans-serif; }
h1, h2, h3, h4, [data-testid="stMetricLabel"] p { font-family: 'Montserrat', Arial, sans-serif !important; color: #233E4F; }
[data-testid="stMetricValue"] { font-family: 'Montserrat', Arial, sans-serif; font-weight: 700; color: #233E4F; }
.kf-band { background:#233E4F; color:#FFFFFF; border-radius:12px; padding:18px 24px; margin-bottom:8px;
           display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; }
.kf-band .t { font-family:'Montserrat',Arial,sans-serif; font-weight:800; font-size:22px; letter-spacing:.5px; }
.kf-band .s { color:#C9D6DC; font-size:14px; }
.kf-band .gold { color:#DAA22A; }
.kf-flag { border-left:6px solid #DAA22A; background:#FBF3E0; color:#233E4F; border-radius:8px; padding:10px 14px; margin:6px 0; }
.kf-flag.info { border-left-color:#008A9E; background:#E3EFF0; }
.kf-flag b { font-family:'Montserrat',Arial,sans-serif; }
.kf-note { color:#5F6F78; font-size:13px; }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- helpers
def k(x: float, d: int = 0) -> str:
    return f"${x / 1000:,.{d}f}K"


def signed_k(x: float) -> str:
    return ("+" if x >= 0 else "-") + k(abs(x), 1)


def md(text: str) -> str:
    """Escape $ so Streamlit doesn't render text between two dollar signs as LaTeX math."""
    return text.replace("$", "\\$")


def pct(x: float, d: int = 0) -> str:
    return f"{x * 100:.{d}f}%"


def vl(spec: dict, data: pd.DataFrame | None, height: int = 300) -> None:
    """Render a Vega-Lite spec with shared brand config (Streamlit bundles Vega-Lite; no extra installs)."""
    base = {
        "width": "container",
        "height": height,
        "config": {
            "font": "Open Sans",
            "axis": {"labelColor": TEXT_2, "titleColor": TEXT_2, "gridColor": GRID, "domainColor": "#BCCBD0",
                     "tickColor": "#BCCBD0", "labelFontSize": 12, "titleFontSize": 12, "titleFontWeight": 600},
            "legend": {"labelColor": TEXT_2, "titleColor": TEXT_2, "orient": "top", "labelFontSize": 12},
            "view": {"stroke": None},
        },
    }
    base.update(spec)
    st.vega_lite_chart(data, base)


def flag(text: str, level: str = "warn") -> None:
    icon, label = ("⚠️", "Watch") if level == "warn" else ("ℹ️", "Note")
    css = "kf-flag" if level == "warn" else "kf-flag info"
    st.markdown(f'<div class="{css}">{icon} <b>{label}:</b> {md(text)}</div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load(path: str) -> dict:
    return F.load_case(path)


# ---------------------------------------------------------------- data (fixed assumptions)
case = load(str(DATA_PATH))
a = F.Assumptions()
opps = F.prepare_opps(case["opps"], a)
deals, roll = F.forecast(opps, a)
dist = F.outcome_distribution(deals)
hist = F.brand_history(opps)
q4h = F.q4_history(opps)
bm = F.brand_month_vs_finance(case["channel"], case["finance"])
tot = roll.loc["Total"]

# ---------------------------------------------------------------- header
st.markdown(
    """<div class="kf-band"><div><div class="t">Q4 2026 commercial view</div>
<div class="s">Revenue Operations &amp; BI case prototype · <span class="gold">as of Sept 30, 2026</span></div></div>
<div class="s">Synthetic case data · built by Matt Rispoli</div></div>""",
    unsafe_allow_html=True,
)

tab_exec, tab_fc, tab_b2c = st.tabs(["Executive view", "Q4 forecast", "B2C measurement"])

# ================================================================= EXECUTIVE VIEW
with tab_exec:
    sep = bm[bm["Month"] == "2026-09"]; aug = bm[bm["Month"] == "2026-08"]
    c = st.columns(6)
    c[0].metric("Q4 base forecast", k(tot["Base"]), f"{signed_k(tot['Base vs plan'])} vs plan")
    c[1].metric("Chance of reaching plan", pct(tot["Chance of plan"]),
                help="Exact probability across every win/lose combination of the open Q4 deals.")
    c[2].metric("Forecast range", md(f"{k(tot['Low'])}–{k(tot['High'])}"), help="Low and high cases; see Q4 forecast tab.")
    c[3].metric("Pipeline coverage", f"{tot['Coverage']:.1f}x", help="Open Q4 pipeline ÷ plan.")
    c[4].metric("B2C net revenue, Sep", k(sep["Net Revenue ($)"].sum()),
                f"{signed_k(sep['Net Revenue ($)'].sum() - aug['Net Revenue ($)'].sum())} vs Aug")
    c[5].metric("Net revenue ÷ paid spend, Sep", f"{sep['Net Revenue ($)'].sum() / sep['Spend ($)'].sum():.1f}x",
                help="Blended efficiency from Finance. Includes unpaid orders, so it is not channel ROAS.")

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Forecast vs plan by brand")
        rng = roll.reset_index()[["Brand", "Low", "Base", "High", "Plan", "Chance of plan"]]
        rng["Chance"] = rng["Chance of plan"].map(lambda v: pct(v))
        tip = [{"field": "Brand"}, {"field": "Low", "format": "$,.0f"}, {"field": "Base", "format": "$,.0f"},
               {"field": "High", "format": "$,.0f"}, {"field": "Plan", "format": "$,.0f"}, {"field": "Chance", "title": "Chance of plan"}]
        vl({
            "layer": [
                {"mark": {"type": "rule", "strokeWidth": 10, "strokeCap": "round", "color": TRACK},
                 "encoding": {"x": {"field": "Low", "type": "quantitative", "title": "Q4 bookings ($)", "axis": {"format": "$,.0f"}},
                              "x2": {"field": "High"}, "tooltip": tip}},
                {"mark": {"type": "tick", "thickness": 3, "size": 34, "color": SLATE},
                 "encoding": {"x": {"field": "Plan", "type": "quantitative"}, "tooltip": tip}},
                {"mark": {"type": "point", "filled": True, "size": 220, "color": "#008A9E", "stroke": "#FFFFFF", "strokeWidth": 2},
                 "encoding": {"x": {"field": "Base", "type": "quantitative"}, "tooltip": tip}},
                {"mark": {"type": "text", "align": "left", "dx": 12, "dy": -14, "fontSize": 12, "color": TEXT_2},
                 "encoding": {"x": {"field": "Base", "type": "quantitative"}, "text": {"field": "Chance"}}},
            ],
            "encoding": {"y": {"field": "Brand", "type": "nominal", "sort": ["Northstar", "Fieldstone", "Total"], "title": None,
                               "axis": {"labelFontSize": 13}}},
        }, rng, height=210)
        st.markdown('<p class="kf-note">Bar = low–high range · teal dot = base forecast (label = chance of plan) · dark tick = plan</p>',
                    unsafe_allow_html=True)

        st.subheader("Initiatives: delivery vs outcome")
        ini = case["initiatives"][["Initiative", "Brand", "Milestone status", "Observed outcome"]]
        st.dataframe(ini, hide_index=True)

    with right:
        st.subheader("Exception flags")
        for b in F.BRANDS_B2B:
            p = roll.loc[b, "Chance of plan"]
            if p < 0.5:
                flag(f"{b} has a {pct(p, 1)} chance of reaching plan, below 50%.")
        for b in F.BRANDS_B2B:
            bb = deals[deals["Brand"] == b]
            if len(bb) and bb["Base ($)"].sum() > 0:
                top = bb.iloc[0]; share = top["Base ($)"] / bb["Base ($)"].sum()
                if share > 0.30:
                    flag(f"{top['Opportunity ID']} is {pct(share)} of {b}'s base forecast.")
        sl = deals[deals["Slip risk"]]
        if len(sl):
            flag(f"{len(sl)} deals ({k(sl['CRM Amount ($)'].sum())}) have close dates shorter than history supports.")
        fs_big = deals[(deals["Brand"] == "Fieldstone") & (deals["CRM Amount ($)"] >= a.big_deal)]
        if len(fs_big):
            flag(f"Fieldstone has won {pct(hist.loc['Fieldstone', 'Large-deal win rate'])} of closed deals at {k(a.big_deal)}+; "
                 f"{len(fs_big)} such deals ({k(fs_big['CRM Amount ($)'].sum())}) are open in Q4.")
        best_q4 = q4h["Total won"].max()
        if a.plan_total > 1.5 * best_q4:
            flag(f"Plan is {a.plan_total / best_q4:.1f}x the best prior Q4 ({k(best_q4)}).")
        flag("CRM stage definitions: draft approved, Finance validation pending; no common-stage report yet.", "info")

        st.subheader("Review cadence")
        st.markdown("- **Monthly:** leadership reviews this view\n- **Weekly:** pipeline call, owned by Sales\n"
                    "- **Quarterly:** forecast vs actual, with Finance")

# ================================================================= Q4 FORECAST
with tab_fc:
    st.subheader("Roll-up vs plan")
    show = roll[["Plan", "Open pipeline", "Coverage", "Low", "Base", "High", "Base vs plan", "Chance of plan"]].copy()
    st.dataframe(show.style.format({"Plan": "${:,.0f}", "Open pipeline": "${:,.0f}", "Coverage": "{:.1f}x", "Low": "${:,.0f}",
                                    "Base": "${:,.0f}", "High": "${:,.0f}", "Base vs plan": "${:+,.0f}", "Chance of plan": "{:.1%}"}))

    l2, r2 = st.columns(2, gap="large")
    with l2:
        st.subheader("Chance of booking at least…")
        curve = F.survival_curve(dist, "Total", step=2500)
        curve["Label"] = curve["Probability"].map(lambda v: pct(v))
        plan_df = pd.DataFrame({"Plan": [a.plan_total], "Label": [f"Plan {k(a.plan_total)}"]})
        vl({
            "layer": [
                {"data": {"values": curve.to_dict("records")},
                 "params": [{"name": "hover", "select": {"type": "point", "fields": ["Bookings at least"], "nearest": True,
                                                         "on": "mouseover", "clear": "mouseout"}}],
                 "mark": {"type": "line", "strokeWidth": 2, "color": "#008A9E", "interpolate": "step-after"},
                 "encoding": {"x": {"field": "Bookings at least", "type": "quantitative", "title": "Total Q4 bookings at least ($)",
                                    "axis": {"format": "$,.0f"}},
                              "y": {"field": "Probability", "type": "quantitative", "title": "Probability", "axis": {"format": "%"},
                                    "scale": {"domain": [0, 1]}}}},
                {"data": {"values": curve.to_dict("records")},
                 "mark": {"type": "point", "filled": True, "size": 80, "color": "#008A9E", "stroke": "#FFFFFF", "strokeWidth": 2},
                 "encoding": {"x": {"field": "Bookings at least", "type": "quantitative"},
                              "y": {"field": "Probability", "type": "quantitative"},
                              "opacity": {"condition": {"param": "hover", "empty": False, "value": 1}, "value": 0},
                              "tooltip": [{"field": "Bookings at least", "format": "$,.0f"}, {"field": "Label", "title": "Probability"}]}},
                {"data": {"values": plan_df.to_dict("records")},
                 "mark": {"type": "rule", "strokeDash": [6, 4], "strokeWidth": 2, "color": SLATE},
                 "encoding": {"x": {"field": "Plan", "type": "quantitative"}}},
                {"data": {"values": plan_df.to_dict("records")},
                 "mark": {"type": "text", "align": "left", "dx": 6, "y": 8, "fontSize": 12, "color": SLATE},
                 "encoding": {"x": {"field": "Plan", "type": "quantitative"}, "text": {"field": "Label"}}},
            ],
        }, None, height=300)
        st.caption(md(f"At plan ({k(a.plan_total)}): {pct(tot['Chance of plan'])}. Assumes deals win or lose independently."))
    with r2:
        st.subheader("Base expected value by deal")
        dd = deals[["Opportunity ID", "Brand", "Common stage", "CRM Amount ($)", "Base ($)", "Base probability", "Slip risk"]].copy()
        dd["Prob"] = dd["Base probability"].map(lambda v: pct(v))
        dd["Slip"] = dd["Slip risk"].map({True: "Slip risk", False: "—"})
        tip = [{"field": "Opportunity ID", "title": "Deal"}, {"field": "Brand"}, {"field": "Common stage"},
               {"field": "CRM Amount ($)", "format": "$,.0f"}, {"field": "Base ($)", "format": "$,.0f", "title": "Base expected"},
               {"field": "Prob", "title": "Base probability"}, {"field": "Slip"}]
        vl({
            "layer": [
                {"mark": {"type": "bar", "color": TRACK, "cornerRadiusEnd": 4, "height": 14},
                 "encoding": {"x": {"field": "CRM Amount ($)", "type": "quantitative", "title": "$ (track = CRM amount)",
                                    "axis": {"format": "$,.0f"}}, "tooltip": tip}},
                {"mark": {"type": "bar", "cornerRadiusEnd": 4, "height": 14},
                 "encoding": {"x": {"field": "Base ($)", "type": "quantitative"},
                              "color": {"field": "Brand", "type": "nominal",
                                        "scale": {"domain": list(BRAND_COLORS), "range": list(BRAND_COLORS.values())},
                                        "legend": {"title": None}},
                              "tooltip": tip}},
                {"mark": {"type": "text", "align": "left", "dx": 6, "fontSize": 11, "color": TEXT_2},
                 "encoding": {"x": {"field": "CRM Amount ($)", "type": "quantitative"}, "text": {"field": "Prob"}}},
            ],
            "encoding": {"y": {"field": "Opportunity ID", "type": "nominal", "sort": dd["Opportunity ID"].tolist(), "title": None}},
        }, dd, height=330)

    st.subheader("Prior Q4 performance")
    st.dataframe(q4h.style.format({"Northstar": "${:,.0f}", "Fieldstone": "${:,.0f}", "Total won": "${:,.0f}",
                                   "Q4 closed (won + lost)": "${:,.0f}", "Q4 $ conversion": "{:.0%}"}), hide_index=True)
    need = a.plan_total / tot["Open pipeline"] if tot["Open pipeline"] else 0
    st.caption(f"Plan needs {pct(need)} of open Q4 pipeline to convert; prior Q4s converted "
               f"{pct(q4h['Q4 $ conversion'].min())}–{pct(q4h['Q4 $ conversion'].max())}.")

    with st.expander("How the forecast works and data notes"):
        st.markdown(
            "- **Base:** brand historical dollar win rate × common-stage weight (0.5x–1.6x), capped at 90%, "
            "halved when the close date looks optimistic.\n"
            "- **Low:** early-stage deals contribute nothing in Q4; large deals are held to the brand's large-deal win rate.\n"
            "- **High (\"CRM as-is\"):** brand historical deal-count win rate on every open deal.\n"
            "- **Chance of plan:** exact probability across every win/lose combination, assuming independence.\n"
            "- **Data treatment:** duplicate O-26016 removed; O-25017 (Won at $0) excluded; CRM amount used as annual value.")
        st.dataframe(F.DATA_ISSUES[["Issue", "Records", "Treatment"]], hide_index=True)

# ================================================================= B2C
with tab_b2c:
    cs = F.channel_summary(case["channel"])
    l5, r5 = st.columns([3, 2], gap="large")
    with l5:
        st.subheader("ROAS by channel: platform vs GA4")
        long = pd.concat([
            pd.DataFrame({"Channel": cs.index, "Source": "Platform", "ROAS": cs["Platform ROAS"].values}),
            pd.DataFrame({"Channel": cs.index, "Source": "GA4", "ROAS": cs["GA4 ROAS"].values}),
        ])
        long["Label"] = long["ROAS"].map(lambda v: f"{v:.2f}x")
        vl({
            "layer": [
                {"mark": {"type": "rule", "color": TRACK, "strokeWidth": 4},
                 "encoding": {"x": {"aggregate": "min", "field": "ROAS", "type": "quantitative",
                                    "title": "Attributed revenue ÷ spend", "axis": {"format": ".1f"}},
                              "x2": {"aggregate": "max", "field": "ROAS"}}},
                {"mark": {"type": "point", "filled": True, "size": 200, "stroke": "#FFFFFF", "strokeWidth": 2},
                 "encoding": {"x": {"field": "ROAS", "type": "quantitative", "scale": {"zero": True}},
                              "color": {"field": "Source", "type": "nominal",
                                        "scale": {"domain": list(SOURCE_COLORS), "range": list(SOURCE_COLORS.values())},
                                        "legend": {"title": None}},
                              "shape": {"field": "Source", "type": "nominal", "scale": {"domain": ["Platform", "GA4"], "range": ["circle", "square"]},
                                        "legend": None},
                              "tooltip": [{"field": "Channel"}, {"field": "Source"}, {"field": "Label", "title": "ROAS"}]}},
                {"mark": {"type": "text", "dy": -16, "fontSize": 12, "color": TEXT_2},
                 "encoding": {"x": {"field": "ROAS", "type": "quantitative"}, "text": {"field": "Label"}}},
            ],
            "encoding": {"y": {"field": "Channel", "type": "nominal", "sort": cs.index.tolist(), "title": None,
                               "axis": {"labelFontSize": 13}}},
        }, long, height=230)
        st.caption("Aug–Sep 2026, all brands. Platforms claim shared customers, so their claims overlap; "
                   "GA4 last-click undercounts upper-funnel channels.")
    with r5:
        st.subheader("Would I move the next dollar?")
        st.markdown("**Not on this data.** The answer depends on which source you believe.\n\n"
                    "**One test:** Paid Social geo holdout for 4–6 weeks, read in Finance net revenue (test vs control regions).\n\n"
                    "**Alongside:** pass an order ID through checkout so platform and GA4 claims can be matched to Finance orders.")

    st.subheader("Brand and month vs Finance (source of record)")
    bmf = bm[["Month", "Brand", "Spend ($)", "Net Revenue ($)", "Platform rev % of Finance gross",
              "GA4 rev % of Finance gross", "Net revenue ÷ paid spend"]]
    st.dataframe(bmf.style.format({"Spend ($)": "${:,.0f}", "Net Revenue ($)": "${:,.0f}",
                                   "Platform rev % of Finance gross": "{:.0%}", "GA4 rev % of Finance gross": "{:.0%}",
                                   "Net revenue ÷ paid spend": "{:.1f}x"}), hide_index=True)
    st.markdown('<p class="kf-note">Finance revenue includes unpaid orders, so revenue ÷ spend is blended efficiency, not channel ROAS.</p>',
                unsafe_allow_html=True)
