"""Phase 6: validate offline, inspect read-only, or explicitly load PostgreSQL.

Run from the repository root: python -m src.load_postgres --help
CSV blanks become None; all other text is retained exactly. No schema DDL here.
"""

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import sqlite3

import certifi
import pandas as pd
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from dotenv import load_dotenv

from scripts.generate_erd import read_schema


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROWS = dict(brands=525, categories=4, products=1987,
                     product_categories=2000, nutrition=1987)
TABLES = tuple(EXPECTED_ROWS)  # Foreign-key-safe insertion order.


class LoadError(Exception):
    """Only fixed, non-sensitive messages may cross the CLI boundary."""


def require(condition, message):
    if not condition:
        raise LoadError(message)


@contextmanager
def database_step(stage):
    """Expose a fixed operation label and safe diagnosis, never raw DB details."""
    try:
        yield
    except LoadError:
        raise
    except Exception as error:
        code = getattr(error, "sqlstate", None)
        code = code if isinstance(code, str) and re.fullmatch(r"[0-9A-Z]{5}", code) else None
        hints = {
            "28P01": "Authentication failed; check the private local credentials.",
            "28000": "Authentication was rejected; check the configured role and access.",
            "42501": "Insufficient permission; check SELECT and catalog access for the configured role.",
            "42P01": "A required relation is missing; review the target database and schema.",
            "42703": "A SQL column is unavailable; review the catalog query and server compatibility.",
            "42702": "A SQL column reference is ambiguous; the loader query needs correction.",
            "42601": "SQL syntax was rejected; the loader query needs correction.",
            "57014": "The query was canceled or timed out; retry read-only verification.",
            "55P03": "A required lock was unavailable; retry when other transactions finish.",
        }
        # Inspect internally only to classify libpq failures without a SQLSTATE.
        # Never copy exception text, diagnostic detail, URLs or hostnames to output.
        message = str(error).lower()
        if "certificate verify failed" in message or "root certificate" in message:
            hint = ("TLS certificate validation failed. Check the configured CA bundle "
                    "(sslrootcert or PGSSLROOTCERT); the default uses certifi. Keep sslmode=verify-full.")
        elif code in hints:
            hint = hints[code]
        elif code and code.startswith("23"):
            hint = "A database constraint rejected the operation; review schema and source validation."
        elif isinstance(error, psycopg.OperationalError):
            hint = "Connection/transport failed; check network access, TLS and the private local connection settings."
        elif isinstance(error, (KeyError, IndexError, TypeError)):
            hint = "An unexpected database response shape was returned; review the loader and server compatibility."
        else:
            hint = "Unexpected database/client failure; review this loader step locally."
        suffix = f" [SQLSTATE {code}]" if code else ""
        raise LoadError(f"{stage} failed{suffix}. {hint} No successful load confirmed.") from None


def execute_check(cursor, stage, query, params=None):
    """Attach a safe location to catalog-query failures."""
    with database_step(stage):
        cursor.execute(query, params)


def parse_cell(value, dtype):
    """Convert CSV strings to native psycopg parameters, without float ID inference."""
    if pd.isna(value):
        return None
    if dtype == "text":
        return str(value)
    if dtype in ("smallint", "integer"):
        require(bool(re.fullmatch(r"-?[0-9]+", value)), "Invalid source integer.")
        number = int(value)
        bound = 2 ** (15 if dtype == "smallint" else 31)
        require(-bound <= number < bound, "Source integer out of range.")
        return number
    if dtype == "double precision":
        number = float(value)
        require(math.isfinite(number), "Non-finite source numeric value.")
        return number
    if dtype == "boolean":
        require(value in ("True", "False"), "Invalid source Boolean.")
        return value == "True"
    if dtype == "timestamptz":
        timestamp = datetime.fromisoformat(value)
        require(timestamp.utcoffset() is not None, "Source timestamp needs a timezone.")
        return timestamp
    raise LoadError("Unsupported source type; review sql/schema.sql.")


def read_sources(directory=ROOT / "data/cleaned"):
    """Validate types, counts, PK/UQ/FK, nullability and existing scalar CHECKs."""
    schema = read_schema()
    require(set(schema) == set(TABLES), "Unexpected repository schema tables.")
    records = {}
    for table in TABLES:
        definition = schema[table]
        frame = pd.read_csv(Path(directory) / f"{table}.csv", dtype="string",
                            keep_default_na=False, na_values=[""])
        require(list(frame.columns) == [c for c, _, _ in definition["columns"]],
                f"CSV columns differ from schema: {table}.")
        require(len(frame) == EXPECTED_ROWS[table], f"Unexpected source row count: {table}.")
        records[table] = [tuple(parse_cell(v, dtype) for v, (_, dtype, _) in
                                zip(row, definition["columns"]))
                          for row in frame.itertuples(index=False, name=None)]
    validate_sources(records, schema)
    return records, schema


def validate_sources(records, schema):
    mapped = {t: [dict(zip([c for c, _, _ in schema[t]["columns"]], row))
                  for row in records[t]] for t in TABLES}
    # Reuse Phase 5's narrow SQLite scalar evaluation approach; no tables/writes.
    with sqlite3.connect(":memory:") as evaluator:
        evaluator.create_function("regexp", 2,
                                  lambda p, v: v is not None and re.search(p, v) is not None)
        for table, definition in schema.items():
            rows = mapped[table]
            for keys in [definition["pk"], *[[c] for c in definition["unique"]]]:
                values = [tuple(row[c] for c in keys) for row in rows]
                require(all(None not in key for key in values) and len(set(values)) == len(values),
                        f"Null or duplicate source key: {table}.")
            expressions = [e.replace(" ~ ", " REGEXP ").replace("'Infinity'::double precision", "1e999")
                           for _, e in definition["checks"]]
            query = "SELECT " + (" AND ".join(f"COALESCE(({e}), 1)" for e in expressions) or "1")
            query += " FROM (SELECT " + ", ".join(f'? AS "{c}"' for c, _, _ in definition["columns"]) + ")"
            for row in rows:
                require(all(not required or row[c] is not None for c, _, required in definition["columns"]),
                        f"Missing required source value: {table}.")
                values = [v.isoformat() if isinstance(v, datetime) else v for v in row.values()]
                require(evaluator.execute(query, values).fetchone()[0] == 1,
                        f"Source CHECK constraint failed: {table}.")
            for child, keys, parent, targets, _ in definition["refs"]:
                parents = {tuple(row[c] for c in targets) for row in mapped[parent]}
                require(all(None in (key := tuple(row[c] for c in keys)) or key in parents
                            for row in mapped[child]), f"Unresolved source foreign key: {child}.")
    require(sum(row["barcode"].startswith("0") for row in mapped["products"]) == 83,
            "Expected 83 leading-zero source barcodes.")
    memberships = Counter(row["barcode"] for row in mapped["product_categories"])
    require(Counter(memberships.values()) == {1: 1974, 2: 13},
            "Unexpected source category overlap counts.")


def connection_settings():
    # Do not interpolate other environment variables inside a password.
    load_dotenv(ROOT / ".env", override=False, interpolate=False)
    url = os.environ.get("DATABASE_URL", "").strip()
    require(bool(url), "DATABASE_URL is missing. Copy .env.example to .env and configure your Neon URL.")
    try:
        require(url.startswith(("postgresql://", "postgres://")), "Invalid DATABASE_URL.")
        settings = conninfo_to_dict(url)
        require(all(settings.get(k) for k in ("host", "dbname", "user", "password")),
                "Incomplete DATABASE_URL; configure your local Neon connection URL.")
        require(not any(token in url for token in ("YOUR_", "<", ">", "example.invalid")),
                "Replace the DATABASE_URL placeholder with your local Neon connection URL.")
        require(settings.get("sslmode") in ("require", "verify-ca", "verify-full"),
                "DATABASE_URL must explicitly require TLS (prefer sslmode=verify-full).")
    except LoadError:
        raise
    except Exception:
        raise LoadError("Invalid DATABASE_URL; check your local configuration.") from None
    # Strengthen Neon sslmode=require URLs; never weaken certificate/hostname checks.
    settings.update(sslmode="verify-full", connect_timeout=15)
    # Bundled libpq/OpenSSL on Windows may not resolve a usable system CA store.
    # certifi is already pinned in requirements.txt; supply its portable CA file.
    # Explicit URL settings take precedence over libpq's environment setting.
    settings.setdefault("sslrootcert", os.environ.get("PGSSLROOTCERT") or certifi.where())
    return settings


def identifiers(names):
    return sql.SQL(", ").join(map(sql.Identifier, names))


def table_name(table):
    require(table in TABLES, "Unexpected table identifier.")
    return sql.Identifier("public", table)


def expression_plan(cursor, table, expressions):
    """Let PostgreSQL normalize CHECK syntax (IN/ANY, casts, BETWEEN).

    EXPLAIN without ANALYZE does not scan data. Expressions come only from the
    repository DDL or server constraint catalog, never from CSV values.
    Comparing server-normalized outputs avoids a fragile home-grown SQL parser.
    """
    execute_check(cursor, f"CHECK expression planning: {table}",
                  sql.SQL("EXPLAIN (VERBOSE, FORMAT JSON) SELECT {} FROM ONLY {}").format(
        sql.SQL(", ").join(sql.SQL(e) for e in expressions), table_name(table)))
    return cursor.fetchone()[0][0]["Plan"]["Output"]


def verify_schema(cursor, schema):
    """Fail closed on column, key, constraint or table-behavior drift; never fix DDL."""
    for table in TABLES:
        definition = schema[table]
        relation = "public." + table
        execute_check(cursor, f"Table catalog verification: {table}", """
            SELECT c.relkind, c.relrowsecurity, c.relforcerowsecurity,
                   EXISTS (SELECT 1 FROM pg_catalog.pg_trigger t
                           WHERE t.tgrelid=c.oid AND (NOT t.tgisinternal OR t.tgenabled <> 'O')),
                   EXISTS (SELECT 1 FROM pg_catalog.pg_rewrite r WHERE r.ev_class=c.oid),
                   EXISTS (SELECT 1 FROM pg_catalog.pg_inherits i
                           WHERE i.inhrelid=c.oid OR i.inhparent=c.oid)
            FROM pg_catalog.pg_class c WHERE c.oid=pg_catalog.to_regclass(%s)
        """, (relation,))
        require(cursor.fetchone() == ("r", False, False, False, False, False),
                f"Live table missing or has unexpected behavior: {table}. Manual review required.")
        execute_check(cursor, f"Column catalog verification: {table}", """
            SELECT a.attname, pg_catalog.format_type(a.atttypid,a.atttypmod),
                   a.attnotnull, a.atthasdef, a.attidentity, a.attgenerated
            FROM pg_catalog.pg_attribute a
            WHERE a.attrelid=pg_catalog.to_regclass(%s) AND a.attnum>0 AND NOT a.attisdropped
            ORDER BY a.attnum
        """, (relation,))
        expected = [(c, "timestamp with time zone" if t == "timestamptz" else t, required, False, "", "")
                    for c, t, required in definition["columns"]]
        require(cursor.fetchall() == expected, f"Live column/type/nullability drift: {table}. Manual review required.")
        execute_check(cursor, f"Constraint catalog verification: {table}", """
            SELECT conname, contype,
                   ARRAY(SELECT a.attname FROM unnest(conkey) WITH ORDINALITY k(n,ord)
                         JOIN pg_catalog.pg_attribute a ON a.attrelid=conrelid AND a.attnum=k.n ORDER BY ord),
                   confrelid::regclass::text,
                   ARRAY(SELECT a.attname FROM unnest(confkey) WITH ORDINALITY k(n,ord)
                         JOIN pg_catalog.pg_attribute a ON a.attrelid=confrelid AND a.attnum=k.n ORDER BY ord),
                   condeferrable, condeferred,
                   convalidated AND COALESCE((to_jsonb(pg_constraint)->>'conenforced')::boolean, true),
                   confupdtype, confdeltype, confmatchtype,
                   pg_catalog.pg_get_expr(conbin,conrelid)
            FROM pg_catalog.pg_constraint WHERE conrelid=pg_catalog.to_regclass(%s)
              AND contype <> 'n' ORDER BY conname
        """, (relation,))
        keys, checks = [], {}
        for name, kind, cols, parent, targets, deferred, initially, valid, update, delete, match, expr in cursor.fetchall():
            require(valid, f"Unvalidated live constraint: {table}.")
            if kind == "c":
                require(not deferred and not initially, f"Unexpected CHECK timing: {table}.")
                checks[name] = expr
            elif kind in ("p", "u"):
                keys.append((kind, tuple(cols), None, (), deferred, initially))
            elif kind == "f":
                require((update, delete, match) == ("a", "a", "s"), f"Live FK actions differ: {table}.")
                keys.append((kind, tuple(cols), parent, tuple(targets), deferred, initially))
            else:
                raise LoadError(f"Unexpected live constraint: {table}.")
        expected_keys = [("p", tuple(definition["pk"]), None, (), False, False)]
        expected_keys += [("u", (c,), None, (), False, False) for c in definition["unique"]]
        expected_keys += [("f", tuple(cs), "public." + parent, tuple(ts), d, d)
                          for _, cs, parent, ts, d in definition["refs"]]
        require(sorted(keys) == sorted(expected_keys), f"Live PK/UNIQUE/FK drift: {table}. Manual review required.")
        expected_checks = dict(definition["checks"])
        require(checks.keys() == expected_checks.keys(), f"Live CHECK set differs: {table}.")
        if checks:
            order = sorted(checks)
            require(expression_plan(cursor, table, [checks[n] for n in order]) ==
                    expression_plan(cursor, table, [expected_checks[n] for n in order]),
                    f"Live CHECK expressions differ: {table}. Manual review required.")


def verify_contents(cursor, records, schema):
    """Use actual SELECTs for counts, duplicates, all FKs and every source cell."""
    counts = {}
    for table in TABLES:
        cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(table_name(table)))
        counts[table] = cursor.fetchone()[0]
    if not any(counts.values()):
        return "empty", counts
    require(counts == EXPECTED_ROWS, "Partial or unexpected live row counts; manual review required: " + json.dumps(counts))
    for table in TABLES:
        definition = schema[table]
        cursor.execute(sql.SQL("SELECT count(*) FROM (SELECT {} FROM {} GROUP BY {} HAVING count(*) > 1) duplicates").format(
            identifiers(definition["pk"]), table_name(table), identifiers(definition["pk"])))
        require(cursor.fetchone()[0] == 0, f"Duplicate live primary key: {table}.")
        for child, cols, parent, targets, _ in definition["refs"]:
            nonnull = sql.SQL(" AND ").join(sql.SQL("c.{} IS NOT NULL").format(sql.Identifier(c)) for c in cols)
            matches = sql.SQL(" AND ").join(sql.SQL("c.{} = p.{}").format(sql.Identifier(c), sql.Identifier(p))
                                           for c, p in zip(cols, targets))
            cursor.execute(sql.SQL("SELECT count(*) FROM {} c WHERE {} AND NOT EXISTS (SELECT 1 FROM {} p WHERE {})").format(
                table_name(child), nonnull, table_name(parent), matches))
            require(cursor.fetchone()[0] == 0, f"Unresolved live foreign key: {child}.")
        cursor.execute(sql.SQL("SELECT {} FROM {}").format(
            identifiers([c for c, _, _ in definition["columns"]]), table_name(table)))
        # Exact Python float equality compares binary64 values, not printed SQL
        # decimals. Python float(CSV text) and psycopg float8 round-trip identically.
        # Aware datetimes compare instants; None is distinct from zero/empty text.
        require(Counter(cursor.fetchall()) == Counter(records[table]),
                f"Live contents differ from cleaned CSV: {table}. Manual review required.")
    cursor.execute("SELECT count(*) FROM public.products WHERE barcode LIKE '0%'")
    require(cursor.fetchone()[0] == 83, "Leading-zero barcode validation failed.")
    # OVERLAPS is reserved in PostgreSQL; use an unambiguous subquery alias.
    execute_check(cursor, "Category overlap count verification", """SELECT count(*) FROM
                      (SELECT barcode FROM public.product_categories
                       GROUP BY barcode HAVING count(*) > 1) AS category_overlaps""")
    require(cursor.fetchone()[0] == 13, "Category overlap validation failed.")
    # Full row comparisons above also check every nutrient NULL and all 13 pairs.
    return "identical", counts


def inspect_database(connection, records, schema):
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        cursor.execute("SET LOCAL search_path TO pg_catalog")
        cursor.execute("SET LOCAL statement_timeout = '60s'")
        with database_step("Read-only schema verification"):
            verify_schema(cursor, schema)
        with database_step("Read-only content verification"):
            return verify_contents(cursor, records, schema)


def load_database(connection, records, schema):
    """Called only by --load after a successful read-only preflight."""
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL search_path TO pg_catalog")
        cursor.execute("SET LOCAL lock_timeout = '10s'")
        cursor.execute("SET LOCAL statement_timeout = '60s'")
        # Serialize writers and block DDL before rechecking; never delete/replace.
        cursor.execute(sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE").format(
            sql.SQL(", ").join(table_name(t) for t in TABLES)))
        verify_schema(cursor, schema)
        state, counts = verify_contents(cursor, records, schema)
        if state == "identical":
            return state, counts
        for table in TABLES:
            columns = [c for c, _, _ in schema[table]["columns"]]
            query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                table_name(table), identifiers(columns),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns))
            cursor.executemany(query, records[table])
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        _, counts = verify_contents(cursor, records, schema)
    # The context has committed successfully before reporting success.
    return "loaded", counts


def run(*, offline=False, load=False):
    records, schema = read_sources()
    if offline:
        return {"status": "offline_validated", "source_rows": {t: len(r) for t, r in records.items()},
                "leading_zero_barcodes": 83, "overlapping_products": 13}
    settings = connection_settings()
    stage = "Database connection"
    try:
        with psycopg.connect(**settings, autocommit=True) as connection:
            stage = "Read-only transaction setup/verification"
            state, counts = inspect_database(connection, records, schema)
            if load and state == "empty":
                stage = "Authorized loading transaction"
                state, counts = load_database(connection, records, schema)
            return {"status": state, "live_rows": counts, "schema": "verified",
                    "content_comparison": "passed" if state in ("identical", "loaded") else "pending"}
    except LoadError:
        raise
    except Exception as error:
        with database_step(stage):
            raise error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--offline", action="store_true", help="Validate cleaned CSVs without connecting.")
    group.add_argument("--verify-only", action="store_true", help="Read-only schema/content verification (default).")
    group.add_argument("--load", action="store_true", help="Explicitly authorize initial inserts after read-only preflight.")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(offline=args.offline, load=args.load), indent=2))
        return 0
    except LoadError as error:
        print(f"STOP: {error}")
    except Exception:
        print("STOP: Source/configuration validation failed. Check cleaned CSVs, schema and local configuration; no successful load confirmed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
