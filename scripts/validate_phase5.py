"""Offline CSV/DDL contract checks. This does NOT execute PostgreSQL DDL.

SQLite evaluates only translated scalar CHECK expressions, never CREATE/INSERT.
PostgreSQL syntax, catalog behavior and deferred enforcement need a real server.
"""

import csv
from datetime import datetime
import json
import math
import re
import sqlite3

try:
    from .generate_erd import ROOT, read_schema, dbml
except ImportError:
    from generate_erd import ROOT, read_schema, dbml


def read_tables():
    tables = {}
    for name in read_schema():
        with (ROOT / f"data/cleaned/{name}.csv").open(encoding="utf-8", newline="") as source:
            tables[name] = list(csv.DictReader(source))
    return tables


def typed(value, dtype):
    if value == "":
        return None
    if dtype == "text":
        return value
    if dtype in ("integer", "smallint"):
        assert re.fullmatch(r"-?[0-9]+", value), "Invalid integer"
        number = int(value)
        bound = 2**15 if dtype == "smallint" else 2**31
        assert -bound <= number < bound, "Integer overflow"
        return number
    if dtype == "double precision":
        number = float(value)
        assert math.isfinite(number), "Non-finite numeric value"
        return number
    if dtype == "boolean":
        assert value in ("True", "False"), "Invalid Boolean"
        return value == "True"
    if dtype == "timestamptz":
        assert datetime.fromisoformat(value).utcoffset() is not None, "Missing timezone"
        return value
    raise AssertionError(f"Unrecognized type {dtype}")


def validate(tables, schema=None):
    schema = schema or read_schema()
    assert set(tables) == set(schema), "Table mapping mismatch"
    result = {}
    with sqlite3.connect(":memory:") as evaluator:
        evaluator.create_function("regexp", 2, lambda pattern, value: value is not None and re.search(pattern, value) is not None)
        for name, definition in schema.items():
            columns = definition["columns"]
            names = [c for c, _, _ in columns]
            rows = tables[name]
            assert rows and list(rows[0]) == names, f"CSV column/order mismatch: {name}"
            for keys in [definition["pk"], *[[c] for c in definition["unique"]]]:
                values = [tuple(r[c] for c in keys) for r in rows]
                assert len(values) == len(set(values)), f"Duplicate key: {name}.{keys}"
                assert all(all(v != "" for v in key) for key in values), f"Null key: {name}.{keys}"
            expressions = [expression.replace(" ~ ", " REGEXP ").replace("'Infinity'::double precision", "1e999")
                           for _, expression in definition["checks"]]
            select = " AND ".join(f"COALESCE(({e}), 1)" for e in expressions) or "1"
            query = "SELECT " + select + " FROM (SELECT " + ", ".join(f'? AS "{c}"' for c in names) + ")"
            for row in rows:
                values = []
                for col, dtype, required in columns:
                    assert not required or row[col] != "", f"NOT NULL: {name}.{col}"
                    values.append(typed(row[col], dtype))
                assert evaluator.execute(query, values).fetchone()[0] == 1, f"CHECK failure: {name}"
            result[name] = {"rows": len(rows), "columns": len(names), "nulls": {c: sum(r[c] == "" for r in rows) for c in names}}
    for definition in schema.values():
        for child, cols, parent, targets, _ in definition["refs"]:
            parents = {tuple(r[c] for c in targets) for r in tables[parent]}
            for row in tables[child]:
                key = tuple(row[c] for c in cols)
                assert "" in key or key in parents, f"Unresolved FK: {child}.{cols} -> {parent}"
    return result


def main():
    schema = read_schema()
    result = validate(read_tables(), schema)
    assert (ROOT / "reports/erd.dbml").read_text(encoding="utf-8") == dbml(schema), "Stale DBML"
    assert sum(len(d["refs"]) for d in schema.values()) == 7
    print(json.dumps(result, indent=2))
    print("PASS: CSV types, nullability, PK/UQ/FK and translated scalar CHECKs; SQL/DBML mapping.")
    print("PostgreSQL DDL execution is NOT verified by this offline check.")


if __name__ == "__main__":
    main()
