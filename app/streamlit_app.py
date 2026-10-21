"""College ROI Explorer: Streamlit dashboard.

Run locally:   streamlit run app/streamlit_app.py
Reads exports/ (real data, committed to the repo) and falls back to
data/demo/exports (synthetic) with a warning banner.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ROOT / "exports"
DEMO_DIR = ROOT / "data" / "demo" / "exports"

# Validated reference palette (light surface). Slots 1-3 are safe together
# for every chart form, so no chart here uses more than three categorical hues.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
RED = "#e34948"
MUTED = "#c3c2b7"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e1e0d9"
DIVERGING = [[0.0, "#b8322f"], [0.25, RED], [0.5, "#f0efec"], [0.75, BLUE], [1.0, "#184f95"]]
FONT = dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', color=INK, size=13)

st.set_page_config(page_title="College ROI Explorer", page_icon="🎓", layout="wide")


# --- Data -----------------------------------------------------------------------


@st.cache_data
def load() -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = REAL_DIR if (REAL_DIR / "schools.parquet").exists() else DEMO_DIR
    if not (base / "schools.parquet").exists():
        st.error("No data found. Run `python -m scorecard all` (or `demo`) first.")
        st.stop()
    meta = json.loads((base / "metadata.json").read_text())
    return (
        meta,
        pd.read_parquet(base / "schools.parquet"),
        pd.read_parquet(base / "model_coefficients.parquet"),
        pd.read_parquet(base / "peer_group_profile.parquet"),
        pd.read_parquet(base / "hbcu_summary.parquet"),
    )


def style(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        font=FONT,
        margin=dict(l=8, r=8, t=36, b=8),
        plot_bgcolor="#fcfcfb",
        paper_bgcolor="#fcfcfb",
        hoverlabel=dict(bgcolor="white", font=FONT),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(
        gridcolor=GRID, zerolinecolor=MUTED, linecolor=MUTED, tickfont=dict(color=INK_2)
    )
    fig.update_yaxes(
        gridcolor=GRID, zerolinecolor=MUTED, linecolor=MUTED, tickfont=dict(color=INK_2)
    )
    return fig


def money(x: float | None) -> str:
    return "n/a" if pd.isna(x) else f"${x:,.0f}"


def pct(x: float | None, signed: bool = False) -> str:
    if pd.isna(x):
        return "n/a"
    return f"{x:+.1%}" if signed else f"{x:.0%}"


meta, schools, coefs, profiles, hbcu = load()

# --- Header + filters ---------------------------------------------------------------

st.title("Is College Worth It?")
st.caption(
    f"Return on investment for {meta['n_schools']:,} U.S. bachelor's-granting colleges · "
    "U.S. Dept. of Education College Scorecard · earnings adjusted for state cost of living "
    f"(BEA) · updated {meta['generated_at'][:10]}"
)
if meta.get("source") != "api":
    st.warning(
        "**Demo mode: synthetic data.** These schools and numbers are fake and exist only to "
        "show how the dashboard works. Run `python -m scorecard all` with an API key "
        "for real data.",
        icon="⚠️",
    )

f1, f2, f3 = st.columns([2, 2, 1])
states = f1.multiselect("State", sorted(schools["state"].dropna().unique()))
sectors = f2.multiselect("Sector", sorted(schools["ownership"].dropna().unique()))
hbcu_only = f3.toggle("HBCUs only")

view = schools.copy()
if states:
    view = view[view["state"].isin(states)]
if sectors:
    view = view[view["ownership"].isin(sectors)]
if hbcu_only:
    view = view[view["is_hbcu"]]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Schools", f"{len(view):,}")
k2.metric("Median earnings, 10 yrs (COL-adj.)", money(view["earnings_10yr_adj"].median()))
k3.metric("Median debt", money(view["median_debt"].median()))
k4.metric(
    "Median payback",
    f"{view['payback_years'].median():.1f} yrs" if view["payback_years"].notna().any() else "n/a",
)

tabs = st.tabs(["Value-added ranking", "Map", "School explorer", "HBCU analysis", "Peer groups"])

# --- 1. Ranking ------------------------------------------------------------------------

with tabs[0]:
    st.subheader("Which schools beat expectations?")
    st.markdown(
        "**Value added** = how much more (or less) a school's graduates earn than a model "
        "predicts for a school with the same SAT scores, Pell share, selectivity, size, sector "
        "and region. It separates what a school *adds* from *who it admits*."
    )
    n = st.slider("Show top and bottom", 5, 25, 10)
    ranked = view.dropna(subset=["value_added_pct"]).sort_values("value_added_pct")
    if ranked.empty:
        st.info("No schools match these filters.")
    else:
        sel = pd.concat([ranked.head(n), ranked.tail(n)]).drop_duplicates("unitid")
        fig = go.Figure(
            go.Bar(
                x=sel["value_added_pct"],
                y=sel["name"],
                orientation="h",
                marker=dict(
                    color=[BLUE if v >= 0 else RED for v in sel["value_added_pct"]],
                    line=dict(color="#fcfcfb", width=2),
                ),
                text=[pct(v, signed=True) for v in sel["value_added_pct"]],
                textposition="outside",
                textfont=dict(color=INK_2),
                customdata=sel[["state", "earnings_10yr_adj", "predicted_earnings_adj"]],
                hovertemplate="<b>%{y}</b> (%{customdata[0]})<br>Actual: $%{customdata[1]:,.0f}"
                "<br>Predicted: $%{customdata[2]:,.0f}<br>Value added: %{x:+.1%}"
                "<extra></extra>",
            )
        )
        span = float(sel["value_added_pct"].abs().max()) or 0.1
        fig.update_xaxes(
            tickformat="+.0%", title="Earnings vs. prediction", range=[-span * 1.25, span * 1.25]
        )  # room for outside labels
        fig.update_yaxes(title=None)
        st.plotly_chart(style(fig, height=max(380, 24 * len(sel))), width="stretch")

    cols = {
        "value_added_rank": "Rank",
        "name": "School",
        "state": "State",
        "ownership": "Sector",
        "earnings_10yr_adj": "Earnings (adj.)",
        "predicted_earnings_adj": "Predicted",
        "value_added_pct": "Value added",
        "median_debt": "Median debt",
        "payback_years": "Payback (yrs)",
        "peer_group_label": "Peer group",
    }
    st.dataframe(
        view.sort_values("value_added_rank")[list(cols)].rename(columns=cols),
        hide_index=True,
        width="stretch",
        column_config={
            "Earnings (adj.)": st.column_config.NumberColumn(format="$%d"),
            "Predicted": st.column_config.NumberColumn(format="$%d"),
            "Median debt": st.column_config.NumberColumn(format="$%d"),
            "Value added": st.column_config.NumberColumn(format="percent"),
        },
    )
    st.download_button("Download as CSV", view.to_csv(index=False), "college_roi.csv", "text/csv")

# --- 2. Map --------------------------------------------------------------------------

with tabs[1]:
    st.subheader("Where are the over- and under-performers?")
    geo = view.dropna(subset=["lat", "lon", "value_added_pct"])
    if geo.empty:
        st.info("No mappable schools for these filters.")
    else:
        lim = float(geo["value_added_pct"].abs().quantile(0.95)) or 0.1
        fig = go.Figure(
            go.Scattergeo(
                lat=geo["lat"],
                lon=geo["lon"],
                mode="markers",
                marker=dict(
                    size=9,
                    color=geo["value_added_pct"],
                    colorscale=DIVERGING,
                    cmin=-lim,
                    cmax=lim,
                    line=dict(color="#fcfcfb", width=1),
                    colorbar=dict(title="Value added", tickformat="+.0%", thickness=12),
                ),
                customdata=geo[["name", "state", "earnings_10yr_adj", "value_added_pct"]],
                hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                "Earnings: $%{customdata[2]:,.0f}<br>Value added: %{customdata[3]:+.1%}"
                "<extra></extra>",
            )
        )
        fig.update_geos(
            scope="usa",
            showland=True,
            landcolor="#f0efec",
            subunitcolor="#ffffff",
            bgcolor="#fcfcfb",
        )
        st.plotly_chart(style(fig, height=560), width="stretch")
        st.caption(
            "Blue = graduates earn more than predicted; red = less. "
            "Color scale is capped at the 95th percentile so outliers don't wash it out."
        )

# --- 3. School explorer -------------------------------------------------------------

with tabs[2]:
    st.subheader("How does one school compare?")
    options = view.sort_values("name")
    if options.empty:
        st.info("No schools match these filters.")
    else:
        default = (
            int(options["name"].str.contains("Oakwood", case=False).idxmax())
            if options["name"].str.contains("Oakwood", case=False).any()
            else options.index[0]
        )
        name = st.selectbox("School", options["name"], index=options.index.get_loc(default))
        s = options[options["name"] == name].iloc[0]
        peers = schools[schools["peer_group"] == s["peer_group"]]

        a, b, c, d = st.columns(4)
        a.metric(
            "Earnings, 10 yrs (adj.)",
            money(s["earnings_10yr_adj"]),
            f"{s['value_added_pct']:+.1%} vs. predicted"
            if pd.notna(s["value_added_pct"])
            else None,
        )
        b.metric("Median debt", money(s["median_debt"]))
        c.metric(
            "Payback", f"{s['payback_years']:.1f} yrs" if pd.notna(s["payback_years"]) else "n/a"
        )
        d.metric("Graduation rate", pct(s["grad_rate"]))
        st.caption(
            f"{s['city']}, {s['state']} · {s['ownership']}"
            f"{' · HBCU' if s['is_hbcu'] else ''} · Peer group: **{s['peer_group_label']}**"
            f" · Value-added rank {int(s['value_added_rank']):,} of {len(schools):,}"
            if pd.notna(s["value_added_rank"])
            else ""
        )

        metrics = [
            ("earnings_10yr_adj", "Earnings (adj.)"),
            ("median_debt", "Median debt"),
            ("net_price", "Annual net price"),
        ]
        series = [
            (name, BLUE, [s[m] for m, _ in metrics]),
            ("Peer-group median", ORANGE, [peers[m].median() for m, _ in metrics]),
            ("National median", AQUA, [schools[m].median() for m, _ in metrics]),
        ]
        fig = go.Figure()
        for label, color, vals in series:
            fig.add_bar(
                name=label,
                x=[lbl for _, lbl in metrics],
                y=vals,
                marker_color=color,
                marker_line=dict(color="#fcfcfb", width=2),
                text=[money(v) for v in vals],
                textposition="outside",
                textfont=dict(color=INK_2),
                hovertemplate=f"<b>{label}</b><br>%{{x}}: $%{{y:,.0f}}<extra></extra>",
            )
        fig.update_layout(barmode="group", bargap=0.25)
        fig.update_yaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(style(fig), width="stretch")

# --- 4. HBCU analysis ------------------------------------------------------------------

with tabs[3]:
    st.subheader("Do HBCU graduates earn less, or do HBCUs serve different students?")
    gap = coefs[(coefs["term"] == "is_hbcu") & coefs["model"].str.startswith("hbcu_")]
    if gap.empty:
        st.info("Not enough HBCUs with earnings data to estimate the gap.")
    else:
        labels = {
            "hbcu_raw": "Raw gap (no controls)",
            "hbcu_controlled": "Controlled (same SAT, Pell, size, sector, region)",
        }
        gap = gap.assign(
            label=gap["model"].map(labels),
            lo=np.exp(gap["ci_low"]) - 1,
            hi=np.exp(gap["ci_high"]) - 1,
        )
        fig = go.Figure()
        for (_, r), color in zip(gap.iterrows(), [ORANGE, BLUE], strict=False):
            fig.add_trace(
                go.Scatter(
                    x=[r["pct_effect"]],
                    y=[r["label"]],
                    mode="markers+text",
                    name=r["label"],
                    marker=dict(size=14, color=color, line=dict(color="#fcfcfb", width=2)),
                    error_x=dict(
                        type="data",
                        symmetric=False,
                        array=[r["hi"] - r["pct_effect"]],
                        arrayminus=[r["pct_effect"] - r["lo"]],
                        color=color,
                        thickness=2,
                    ),
                    text=[f"{r['pct_effect']:+.1%}"],
                    textposition="top center",
                    textfont=dict(color=INK),
                    hovertemplate=f"<b>{r['label']}</b><br>Effect: {r['pct_effect']:+.1%}<br>"
                    f"95% CI: {r['lo']:+.1%} to {r['hi']:+.1%}<br>"
                    f"p = {r['p_value']:.3g}<extra></extra>",
                )
            )
        fig.add_vline(x=0, line=dict(color=MUTED, width=1))
        fig.update_xaxes(tickformat="+.0%", title="HBCU graduates' earnings vs. non-HBCU")
        fig.update_layout(showlegend=False)
        fig.update_yaxes(range=[-0.6, len(gap) - 0.3])  # headroom for value labels
        st.plotly_chart(style(fig, height=320), width="stretch")

        raw = gap.set_index("model")
        st.markdown(
            f"Without controls, HBCU graduates earn **{raw.loc['hbcu_raw', 'pct_effect']:+.1%}** "
            "relative to non-HBCU graduates. Comparing schools that serve similar students, the "
            f"difference is **{raw.loc['hbcu_controlled', 'pct_effect']:+.1%}** (95% CI "
            f"{raw.loc['hbcu_controlled', 'lo']:+.1%} to {raw.loc['hbcu_controlled', 'hi']:+.1%}). "
            "Bars show 95% confidence intervals with heteroskedasticity-robust (HC3) errors."
        )
    st.markdown("**Raw medians**")
    st.dataframe(
        hbcu.rename(
            columns={
                "group_name": "Group",
                "n_schools": "Schools",
                "median_earnings_10yr": "Earnings",
                "median_earnings_10yr_adj": "Earnings (adj.)",
                "median_debt": "Debt",
                "median_debt_to_earnings": "Debt / earnings",
                "median_pell_rate": "Pell share",
                "median_grad_rate": "Grad rate",
            }
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "Earnings": st.column_config.NumberColumn(format="$%d"),
            "Earnings (adj.)": st.column_config.NumberColumn(format="$%d"),
            "Debt": st.column_config.NumberColumn(format="$%d"),
            "Debt / earnings": st.column_config.NumberColumn(format="%.2f"),
            "Pell share": st.column_config.NumberColumn(format="percent"),
            "Grad rate": st.column_config.NumberColumn(format="percent"),
        },
    )

# --- 5. Peer groups ---------------------------------------------------------------------

with tabs[4]:
    st.subheader("Peer groups: schools that look alike")
    st.markdown(
        "K-means clustering on size, selectivity, net price, Pell share, SAT and "
        "graduation rate. The number of groups was chosen by silhouette score."
    )
    group = st.selectbox("Highlight a peer group", profiles["peer_group_label"])
    pts = view.dropna(subset=["net_price", "earnings_10yr_adj"])
    on = pts[pts["peer_group_label"] == group]
    off = pts[pts["peer_group_label"] != group]
    fig = go.Figure()
    for df_, label, color, size in [(off, "Other schools", MUTED, 7), (on, group, BLUE, 9)]:
        fig.add_trace(
            go.Scatter(
                x=df_["net_price"],
                y=df_["earnings_10yr_adj"],
                mode="markers",
                name=label,
                marker=dict(color=color, size=size, line=dict(color="#fcfcfb", width=1)),
                customdata=df_[["name", "state"]],
                hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>Net price: $%{x:,.0f}"
                "<br>Earnings (adj.): $%{y:,.0f}<extra></extra>",
            )
        )
    fig.update_xaxes(title="Annual net price", tickprefix="$", tickformat=",.0f")
    fig.update_yaxes(title="Earnings 10 yrs after entry (adj.)", tickprefix="$", tickformat=",.0f")
    st.plotly_chart(style(fig, height=480), width="stretch")

    show = profiles.rename(
        columns={
            "peer_group_label": "Peer group",
            "n_schools": "Schools",
            "median_enrollment": "Enrollment",
            "median_admission_rate": "Admit rate",
            "median_net_price": "Net price",
            "median_pell_rate": "Pell share",
            "median_grad_rate": "Grad rate",
            "median_earnings_10yr_adj": "Earnings (adj.)",
            "pct_hbcu": "% HBCU",
        }
    ).drop(columns="peer_group")
    st.dataframe(
        show,
        hide_index=True,
        width="stretch",
        column_config={
            "Admit rate": st.column_config.NumberColumn(format="percent"),
            "Pell share": st.column_config.NumberColumn(format="percent"),
            "Grad rate": st.column_config.NumberColumn(format="percent"),
            "% HBCU": st.column_config.NumberColumn(format="percent"),
            "Net price": st.column_config.NumberColumn(format="$%d"),
            "Earnings (adj.)": st.column_config.NumberColumn(format="$%d"),
            "Enrollment": st.column_config.NumberColumn(format="%d"),
        },
    )

st.divider()
st.caption(
    "Earnings cover federal aid recipients, measured 10 years after entry. Cost-of-living "
    "adjustment uses the school's state, though graduates may live elsewhere. Value added "
    "is a regression residual: a useful signal, not a causal estimate. "
    "Source code: github.com/Daniels-not/college-roi"
)
