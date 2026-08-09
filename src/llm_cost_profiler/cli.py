"""CLI entry point: `llm-cost-profiler dashboard [--sink PATH] [--budget N] [--port N] [--headless]`

Streamlit itself takes flags like --server.port before the `--`
separator, while flags meant for our dashboard script go after it.
This wrapper exposes a small, curated set of options and places each
in the correct position, rather than naively forwarding everything
after `--` (which would silently break if a user tried to pass a
streamlit-level flag like --server.port through - argparse in the
dashboard script would reject it as unrecognized).
"""
import argparse
import os
import subprocess
import sys


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "dashboard":
        print("Usage: llm-cost-profiler dashboard [--sink PATH] [--budget N] [--port N] [--headless]")
        sys.exit(0 if len(sys.argv) < 2 else 1)

    parser = argparse.ArgumentParser(prog="llm-cost-profiler dashboard")
    parser.add_argument("--sink", default="llm_costs.jsonl", help="Path to the JSONL cost log")
    parser.add_argument("--budget", type=float, default=None, help="Optional USD budget threshold")
    parser.add_argument("--port", type=int, default=None, help="Port to serve the dashboard on")
    parser.add_argument("--headless", action="store_true", help="Don't try to open a browser")
    args = parser.parse_args(sys.argv[2:])

    try:
        import streamlit  # noqa: F401
    except ImportError:
        print(
            "The dashboard requires the 'dashboard' extra.\n"
            "Install it with: pip install llm-cost-profiler[dashboard]"
        )
        sys.exit(1)

    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.py")

    # Streamlit-level flags go BEFORE the `--` separator. We set a
    # dark theme by default (matching this project's visual identity)
    # via real theme flags - not just CSS - since CSS alone can't
    # reach Streamlit's native chrome (the dataframe widget, inputs,
    # the "Deploy" menu, etc).
    streamlit_flags = [
        "--theme.base", "dark",
        "--theme.backgroundColor", "#08090b",
        "--theme.secondaryBackgroundColor", "#12141a",
        "--theme.textColor", "#e8e9ec",
        "--theme.primaryColor", "#5b8def",
        "--theme.borderColor", "#23262e",
    ]
    if args.port is not None:
        streamlit_flags += ["--server.port", str(args.port)]
    if args.headless:
        streamlit_flags += ["--server.headless", "true"]

    # App-level flags go AFTER `--`, parsed by dashboard.py's own argparse.
    app_flags = ["--sink", args.sink]
    if args.budget is not None:
        app_flags += ["--budget", str(args.budget)]

    cmd = ["streamlit", "run", dashboard_path] + streamlit_flags + ["--"] + app_flags

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print(
            "Could not find the 'streamlit' command on your PATH.\n"
            "Install it with: pip install llm-cost-profiler[dashboard]"
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
