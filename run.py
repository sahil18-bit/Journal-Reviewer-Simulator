"""Start the Journal Reviewer Simulator with one click.

Click "Run" on this file (or on backend/app/main.py). The first run creates a
private Python environment in the .venv folder and installs what the app needs
(about a minute, needs internet). Every run then opens the app in your browser.
Press Ctrl+C in the terminal to stop it.
"""

import os
import socket
import subprocess
import sys
import threading
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
PACKAGES = [
    "fastapi>=0.115,<1.0",
    "uvicorn>=0.30,<1.0",
    "pydantic-settings>=2.6,<3.0",
    "pypdf>=4.0,<7.0",
    "python-multipart>=0.0.9",
    "httpx>=0.27,<1.0",
]
MARKER = VENV / "installed.txt"


def inside_venv() -> bool:
    return Path(sys.prefix).resolve() == VENV.resolve()


def setup_and_relaunch() -> None:
    if sys.version_info < (3, 9):  # noqa: UP036 - friendly message on very old Pythons
        sys.exit("Python 3.9 or newer is needed. Install it from https://www.python.org/downloads/")
    if not VENV_PY.exists():
        print("First run: creating the project environment...")
        venv.create(VENV, with_pip=True)
    if not MARKER.exists() or MARKER.read_text() != "\n".join(PACKAGES):
        print("Installing the required packages (one time, about a minute)...")
        subprocess.check_call(
            [str(VENV_PY), "-m", "pip", "install", "-q", "--disable-pip-version-check", *PACKAGES]
        )
        MARKER.write_text("\n".join(PACKAGES))
    ask_for_key_once()
    sys.exit(subprocess.call([str(VENV_PY), str(ROOT / "run.py")]))


def ask_for_key_once() -> None:
    """On the first run, ask for an AI key and save it in .env (never asked again)."""
    env = ROOT / ".env"
    if env.exists():
        return
    print("\nThe AI reviewers need an API key (Gemini, OpenAI or Claude).")
    print("A free Gemini key: https://aistudio.google.com/apikey")
    try:
        key = input(
            "Paste your key here, or just press Enter to use the built-in checklist: "
        ).strip()
    except EOFError:
        key = ""
    if key.startswith("sk-ant-"):
        provider = "anthropic"
    elif key.startswith("sk-"):
        provider = "openai"
    else:
        provider = "gemini" if key else "none"
    env.write_text(f"JRS_LLM_PROVIDER={provider}\nJRS_LLM_API_KEY={key}\n", encoding="utf-8")
    print("Saved. (To change it later, delete the .env file and run again.)\n")


def free_port(start: int = 8000) -> int:
    for port in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def serve() -> None:
    os.chdir(ROOT)  # so the optional .env file is found
    os.environ.setdefault("JRS_LOG_LEVEL", "WARNING")  # keep the terminal quiet
    sys.path.insert(0, str(ROOT / "backend"))
    import uvicorn

    port = free_port()
    url = f"http://127.0.0.1:{port}"
    print(f"\nJournal Reviewer Simulator is running at {url}")
    print("Your browser will open automatically. Press Ctrl+C here to stop.\n")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    if inside_venv():
        try:
            serve()
        except KeyboardInterrupt:
            pass
    else:
        setup_and_relaunch()
