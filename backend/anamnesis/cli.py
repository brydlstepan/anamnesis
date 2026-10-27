"""`anamnesis serve` / `anamnesis migrate` / `anamnesis gen-secret`."""

import argparse
import base64
import secrets


def main() -> None:
    parser = argparse.ArgumentParser(prog="anamnesis")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="run the web server")
    serve.add_argument("--host", default="0.0.0.0")  # noqa: S104 - container default
    serve.add_argument("--port", type=int, default=8080)
    sub.add_parser("migrate", help="apply database migrations")
    sub.add_parser("gen-secret", help="print a random ANAMNESIS_SECRET_KEY")
    args = parser.parse_args()

    if args.cmd == "gen-secret":
        print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
    elif args.cmd == "migrate":
        from .config import Settings
        from .db import make_engine
        from .migrate import run_migrations

        s = Settings()
        s.data_dir.mkdir(parents=True, exist_ok=True)
        run_migrations(make_engine(s.db_url))
        print("migrations applied")
    elif args.cmd == "serve":
        import uvicorn

        uvicorn.run(
            "anamnesis.main:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            proxy_headers=True,  # trusted proxies: FORWARDED_ALLOW_IPS env (uvicorn default 127.0.0.1)
            workers=1,  # single process: in-memory rate limiter + scheduler live here
        )


if __name__ == "__main__":
    main()
