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
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help=(
            "Bind address. Defaults to 127.0.0.1 (local only). Use 0.0.0.0 to serve "
            "the local network; this is a deliberate, trusted-network-only choice."
        ),
    )
    parser.add_argument("--no-browser", action="store_true", help="Do not open the default browser.")
    return parser.parse_args(argv)


def _lan_urls(port: int) -> list[str]:
    """Best-effort LAN-facing URLs when binding beyond loopback."""
    try:
        hostnames = {socket.gethostname()}
    except Exception:
        return []
    urls: list[str] = []
    for name in sorted(hostnames):
        try:
            for info in socket.getaddrinfo(name, None, socket.AF_INET):
                addr = info[4][0]
                if addr and not addr.startswith("127."):
                    url = f"http://{addr}:{port}"
                    if url not in urls:
                        urls.append(url)
        except Exception:
            continue
    return urls


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise SystemExit("Port must be between 1 and 65535")
    probe_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    if not _port_available(args.port):
        raise SystemExit(f"Port {args.port} is already in use on {probe_host}")

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
    if not os.getenv("PE3_SETUP_TOKEN"):
        setup_token_path = data_dir / ".pe3-setup-token"
        if setup_token_path.is_file():
            # Keep setup available across restarts until the first admin
            # exists; the service still refuses once any user is created.
            stored = setup_token_path.read_text(encoding="utf-8").strip()
            if len(stored) >= 32:
                os.environ["PE3_SETUP_TOKEN"] = stored
        elif not db_path.exists():
            os.environ["PE3_SETUP_TOKEN"] = _ensure_secret(setup_token_path)
            print(f"First-run setup token stored in: {setup_token_path}")

    url = f"http://127.0.0.1:{args.port}"
    print(f"PE3 QC: {url}")
    print(f"Database: {db_path}")
    lan = args.host not in ("127.0.0.1", "localhost", "::1")
    if lan:
        print("LAN bind requested; sharing this database over the network is intended "
              "for a trusted local network only.")
        for lan_url in _lan_urls(args.port):
            print(f"LAN URL: {lan_url}")
    if not args.no_browser and not lan:
        Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()

    uvicorn.run(
        "backend.app.main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        workers=1,
    )


if __name__ == "__main__":
    main()
