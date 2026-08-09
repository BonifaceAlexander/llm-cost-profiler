"""
Local Streamlit dashboard for llm-cost-profiler.

Run with:
    llm-cost-profiler dashboard --sink agent_costs.jsonl

or directly:
    streamlit run src/llm_cost_profiler/dashboard.py -- --sink agent_costs.jsonl
"""
import argparse
import json
import os
import sys
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---- brand palette (matches the project's architecture diagram) ----
BG = "#08090b"
PANEL = "#101319"
LINE = "#23262e"
TEXT = "#e8e9ec"
MUTED = "#8a8f99"
MUTED2 = "#565a63"
BLUE = "#5b8def"
PURPLE = "#9d7bf2"
GREEN = "#5fd68a"
AMBER = "#e8b34f"
RED = "#e0616b"

MODEL_COLORS = [BLUE, PURPLE, GREEN, AMBER, RED, "#4fc3d9", "#e88fd4"]


def _parse_args():
    # Streamlit strips its own flags AND the `--` separator before
    # handing off to the script - sys.argv[1:] here is already just
    # our app-level args (e.g. ['--sink', 'x.jsonl']) in a real
    # `streamlit run` subprocess. (Verified by direct inspection.)
    #
    # Under streamlit.testing.v1.AppTest, though, the script runs
    # in-process, so sys.argv is whatever the *outer* process (e.g.
    # pytest) was invoked with - completely unrelated to this app.
    # We use parse_known_args() so unrecognized argv there is ignored
    # instead of raising, and fall back to env vars in that case.
    argv = sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--sink", default=os.environ.get("LLM_COST_PROFILER_SINK", "llm_costs.jsonl"))
    parser.add_argument("--budget", type=float,
                         default=_env_float("LLM_COST_PROFILER_BUDGET"),
                         help="Optional total budget in USD; a banner shows if exceeded")
    args, _unknown = parser.parse_known_args(argv)
    return args


def _env_float(name):
    val = os.environ.get(name)
    return float(val) if val is not None else None


def load_records(sink_path: str) -> pd.DataFrame:
    rows = []
    skipped = 0
    try:
        with open(sink_path) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    # A truncated/corrupt final line can happen if a
                    # writer process was killed mid-write. Skip it
                    # rather than let one bad line crash the whole
                    # dashboard - the rest of the log is still valid.
                    skipped += 1
    except FileNotFoundError:
        return pd.DataFrame()

    if skipped:
        st.warning(f"Skipped {skipped} unparseable line(s) in `{sink_path}` "
                   "(likely truncated by a process that was killed mid-write).")

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    if "step" not in df.columns:
        df["step"] = None
    df["step"] = df["step"].fillna("unattributed")
    return df


# ---------------------------------------------------------------- CSS

def inject_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');

    /* Streamlit's generated wrapper classes have changed naming scheme
       across versions (old: "css-xxxxx", current: "st-emotion-cache-xxxxx")
       and re-apply Streamlit's own default font on elements close to our
       injected HTML, overriding plain inheritance from html/body. A
       universal selector can't go stale the way a class-substring one did. */
    * {{
        font-family: 'IBM Plex Mono', ui-monospace, monospace !important;
    }}

    .block-container {{
        padding-top: 2.2rem;
        padding-bottom: 3rem;
        max-width: 1180px;
    }}

    #MainMenu, footer {{visibility: hidden;}}

    /* ---- header ---- */
    /* font-size floor: below ~18px, this label reliably renders with its
       glyphs vertically clipped (top slice only) in Streamlit's flex-based
       block layout - reproduced with every font-family/weight/letter-spacing
       combination and independent of load timing, so it isn't a font or
       animation issue. Verified clean at 19px+; kept at 20px for margin. */
    .lcp-eyebrow {{
        color: {MUTED};
        font-size: 20px;
        letter-spacing: .2em;
        margin-bottom: 6px;
    }}
    .lcp-title {{
        font-size: 34px;
        font-weight: 700;
        letter-spacing: .02em;
        color: {TEXT};
        margin-bottom: 4px;
    }}
    .lcp-sink {{
        color: {MUTED};
        font-size: 13px;
        margin-bottom: 28px;
    }}
    .lcp-sink code {{
        color: {BLUE};
        background: transparent;
    }}

    /* ---- status pill ---- */
    .lcp-status {{
        display:flex; align-items:center; justify-content:space-between;
        border:1px solid; border-radius:12px; padding:16px 22px;
        margin-bottom: 26px;
    }}
    .lcp-status.ok {{ border-color: {GREEN}55; background: {GREEN}0f; }}
    .lcp-status.warn {{ border-color: {RED}55; background: {RED}12; }}
    .lcp-status-left {{ display:flex; align-items:center; gap:12px; }}
    .lcp-status-dot {{ width:10px; height:10px; border-radius:50%; }}
    .lcp-status.ok .lcp-status-dot {{ background:{GREEN}; box-shadow:0 0 10px {GREEN}; }}
    .lcp-status.warn .lcp-status-dot {{ background:{RED}; box-shadow:0 0 10px {RED}; }}
    .lcp-status-label {{ font-weight:700; letter-spacing:.05em; font-size:14px; }}
    .lcp-status.ok .lcp-status-label {{ color:{GREEN}; }}
    .lcp-status.warn .lcp-status-label {{ color:{RED}; }}
    .lcp-status-detail {{ color:{MUTED}; font-size:13px; }}
    .lcp-status-bar-track {{ width:180px; height:6px; border-radius:3px; background:{LINE}; overflow:hidden; }}
    .lcp-status-bar-fill {{ height:100%; border-radius:3px; }}

    /* ---- metric cards ---- */
    .lcp-cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:26px; }}
    .lcp-card {{
        border:1px solid {LINE}; border-left:3px solid var(--accent, {BLUE});
        border-radius:10px; padding:18px 20px; background:{PANEL};
    }}
    .lcp-card-label {{ color:{MUTED}; font-size:11.5px; letter-spacing:.08em; text-transform:uppercase; margin-bottom:8px; }}
    .lcp-card-value {{ color:{TEXT}; font-size:26px; font-weight:700; letter-spacing:-0.01em; }}
    .lcp-card-sub {{ color:{MUTED2}; font-size:11.5px; margin-top:4px; }}

    /* ---- insight callout ---- */
    .lcp-insight {{
        border:1px solid {AMBER}55; background:{AMBER}0d;
        border-radius:12px; padding:18px 22px; margin-bottom:34px;
        display:flex; align-items:flex-start; gap:14px;
    }}
    .lcp-insight-icon {{ font-size:18px; line-height:1.4; }}
    .lcp-insight-text {{ color:{TEXT}; font-size:14.5px; line-height:1.55; }}
    .lcp-insight-text b {{ color:{AMBER}; }}
    .lcp-insight-text .muted {{ color:{MUTED}; }}

    /* ---- section headers ---- */
    .lcp-section {{ display:flex; align-items:center; gap:10px; margin:8px 0 14px; }}
    .lcp-section-bar {{ width:4px; height:18px; border-radius:2px; background:{BLUE}; }}
    .lcp-section-title {{ font-size:15px; font-weight:700; letter-spacing:.06em; color:{TEXT}; text-transform:uppercase; }}

    [data-testid="stExpander"] {{
        border:1px solid {LINE} !important; border-radius:10px !important; background:{PANEL} !important;
    }}
    </style>
    """, unsafe_allow_html=True)


def metric_card(label, value, sub, accent):
    st.markdown(f"""
    <div class="lcp-card" style="--accent:{accent}">
        <div class="lcp-card-label">{label}</div>
        <div class="lcp-card-value">{value}</div>
        <div class="lcp-card-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


def section_header(title):
    st.markdown(f"""
    <div class="lcp-section">
        <div class="lcp-section-bar"></div>
        <div class="lcp-section-title">{title}</div>
    </div>
    """, unsafe_allow_html=True)


# --------------------------------------------------------------- charts

def _base_layout(fig, height=320):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Mono, monospace", color=TEXT, size=12),
        margin=dict(l=10, r=20, t=10, b=10),
        height=height,
        showlegend=False,
        hoverlabel=dict(bgcolor=PANEL, font_family="IBM Plex Mono, monospace", bordercolor=LINE),
    )
    fig.update_xaxes(gridcolor=LINE, zerolinecolor=LINE, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=LINE, zerolinecolor=LINE, tickfont=dict(color=MUTED))
    return fig


def cost_by_step_chart(df):
    s = df.groupby("step")["cost_usd"].sum().sort_values(ascending=True)
    colors = [RED if i == len(s) - 1 else BLUE for i in range(len(s))]
    fig = go.Figure(go.Bar(
        x=s.values, y=s.index, orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"${v:,.4f}" for v in s.values],
        textposition="outside",
        textfont=dict(color=TEXT, size=12),
        cliponaxis=False,
        hovertemplate="%{y}: $%{x:,.4f}<extra></extra>",
    ))
    fig = _base_layout(fig, height=max(220, 60 * len(s)))
    # This chart renders in a narrower column than the others, so its
    # plot area is tighter - without extra right margin and a bit of
    # x-axis headroom, the widest bar's outside-positioned label gets
    # clipped by the container edge (seen directly in a real render:
    # "$5.5632" was cut down to "$5.").
    fig.update_layout(margin=dict(l=10, r=70, t=10, b=10))
    fig.update_xaxes(range=[0, s.values.max() * 1.22])
    return fig


def cost_by_model_chart(df):
    s = df.groupby("model")["cost_usd"].sum().sort_values(ascending=False)
    total = s.sum()
    colors = [MODEL_COLORS[i % len(MODEL_COLORS)] for i in range(len(s))]
    fig = go.Figure(go.Pie(
        labels=s.index, values=s.values, hole=0.62,
        marker=dict(colors=colors, line=dict(color=BG, width=2)),
        textinfo="none",
        hovertemplate="%{label}<br>$%{value:,.4f} (%{percent})<extra></extra>",
    ))
    fig.add_annotation(text=f"${total:,.2f}<br><span style='font-size:11px;color={MUTED}'>total</span>",
                        showarrow=False, font=dict(size=18, color=TEXT))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Mono, monospace", color=TEXT, size=12),
        margin=dict(l=10, r=10, t=10, b=10), height=280,
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02,
                    font=dict(size=11, color=MUTED)),
    )
    return fig


def _hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def cumulative_cost_chart(df):
    d = df.sort_values("timestamp").copy()
    d["cumulative"] = d["cost_usd"].cumsum()
    fig = go.Figure(go.Scatter(
        x=d["timestamp"], y=d["cumulative"], mode="lines",
        line=dict(color=BLUE, width=2.2),
        fill="tozeroy", fillcolor=_hex_to_rgba(BLUE, 0.13),
        hovertemplate="%{x|%b %d, %H:%M}<br>$%{y:,.4f}<extra></extra>",
    ))
    return _base_layout(fig, height=260)


def latency_by_step_chart(df):
    s = df.groupby("step")["latency_s"].mean().sort_values(ascending=True)
    fig = go.Figure(go.Bar(
        x=s.values, y=s.index, orientation="h",
        marker=dict(color=PURPLE),
        text=[f"{v:.3f}s" for v in s.values],
        textposition="outside", textfont=dict(color=TEXT, size=11),
        cliponaxis=False,
        hovertemplate="%{y}: %{x:.4f}s avg<extra></extra>",
    ))
    fig = _base_layout(fig, height=max(200, 55 * len(s)))
    fig.update_layout(margin=dict(l=10, r=60, t=10, b=10))
    if s.values.max() > 0:
        fig.update_xaxes(range=[0, s.values.max() * 1.22])
    return fig


# ---------------------------------------------------------------- render

def render(df: pd.DataFrame, sink_path: str, budget: Optional[float]):
    st.set_page_config(page_title="LLM Cost Profiler", layout="wide", initial_sidebar_state="collapsed")
    inject_css()

    st.markdown('<div class="lcp-eyebrow">LLM&#8209;COST&#8209;PROFILER</div>', unsafe_allow_html=True)
    st.markdown('<div class="lcp-title">Cost Dashboard</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="lcp-sink">reading from <code>{sink_path}</code></div>', unsafe_allow_html=True)

    if df.empty:
        st.info("No records yet. Run your instrumented app to generate data, then refresh.")
        return

    total_cost = float(df["cost_usd"].sum())
    total_calls = int(len(df))
    total_tokens = int(df["total_tokens"].sum())
    avg_cost = total_cost / total_calls if total_calls else 0
    n_steps = df["step"].nunique()

    # ---- status bar ----
    if budget is not None:
        pct = min(total_cost / budget, 1.0) if budget > 0 else 1.0
        exceeded = total_cost > budget
        cls = "warn" if exceeded else "ok"
        label = "BUDGET EXCEEDED" if exceeded else "WITHIN BUDGET"
        bar_color = RED if exceeded else GREEN
        st.markdown(f"""
        <div class="lcp-status {cls}">
            <div class="lcp-status-left">
                <div class="lcp-status-dot"></div>
                <div class="lcp-status-label">{label}</div>
                <div class="lcp-status-detail">${total_cost:,.4f} of ${budget:,.2f} budget</div>
            </div>
            <div class="lcp-status-bar-track">
                <div class="lcp-status-bar-fill" style="width:{pct*100:.1f}%; background:{bar_color}"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ---- hero metric cards ----
    st.markdown('<div class="lcp-cards">', unsafe_allow_html=True)
    cols = st.columns(4)
    with cols[0]:
        metric_card("Total cost", f"${total_cost:,.4f}", f"{total_calls} calls logged", BLUE)
    with cols[1]:
        metric_card("Avg cost / call", f"${avg_cost:,.5f}", "across all steps", PURPLE)
    with cols[2]:
        metric_card("Total tokens", f"{total_tokens:,}", "prompt + completion", GREEN)
    with cols[3]:
        metric_card("Steps tracked", f"{n_steps}", "distinct pipeline steps", AMBER)
    st.markdown('</div>', unsafe_allow_html=True)

    # ---- insight callout: auto-generated top cost driver ----
    step_costs = df.groupby("step")["cost_usd"].sum().sort_values(ascending=False)
    if len(step_costs) > 0 and step_costs.iloc[0] > 0:
        top_step = step_costs.index[0]
        top_cost = step_costs.iloc[0]
        share = (top_cost / total_cost * 100) if total_cost else 0
        # 99.5% correctly rounds to "100%" at 0dp, which reads as a
        # misleading "there is zero cost elsewhere" claim - use 1dp
        # once we're past 99% so the real magnitude stays visible.
        share_str = f"{share:.1f}" if share > 99 else f"{share:.0f}"
        st.markdown(f"""
        <div class="lcp-insight">
            <div class="lcp-insight-icon">&#9888;&#65039;</div>
            <div class="lcp-insight-text">
                <b>{top_step}</b> is your top cost driver &mdash; <b>{share_str}%</b> of total spend
                <span class="muted">(${top_cost:,.4f} of ${total_cost:,.4f} across {total_calls} calls)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ---- charts ----
    left, right = st.columns([1.3, 1])
    with left:
        section_header("Cost by step")
        st.plotly_chart(cost_by_step_chart(df), width="stretch", config={"displayModeBar": False})
    with right:
        section_header("Cost by model")
        st.plotly_chart(cost_by_model_chart(df), width="stretch", config={"displayModeBar": False})

    section_header("Cumulative cost over time")
    st.plotly_chart(cumulative_cost_chart(df), width="stretch", config={"displayModeBar": False})

    section_header("Average latency by step")
    st.plotly_chart(latency_by_step_chart(df), width="stretch", config={"displayModeBar": False})

    with st.expander(f"Raw records ({total_calls} total, most recent first)"):
        st.dataframe(df.sort_values("timestamp", ascending=False).head(200), width="stretch")


def main():
    args = _parse_args()
    df = load_records(args.sink)
    render(df, args.sink, args.budget)


main()
