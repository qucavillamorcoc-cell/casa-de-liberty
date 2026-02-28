"""Local HTTPS dev server for Django using Werkzeug.

Usage (in a second terminal while runserver is on 8000):
    python serve_https.py

Default URL:
    https://127.0.0.1:8000/

Notes:
- Uses a self-signed ad-hoc certificate (browser warning is expected).
- Keeps your normal Django HTTP server on http://127.0.0.1:8000/.
"""

from __future__ import annotations

import argparse
import os


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Django over HTTPS for local development.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="HTTPS port (default: 8000)")
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable Werkzeug auto-reloader",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Load Django app and exit (sanity check only)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # Mark this process as local HTTPS development so Django can serve /media/
    # even when DEBUG=False in the user's .env.
    os.environ.setdefault("LOCAL_HTTPS_DEV", "1")

    from django.core.wsgi import get_wsgi_application
    from django.conf import settings
    from werkzeug.serving import run_simple

    app = get_wsgi_application()

    if args.check:
        print("HTTPS dev server check OK")
        print(f"DJANGO_SETTINGS_MODULE={os.environ.get('DJANGO_SETTINGS_MODULE')}")
        print(f"DEBUG={settings.DEBUG}")
        print(f"Target: https://{args.host}:{args.port}/")
        return

    print(f"Starting local HTTPS server at https://{args.host}:{args.port}/")
    print("Self-signed certificate: browser warning is expected (use Advanced > Proceed).")
    run_simple(
        hostname=args.host,
        port=args.port,
        application=app,
        ssl_context="adhoc",
        use_reloader=not args.no_reload,
        use_debugger=bool(settings.DEBUG),
        threaded=True,
    )


if __name__ == "__main__":
    main()
