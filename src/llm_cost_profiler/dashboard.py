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
import streamlit as st


def _parse_args():
    # Streamlit strips its own flags AND the `--` separator before
    # handing off to the script - sys.argv[1:] here is already just
    # our app-level args (e.g. ['--sink', 'x.jsonl']) in a real
    # `streamlit run` subprocess. (Verified by direct inspection.)
    #
    # Under streamlit.testing.v1.AppTest, though, the script runs
    # in-process, so sys.argv is whatever the *outer* process (e.g.
    # pytest) was invoked with - completely unrelated to this app and
    # not safe to parse strictly. We use parse_known_args() so any
    # unrecognized argv (pytest's own flags, test paths, etc.) is
    # ignored instead of raising, and rely on the env var defaults
    # below in that case.
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


def render(df: pd.DataFrame, sink_path: str, budget: Optional[float]):
    st.set_page_config(page_title="LLM Cost Profiler", layout="wide")
    st.title("LLM Cost Profiler")
    st.caption(f"Reading from `{sink_path}`")

    if df.empty:
        st.info("No records yet. Run your instrumented app to generate data, then refresh.")
        return

    total_cost = float(df["cost_usd"].sum())
    total_calls = int(len(df))
    total_tokens = int(df["total_tokens"].sum())

    if budget is not None and total_cost > budget:
        st.error(f"Budget exceeded: ${total_cost:.4f} spent vs ${budget:.2f} budget")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total cost", f"${total_cost:.4f}")
    c2.metric("Total calls", total_calls)
    c3.metric("Total tokens", f"{total_tokens:,}")

    st.subheader("Cost by step")
    step_costs = df.groupby("step")["cost_usd"].sum().sort_values(ascending=False)
    st.bar_chart(step_costs)

    st.subheader("Cost by model")
    model_costs = df.groupby("model")["cost_usd"].sum().sort_values(ascending=False)
    st.bar_chart(model_costs)

    st.subheader("Cumulative cost over time")
    df_sorted = df.sort_values("timestamp").copy()
    df_sorted["cumulative_cost"] = df_sorted["cost_usd"].cumsum()
    st.line_chart(df_sorted.set_index("timestamp")["cumulative_cost"])

    st.subheader("Average latency by step")
    step_latency = df.groupby("step")["latency_s"].mean().sort_values(ascending=False)
    st.bar_chart(step_latency)

    st.subheader("Raw records (most recent first)")
    st.dataframe(df.sort_values("timestamp", ascending=False).head(200), width="stretch")


def main():
    args = _parse_args()
    df = load_records(args.sink)
    render(df, args.sink, args.budget)


main()
