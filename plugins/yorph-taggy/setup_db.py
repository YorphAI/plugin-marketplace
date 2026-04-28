#!/usr/bin/env python3
"""yorph-taggy database setup helper.

One-time, conversational bootstrap. Driven by skills/setup/SKILL.md.

Three subcommands:

    init       Create the database, the two roles (taggy_rw, taggy_ro),
               apply the schema, and write ~/.yorph/taggy/config.json.

    join       Save existing connection strings (when joining a database a
               teammate already provisioned).

    verify-ro  Confirm taggy_ro cannot mutate state. Used for the spec's
               acceptance criterion #6.

Examples:

    python3 setup_db.py init \\
        --admin-url postgres://postgres:pw@localhost:5432/postgres \\
        --db-name taggy --actor alice

    python3 setup_db.py join \\
        --rw-url postgres://taggy_rw:...@host/taggy \\
        --ro-url postgres://taggy_ro:...@host/taggy \\
        --actor alice

    python3 setup_db.py verify-ro
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse, quote

try:
    import pg8000.dbapi
except ImportError:
    sys.stderr.write(
        "Missing dependency: pg8000. Install with `pip install pg8000`.\n"
    )
    sys.exit(2)


def config_home() -> Path:
    return Path(
        os.environ.get("YORPH_TAGGY_HOME")
        or (Path.home() / ".yorph" / "taggy")
    )


def config_path() -> Path:
    return config_home() / "config.json"


SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def parse_pg_url(url: str) -> dict:
    p = urlparse(url)
    if not p.hostname:
        raise ValueError(f"Could not parse host out of URL: {url!r}")
    return {
        "user": p.username,
        "password": p.password,
        "host": p.hostname,
        "port": p.port or 5432,
        "database": (p.path or "/").lstrip("/") or "postgres",
    }


def connect(url: str, *, autocommit: bool = True) -> "pg8000.dbapi.Connection":
    info = parse_pg_url(url)
    conn = pg8000.dbapi.connect(**info)
    conn.autocommit = autocommit
    return conn


def gen_password() -> str:
    return secrets.token_urlsafe(24)


def quote_ident(name: str) -> str:
    if not name.replace("_", "").isalnum():
        raise ValueError(f"Refusing to quote suspicious identifier: {name!r}")
    return '"' + name.replace('"', '""') + '"'


def ensure_database(admin_url: str, db_name: str) -> None:
    conn = connect(admin_url)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
        )
        if not cur.fetchone():
            cur.execute(f"CREATE DATABASE {quote_ident(db_name)}")
            print(f"  created database {db_name}")
        else:
            print(f"  database {db_name} already exists")
    finally:
        conn.close()


def quote_literal(s: str) -> str:
    # PASSWORD in CREATE/ALTER ROLE does not accept bound parameters, so we
    # have to inline the value as a SQL string literal. Escape single quotes
    # by doubling, and refuse backslashes (would need E'…' form to be safe).
    if "\\" in s:
        raise ValueError("Password contains backslash; choose a different one.")
    return "'" + s.replace("'", "''") + "'"


def ensure_role(cur, role: str, password: str) -> None:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    pw_lit = quote_literal(password)
    if cur.fetchone():
        cur.execute(
            f"ALTER ROLE {quote_ident(role)} WITH LOGIN PASSWORD {pw_lit}"
        )
        print(f"  updated role {role}")
    else:
        cur.execute(
            f"CREATE ROLE {quote_ident(role)} WITH LOGIN PASSWORD {pw_lit}"
        )
        print(f"  created role {role}")


def apply_schema_and_grants(
    admin_url: str, db_name: str, rw_pw: str, ro_pw: str
) -> None:
    # Roles are cluster-global; create from the admin connection.
    admin = connect(admin_url)
    try:
        cur = admin.cursor()
        ensure_role(cur, "taggy_rw", rw_pw)
        ensure_role(cur, "taggy_ro", ro_pw)
    finally:
        admin.close()

    # Schema + grants apply inside the target database.
    parsed = parse_pg_url(admin_url)
    db_url = (
        f"postgres://{quote(parsed['user'] or '', safe='')}:"
        f"{quote(parsed['password'] or '', safe='')}"
        f"@{parsed['host']}:{parsed['port']}/{db_name}"
    )
    db = connect(db_url)
    try:
        # The schema has multiple statements (including a CREATE FUNCTION
        # with $$ … $$). pg8000's cursor.execute() goes via the extended
        # protocol and accepts only one statement at a time. execute_simple
        # uses the simple query protocol, which handles a multi-statement
        # script natively.
        db.execute_simple(SCHEMA_PATH.read_text())
        print("  applied schema")
        cur = db.cursor()

        ident_db = quote_ident(db_name)
        cur.execute(
            f"GRANT CONNECT ON DATABASE {ident_db} TO taggy_rw, taggy_ro"
        )
        cur.execute("GRANT USAGE ON SCHEMA public TO taggy_rw, taggy_ro")
        cur.execute(
            "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public "
            "TO taggy_rw"
        )
        cur.execute(
            "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public "
            "TO taggy_rw"
        )
        cur.execute(
            "GRANT SELECT ON ALL TABLES IN SCHEMA public TO taggy_ro"
        )
        cur.execute(
            "GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO taggy_ro"
        )
        # Default privileges so future tables / sequences inherit grants.
        cur.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE ON TABLES TO taggy_rw"
        )
        cur.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO taggy_rw"
        )
        cur.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT ON TABLES TO taggy_ro"
        )
        cur.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT ON SEQUENCES TO taggy_ro"
        )
        print("  applied grants")
    finally:
        db.close()


def write_config(actor: str, rw_url: str, ro_url: str) -> None:
    home = config_home()
    home.mkdir(parents=True, exist_ok=True)
    cfg = {"db_url_rw": rw_url, "db_url_ro": ro_url, "actor": actor}
    path = config_path()
    path.write_text(json.dumps(cfg, indent=2) + "\n")
    os.chmod(path, 0o600)
    print(f"  wrote {path}")


def cmd_init(args: argparse.Namespace) -> None:
    rw_pw = args.rw_password or gen_password()
    ro_pw = args.ro_password or gen_password()

    print(f"Setting up taggy in database `{args.db_name}` ...")
    ensure_database(args.admin_url, args.db_name)
    apply_schema_and_grants(args.admin_url, args.db_name, rw_pw, ro_pw)

    parsed = parse_pg_url(args.admin_url)
    rw_url = (
        f"postgres://taggy_rw:{quote(rw_pw, safe='')}"
        f"@{parsed['host']}:{parsed['port']}/{args.db_name}"
    )
    ro_url = (
        f"postgres://taggy_ro:{quote(ro_pw, safe='')}"
        f"@{parsed['host']}:{parsed['port']}/{args.db_name}"
    )
    write_config(args.actor, rw_url, ro_url)
    print("Done.")


def cmd_join(args: argparse.Namespace) -> None:
    write_config(args.actor, args.rw_url, args.ro_url)
    for label, url in (("rw", args.rw_url), ("ro", args.ro_url)):
        try:
            c = connect(url)
            c.cursor().execute("SELECT 1")
            c.close()
            print(f"  verified {label} connection")
        except Exception as e:
            print(f"  WARNING: {label} connection failed: {e}", file=sys.stderr)
    print("Done.")


def cmd_verify_ro(_args: argparse.Namespace) -> None:
    """Confirm taggy_ro cannot mutate state. Spec acceptance #6."""
    cfg = json.loads(config_path().read_text())
    c = connect(cfg["db_url_ro"], autocommit=False)
    cur = c.cursor()
    refused = []
    for stmt in [
        "INSERT INTO items (title, created_by) VALUES ('x', 'x')",
        "UPDATE items SET title = 'x'",
        "DELETE FROM items",
        "CREATE TABLE _ro_smoke (x INT)",
    ]:
        try:
            cur.execute(stmt)
            c.rollback()
            print(f"  FAIL: ro role accepted: {stmt}")
            sys.exit(1)
        except Exception:
            c.rollback()
            refused.append(stmt.split()[0])
    print(f"  ro role correctly refused: {', '.join(refused)}")


def main() -> None:
    p = argparse.ArgumentParser(prog="setup_db.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(required=True, dest="cmd")

    pi = sub.add_parser("init", help="Create DB, roles, schema, and config.")
    pi.add_argument(
        "--admin-url", required=True,
        help="Connection URL with rights to CREATE DATABASE / CREATE ROLE.",
    )
    pi.add_argument("--db-name", default="taggy")
    pi.add_argument(
        "--rw-password", default=None,
        help="Password for taggy_rw. Defaults to a fresh random secret.",
    )
    pi.add_argument(
        "--ro-password", default=None,
        help="Password for taggy_ro. Defaults to a fresh random secret.",
    )
    pi.add_argument(
        "--actor", required=True,
        help="Display name written into config.json (used as created_by / tagged_by).",
    )
    pi.set_defaults(func=cmd_init)

    pj = sub.add_parser(
        "join", help="Save existing connection strings as config."
    )
    pj.add_argument("--rw-url", required=True)
    pj.add_argument("--ro-url", required=True)
    pj.add_argument("--actor", required=True)
    pj.set_defaults(func=cmd_join)

    pv = sub.add_parser(
        "verify-ro", help="Confirm taggy_ro is read-only."
    )
    pv.set_defaults(func=cmd_verify_ro)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
