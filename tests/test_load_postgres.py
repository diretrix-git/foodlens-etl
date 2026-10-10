"""Offline Phase 6 regression tests. No real database or HTTP connections."""

from collections import Counter
from contextlib import contextmanager, redirect_stdout
import copy
from datetime import datetime, timezone, timedelta
import io
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from src import load_postgres as loader


class FakeDatabase:
    """Transaction-aware DB-API fake; SQL assertions do not simulate PostgreSQL DDL."""

    def __init__(self, records, schema, *, empty=False):
        self.rows = {t: [] if empty else list(rows) for t, rows in records.items()}
        self.schema = schema
        self.executed = []
        self.inserts = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_table = None
        self.fail_commit = False
        self.corrupt_insert = False
        self.catalog_change = None
        self.integrity_error = False
        self.before_lock = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self

    @contextmanager
    def transaction(self):
        before = copy.deepcopy(self.rows)
        try:
            yield
            if self.fail_commit:
                raise RuntimeError("private connection detail")
        except Exception:
            self.rows = before
            self.rollbacks += 1
            raise
        else:
            self.commits += 1

    def execute(self, query, params=None):
        query = query if isinstance(query, str) else query.as_string()
        self.executed.append((query, params))
        # PostgreSQL reserves OVERLAPS: the former fake accidentally accepted it
        # as a bare FROM-subquery alias, hiding a real post-insert syntax error.
        if re.search(r"\)\s+(?:AS\s+)?overlaps\s*$", query, re.IGNORECASE):
            raise loader.psycopg.errors.SyntaxError("Unquoted reserved subquery alias")
        table_match = re.search(r'"public"\."(\w+)"', query)
        table = table_match.group(1) if table_match else None
        if "FROM pg_catalog.pg_class" in query:
            self.result = [("r", False, False, False, False, False)]
            if self.catalog_change == "table":
                self.result = []
        elif "a.atthasdef" in query:
            table = params[0].split(".")[1]
            self.result = [(c, "timestamp with time zone" if t == "timestamptz" else t,
                            n, False, "", "") for c, t, n in self.schema[table]["columns"]]
            if self.catalog_change == "column":
                self.result = self.result[:-1]
        elif "FROM pg_catalog.pg_constraint" in query:
            table = params[0].split(".")[1]
            d = self.schema[table]
            self.result = [("pk", "p", d["pk"], "-", [], False, False, True, " ", " ", " ", None)]
            self.result += [("uq", "u", [c], "-", [], False, False, True, " ", " ", " ", None)
                            for c in d["unique"]]
            self.result += [("fk", "f", cs, "public." + p, ts, deferred, deferred, True, "a", "a", "s", None)
                            for _, cs, p, ts, deferred in d["refs"]]
            self.result += [(n, "c", [], "-", [], False, False, True, " ", " ", " ", e)
                            for n, e in d["checks"]]
            if self.catalog_change == "constraint":
                self.result.pop(0)
            if self.catalog_change == "check" and d["checks"]:
                self.result[-1] = (*self.result[-1][:-1], "TRUE")
            if self.catalog_change in ("fk_timing", "fk_action", "unvalidated"):
                for i, row in enumerate(self.result):
                    if row[1] == "f":
                        row = list(row)
                        row[{"fk_timing": 5, "fk_action": 9, "unvalidated": 7}[self.catalog_change]] = (
                            "c" if self.catalog_change == "fk_action" else not row[5] if self.catalog_change == "fk_timing" else False)
                        self.result[i] = tuple(row)
                        break
        elif query.startswith("EXPLAIN"):
            self.result = [([{"Plan": {"Output": query.split(" SELECT ")[1].split(" FROM ONLY ")[0]}}],)]
        elif query.startswith("LOCK"):
            if self.before_lock:
                self.before_lock(self)
            self.result = []
        elif query.startswith("SET"):
            self.result = []
        elif "WHERE barcode LIKE" in query:
            self.result = [(sum(r[0].startswith("0") for r in self.rows["products"]),)]
        elif ") AS category_overlaps" in query:
            self.result = [(sum(n > 1 for n in Counter(r[0] for r in self.rows["product_categories"]).values()),)]
        elif ") duplicates" in query or "NOT EXISTS" in query:
            self.result = [(int(self.integrity_error),)]
        elif query.startswith("SELECT count(*)"):
            self.result = [(len(self.rows[table]),)]
        elif query.startswith("SELECT"):
            self.result = list(reversed(self.rows[table]))  # Ordering must not matter.
        else:
            raise AssertionError("Unexpected SQL in fake")

    def executemany(self, query, rows):
        query = query.as_string()
        table = re.search(r'"public"\."(\w+)"', query).group(1)
        self.inserts.append((table, query, rows))
        if self.fail_table == table:
            raise RuntimeError("private connection detail")
        self.rows[table].extend(rows)
        if self.corrupt_insert and table == "brands":
            self.rows[table][0] = (rows[0][0], "unexpected")

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return self.result


class LoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.schema = loader.read_sources()

    def setUp(self):
        self.connect = self.enterContext(patch.object(loader.psycopg, "connect",
                                                     side_effect=AssertionError("Real DB forbidden")))
        self.enterContext(patch("requests.sessions.Session.request", side_effect=AssertionError("HTTP forbidden")))

    def database(self, **kwargs):
        return FakeDatabase(self.records, self.schema, **kwargs)

    def test_actual_sources_counts_keys_and_nulls(self):
        self.assertEqual({t: len(r) for t, r in self.records.items()}, loader.EXPECTED_ROWS)
        self.assertEqual(sum(r[0].startswith("0") for r in self.records["products"]), 83)
        columns = [c for c, _, _ in self.schema["nutrition"]["columns"]]
        expected = dict(energy_kcal=42, energy_kj=55, protein_g=43, carbohydrates_g=45,
                        sugars_g=50, fat_g=41, saturated_fat_g=54, fiber_g=351, salt_g=67)
        for name, count in expected.items():
            index = columns.index(name + "_per_100")
            self.assertEqual(sum(r[index] is None for r in self.records["nutrition"]), count)

    def test_cell_conversion_preserves_text_and_native_types(self):
        for text in ("00038317", "NA", "a'b\nquoted", "NULL"):
            self.assertEqual(loader.parse_cell(text, "text"), text)
        self.assertIsNone(loader.parse_cell(loader.pd.NA, "double precision"))
        self.assertIs(loader.parse_cell("False", "boolean"), False)
        self.assertEqual(loader.parse_cell("0", "double precision"), 0.0)
        self.assertEqual(loader.parse_cell("0.10000000000000002", "double precision"), 0.10000000000000002)

    def test_invalid_types_rejected(self):
        for text, kind in [("NaN", "double precision"), ("inf", "double precision"),
                           ("32768", "smallint"), ("1.5", "integer"), ("yes", "boolean"),
                           ("2026-01-01", "timestamptz")]:
            with self.subTest(kind=kind), self.assertRaises(loader.LoadError):
                loader.parse_cell(text, kind)

    def test_source_duplicate_fk_and_check_failure(self):
        for change in ("duplicate", "foreign", "check", "required"):
            rows = copy.deepcopy(self.records)
            if change == "duplicate":
                rows["brands"][1] = rows["brands"][0]
            else:
                row = list(rows["products"][0])
                row[{"foreign": 3, "check": 7, "required": 6}[change]] = {
                    "foreign": "missing-brand", "check": 5, "required": None}[change]
                rows["products"][0] = tuple(row)
            with self.subTest(change=change), self.assertRaises(loader.LoadError):
                loader.validate_sources(rows, self.schema)

    def test_csv_header_and_count_drift_rejected(self):
        original = loader.pd.read_csv
        for change in ("header", "count"):
            def altered(*args, **kwargs):
                frame = original(*args, **kwargs)
                return frame.rename(columns={frame.columns[0]: "wrong"}) if change == "header" else frame.iloc[:-1]
            with patch.object(loader.pd, "read_csv", side_effect=altered), self.assertRaises(loader.LoadError):
                loader.read_sources()

    def test_offline_never_connects(self):
        self.assertEqual(loader.run(offline=True)["status"], "offline_validated")
        self.connect.assert_not_called()

    def test_missing_url_stops_without_connecting(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(loader, "load_dotenv"):
            with self.assertRaisesRegex(loader.LoadError, "DATABASE_URL is missing"):
                loader.run()
        self.connect.assert_not_called()

    def test_placeholder_malformed_and_weak_tls_rejected(self):
        for url in ("not a url", "postgresql://YOUR_HOST/neondb?sslmode=verify-full",
                    "postgresql://example.invalid/neondb", "postgresql://u:p@localhost/neondb?sslmode=disable",
                    "postgresql://u:p@localhost/neondb"):
            with self.subTest(url=url), patch.dict(os.environ, {"DATABASE_URL": url}), patch.object(loader, "load_dotenv"):
                with self.assertRaises(loader.LoadError):
                    loader.connection_settings()

    def test_tls_strengthened_and_channel_binding_preserved(self):
        # Synthetic fixture only, never used to connect.
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://fixture:fixture@localhost/neondb?sslmode=require&channel_binding=require"}, clear=True), patch.object(loader, "load_dotenv"):
            settings = loader.connection_settings()
        self.assertEqual(settings["sslmode"], "verify-full")
        self.assertEqual(settings["sslrootcert"], loader.certifi.where())
        self.assertEqual(settings["channel_binding"], "require")
        self.assertTrue(Path(settings["sslrootcert"]).is_file())
        self.assertEqual((settings["host"], settings["dbname"]), ("localhost", "neondb"))

    def test_explicit_ca_url_and_environment_precedence(self):
        base = "postgresql://fixture:fixture@localhost/neondb?sslmode=verify-full"
        for query, environment, expected in (
            ("", "fixture-ca.pem", "fixture-ca.pem"),
            ("&sslrootcert=url-ca.pem", "environment-ca.pem", "url-ca.pem"),
            ("&sslrootcert=system", "", "system"),
        ):
            with self.subTest(query=query), patch.dict(os.environ, {
                "DATABASE_URL": base + query, "PGSSLROOTCERT": environment,
            }, clear=True), patch.object(loader, "load_dotenv"):
                settings = loader.connection_settings()
            self.assertEqual(settings["sslrootcert"], expected)
            self.assertEqual(settings["sslmode"], "verify-full")

    def test_dotenv_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(loader, "ROOT", Path(directory)), patch.dict(os.environ, {}, clear=True):
            Path(directory, ".env").write_text("DATABASE_URL=postgresql://fixture:fixture@localhost/neondb?sslmode=verify-full\n")
            self.assertEqual(loader.connection_settings()["dbname"], "neondb")
            os.environ["DATABASE_URL"] = "postgresql://fixture:fixture@localhost/override?sslmode=verify-full"
            self.assertEqual(loader.connection_settings()["dbname"], "override")

    def test_live_schema_fixture_and_drift(self):
        loader.verify_schema(self.database(), self.schema)
        for change in ("table", "column", "constraint", "check", "fk_timing", "fk_action", "unvalidated"):
            db = self.database()
            db.catalog_change = change
            with self.subTest(change=change), self.assertRaises(loader.LoadError):
                loader.verify_schema(db, self.schema)
            self.assertEqual(db.inserts, [])

    def test_read_only_empty_and_identical(self):
        for empty, expected in ((True, "empty"), (False, "identical")):
            db = self.database(empty=empty)
            state, _ = loader.inspect_database(db, self.records, self.schema)
            self.assertEqual(state, expected)
            self.assertIn("READ ONLY", db.executed[0][0])
            self.assertEqual(db.inserts, [])

    def test_initial_load_parameterization_and_order(self):
        db = self.database(empty=True)
        state, counts = loader.load_database(db, self.records, self.schema)
        self.assertEqual((state, counts), ("loaded", loader.EXPECTED_ROWS))
        self.assertEqual([t for t, _, _ in db.inserts], list(loader.TABLES))
        for table, query, rows in db.inserts:
            self.assertEqual(query.count("%s"), len(self.schema[table]["columns"]))
            columns = [c for c, _, _ in self.schema[table]["columns"]]
            column_sql = ", ".join('"' + c + '"' for c in columns)
            self.assertTrue(query.startswith(f'INSERT INTO "public"."{table}" ({column_sql}) VALUES ('))
            self.assertTrue(all(len(row) == len(columns) for row in rows))
            self.assertEqual(rows, self.records[table])
            self.assertNotIn(rows[0][0], query)
        self.assertEqual(db.commits, 1)
        self.assertTrue(any(q == "SET CONSTRAINTS ALL IMMEDIATE" for q, _ in db.executed))

    def test_overlap_count_uses_postgresql_safe_alias(self):
        db = self.database()
        state, _ = loader.verify_contents(db, self.records, self.schema)
        self.assertEqual(state, "identical")
        queries = [q for q, _ in db.executed if "GROUP BY barcode HAVING count(*) > 1" in q]
        self.assertEqual(len(queries), 1)
        self.assertTrue(queries[0].endswith(") AS category_overlaps"))
        with self.assertRaises(loader.psycopg.errors.SyntaxError):
            db.execute(queries[0].replace(") AS category_overlaps", ") overlaps"))

    def test_post_insert_overlap_sql_error_rolls_back_all_five_tables(self):
        db = self.database(empty=True)
        execute = db.execute

        def fail_overlap(query, params=None):
            if isinstance(query, str) and "GROUP BY barcode HAVING count(*) > 1" in query:
                raise loader.psycopg.errors.SyntaxError("SECRET server diagnostic")
            return execute(query, params)

        with patch.object(db, "execute", side_effect=fail_overlap):
            with self.assertRaises(loader.LoadError) as raised:
                loader.load_database(db, self.records, self.schema)
        self.assertIn("Category overlap count verification failed [SQLSTATE 42601]", str(raised.exception))
        self.assertNotIn("SECRET", str(raised.exception))
        self.assertEqual([table for table, _, _ in db.inserts], list(loader.TABLES))
        self.assertEqual(db.rows, {t: [] for t in loader.TABLES})
        self.assertEqual((db.commits, db.rollbacks), (0, 1))

    def test_rerun_does_not_insert(self):
        db = self.database(empty=True)
        loader.load_database(db, self.records, self.schema)
        db.inserts.clear()
        self.assertEqual(loader.load_database(db, self.records, self.schema)[0], "identical")
        self.assertEqual(db.inserts, [])

    def test_partial_and_same_count_differences_stop(self):
        for change in ("partial", "text", "numeric", "null", "barcode", "membership"):
            db = self.database()
            table = {"numeric": "nutrition", "null": "nutrition", "membership": "product_categories"}.get(change, "products")
            if change == "partial":
                db.rows[table].pop()
            else:
                row = list(db.rows[table][0])
                index = {"text": 1, "numeric": 4, "null": 4, "barcode": 0, "membership": 1}[change]
                row[index] = {"text": "changed", "numeric": 123.456, "null": None,
                              "barcode": "99999999999999", "membership": "wrong"}[change]
                db.rows[table][0] = tuple(row)
            with self.subTest(change=change), self.assertRaises(loader.LoadError):
                loader.load_database(db, self.records, self.schema)
            self.assertEqual(db.inserts, [])

    def test_equivalent_timestamp_instants_match(self):
        db = self.database()
        index = [c for c, _, _ in self.schema["products"]["columns"]].index("extracted_at_utc")
        db.rows["products"] = [tuple(v.astimezone(timezone(timedelta(hours=5))) if i == index and v else v
                                      for i, v in enumerate(row)) for row in db.rows["products"]]
        self.assertEqual(loader.verify_contents(db, self.records, self.schema)[0], "identical")

    def test_sql_integrity_failure_stops(self):
        db = self.database()
        db.integrity_error = True
        with self.assertRaises(loader.LoadError):
            loader.verify_contents(db, self.records, self.schema)

    def test_insert_validation_and_commit_failures_roll_back(self):
        for failure in ("insert", "validation", "commit"):
            db = self.database(empty=True)
            db.fail_table = "nutrition" if failure == "insert" else None
            db.corrupt_insert = failure == "validation"
            db.fail_commit = failure == "commit"
            with self.subTest(failure=failure), self.assertRaises(Exception):
                loader.load_database(db, self.records, self.schema)
            self.assertEqual(db.rows, {t: [] for t in loader.TABLES})
            self.assertEqual(db.rollbacks, 1)

    def test_state_rechecked_after_lock(self):
        db = self.database(empty=True)
        db.before_lock = lambda d: d.rows.update(copy.deepcopy(self.records))
        self.assertEqual(loader.load_database(db, self.records, self.schema)[0], "identical")
        self.assertEqual(db.inserts, [])

    def test_default_readonly_and_load_preflight(self):
        for load in (False, True):
            db = self.database(empty=True)
            with patch.object(loader, "connection_settings", return_value={}), patch.object(loader.psycopg, "connect", return_value=db):
                self.assertEqual(loader.run(load=load)["status"], "loaded" if load else "empty")
            self.assertIn("READ ONLY", db.executed[0][0])
            if not load:
                self.assertEqual(db.inserts, [])

    def test_schema_failure_prevents_authorized_inserts(self):
        db = self.database(empty=True)
        db.catalog_change = "column"
        with patch.object(loader, "connection_settings", return_value={}), patch.object(loader.psycopg, "connect", return_value=db):
            with self.assertRaises(loader.LoadError):
                loader.run(load=True)
        self.assertEqual(db.inserts, [])

    def test_cli_sanitizes_connection_and_source_errors(self):
        for where in ("connection", "source"):
            output = io.StringIO()
            with redirect_stdout(output), patch.object(loader, "connection_settings", return_value={}):
                if where == "connection":
                    self.connect.side_effect = RuntimeError("SECRET fixture private URL")
                    code = loader.main([])
                else:
                    with patch.object(loader, "read_sources", side_effect=ValueError("SECRET CSV value")):
                        code = loader.main(["--offline"])
            self.assertEqual(code, 1)
            self.assertNotIn("SECRET", output.getvalue())
            self.assertNotIn("Traceback", output.getvalue())

    def test_certificate_failure_identifies_connection_and_ca_without_secrets(self):
        output = io.StringIO()
        self.connect.side_effect = loader.psycopg.OperationalError(
            "connection SECRET_HOST SECRET_PASSWORD: certificate verify failed")
        with redirect_stdout(output), patch.object(loader, "connection_settings", return_value={}):
            code = loader.main(["--verify-only"])
        self.assertEqual(code, 1)
        message = output.getvalue()
        for expected in ("Database connection failed", "TLS certificate validation failed", "CA bundle", "verify-full"):
            self.assertIn(expected, message)
        self.assertNotIn("SECRET", message)

    def test_catalog_sql_failure_identifies_exact_step_and_sqlstate(self):
        for fragment, label in (("FROM pg_catalog.pg_class", "Table"),
                                ("a.atthasdef", "Column"),
                                ("FROM pg_catalog.pg_constraint", "Constraint")):
            db = self.database(empty=True)
            execute = db.execute

            def fail_catalog(query, params=None):
                if isinstance(query, str) and fragment in query:
                    raise loader.psycopg.errors.UndefinedColumn("SECRET column detail")
                return execute(query, params)

            with self.subTest(label=label), patch.object(db, "execute", side_effect=fail_catalog):
                with self.assertRaises(loader.LoadError) as raised:
                    loader.inspect_database(db, self.records, self.schema)
            message = str(raised.exception)
            self.assertIn(f"{label} catalog verification: brands failed", message)
            self.assertIn("SQLSTATE 42703", message)
            self.assertNotIn("SECRET", message)
            self.assertEqual(db.inserts, [])

    def test_content_failure_and_response_shape_are_sanitized(self):
        for error, expected in ((loader.psycopg.errors.InsufficientPrivilege("SECRET"), "SQLSTATE 42501"),
                                (KeyError("SECRET"), "unexpected database response shape")):
            db = self.database(empty=True)
            with patch.object(loader, "verify_contents", side_effect=error):
                with self.assertRaises(loader.LoadError) as raised:
                    loader.inspect_database(db, self.records, self.schema)
            message = str(raised.exception)
            self.assertIn("Read-only content verification failed", message)
            self.assertIn(expected, message)
            self.assertNotIn("SECRET", message)

    def test_connection_failure_never_starts_verification_or_loading(self):
        with patch.object(loader, "connection_settings", return_value={}), \
                patch.object(loader, "inspect_database") as inspect, \
                patch.object(loader, "load_database") as load:
            self.connect.side_effect = loader.psycopg.OperationalError("certificate verify failed SECRET")
            with self.assertRaisesRegex(loader.LoadError, "Database connection failed"):
                loader.run(load=True)
        inspect.assert_not_called()
        load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
