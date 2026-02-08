import webbrowser
import threading
import uvicorn


def open_browser():
    """Open browser after a short delay to let the server start."""
    import time
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000")


def main():
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("src.api.routes:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
