from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def resource_path(name: str) -> Path:
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_dir / name


def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_free_port(start: int = 8501, end: int = 8599) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("没有找到可用端口，请关闭占用 8501-8599 的程序后重试。")


def open_browser_later(port: int) -> None:
    time.sleep(2.5)
    webbrowser.open(f"http://localhost:{port}")


def main() -> None:
    app_path = resource_path("app.py")
    data_dir = runtime_dir()
    os.environ["XHS_GENERATOR_DATA_DIR"] = str(data_dir)
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    port = find_free_port()
    threading.Thread(target=open_browser_later, args=(port,), daemon=True).start()

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.headless=true",
        f"--server.port={port}",
        "--server.address=127.0.0.1",
    ]
    stcli.main()


if __name__ == "__main__":
    main()
