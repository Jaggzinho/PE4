from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import socket
import sys
from threading import Thread
import time
import urllib.request
import webbrowser

import uvicorn

from backend.app.static_spa import default_static_dir
from backend.app.services.database_source import InvalidDatabaseSource, configured_path, web_config_path


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _ensure_secret(path: Path) -> str:
    if path.is_file():
        value = path.read_text(encoding="utf-8").strip()
        if len(value) >= 32:
            return value
    path.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_urlsafe(48)
    path.write_text(value, encoding="utf-8")
    return value


def _open_browser_when_ready(url: str) -> None:
    health_url = f"{url}/api/health"
    for _attempt in range(60):
        try:
            with urllib.request.urlopen(health_url, timeout=1) as response:  # noqa: S310 - loopback URL
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except Exception:
            time.sleep(0.25)


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local PE3 QC web application.")
    parser.add_argument("--db", type=Path, help="DuckDB file to use; defaults to data/pe3.duckdb.")
    parser.add_argument("--port", type=int, default=8000, help="Loopback port (default: 8000).")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the default browser.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise SystemExit("Port must be between 1 and 65535")
    if not _port_available(args.port):
        raise SystemExit(f"Port {args.port} is already in use on 127.0.0.1")

    root = _runtime_root()
    data_dir = root / "data"
    try:
        saved_path = configured_path(web_config_path()) if not args.db and not os.getenv("PE3_DB_PATH") else None
    except InvalidDatabaseSource as exc:
        raise SystemExit(str(exc)) from exc
    if args.db:
        db_source = "command_line"
    elif os.getenv("PE3_DB_PATH"):
        db_source = "environment"
    elif saved_path:
        db_source = "local_config"
    else:
        db_source = "default"
    db_path = (args.db or os.getenv("PE3_DB_PATH") or saved_path or data_dir / "pe3.duckdb")
    db_path = Path(db_path).expanduser().resolve()
    if db_source == "local_config" and not db_path.is_file():
        raise SystemExit(f"Configured database file does not exist: {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    static_dir = Path(os.getenv("PE3_STATIC_DIR") or default_static_dir()).resolve()
    if not (static_dir / "index.html").is_file():
        raise SystemExit(
            f"Built frontend not found at {static_dir}. Run build-web.cmd before starting PE3."
        )

    os.environ["PE3_DB_PATH"] = str(db_path)
    os.environ["PE3_DB_SOURCE"] = db_source
    os.environ["PE3_STATIC_DIR"] = str(static_dir)
    if not os.getenv("PE3_JWT_SECRET"):
        os.environ["PE3_JWT_SECRET"] = _ensure_secret(data_dir / ".pe3-jwt-secret")
    if not db_path.exists() and not os.getenv("PE3_SETUP_TOKEN"):
        setup_path = data_dir / ".pe3-setup-token"
        os.environ["PE3_SETUP_TOKEN"] = _ensure_secret(setup_path)
        print(f"First-run setup token stored in: {setup_path}")

    url = f"http://127.0.0.1:{args.port}"
    print(f"PE3 QC: {url}")
    print(f"Database: {db_path}")
    if not args.no_browser:
        Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()

    uvicorn.run(
        "backend.app.main:create_app",
        factory=True,
        host="127.0.0.1",
        port=args.port,
        workers=1,
    )


if __name__ == "__main__":
    main()
