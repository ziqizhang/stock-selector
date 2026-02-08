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
    # Optional CLI arg: python run.py <codex|claude>
    # Default: claude
    if len(sys.argv) > 1:
        provider = sys.argv[1].strip().lower()
        if provider not in {"codex", "claude"}:
            raise SystemExit("Usage: python run.py [codex|claude]")
        os.environ["STOCK_SELECTOR_LLM"] = provider
    else:
        os.environ.setdefault("STOCK_SELECTOR_LLM", "claude")

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("src.api.routes:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
