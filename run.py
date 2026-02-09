import webbrowser
import threading
import os
import sys
import uvicorn


def open_browser():
    """Open browser after a short delay to let the server start."""
    import time
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Stock Selector")
    parser.add_argument(
        "llm", nargs="?", default=None,
        help="LLM backend: codex or claude (default: claude)",
    )
    parser.add_argument(
        "--data-source", choices=["yfinance", "finviz"], default=None,
        help="Primary data source (default: yfinance)",
    )
    args = parser.parse_args()

    # LLM backend
    if args.llm:
        if args.llm.lower() not in {"codex", "claude", "opencode"}:
            raise SystemExit("Supported LLM model CLI provider 'codex' or 'claude' or 'opencode'")
        os.environ["STOCK_SELECTOR_LLM"] = args.llm.lower()
    else:
        os.environ.setdefault("STOCK_SELECTOR_LLM", "claude")

    # Data source
    if args.data_source:
        os.environ["STOCK_SELECTOR_DATA_SOURCE"] = args.data_source
    else:
        os.environ.setdefault("STOCK_SELECTOR_DATA_SOURCE", "yfinance")

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("src.api.routes:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
