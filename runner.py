# -*- coding: utf-8 -*-
"""لانچر داشبورد آزمایشگاه برای نسخهٔ تک‌کلیکی exe"""
import os
import sys
import socket
import time
import threading
import webbrowser

from streamlit.web import cli as stcli


def resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def find_free_port(start: int = 8501, end: int = 8599) -> int:
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("هیچ پورت آزادی پیدا نشد.")


def main() -> None:
    app_path = resource_path("app.py")
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"

    def open_browser() -> None:
        for _ in range(180):                     # ~۹۰ ثانیه صبر
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.5)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    sys.argv = [
        "streamlit", "run", app_path,
        f"--server.port={port}",
        "--server.address=127.0.0.1",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()