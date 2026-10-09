"""Offline tests. Real saved products are copied only into temporary test data.

No generated products are added to the project dataset. Malformed identifiers
and HTTP responses below are deliberately mocked failure cases.
"""

import copy
import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from src import download_dataset as d


class FakeClock:
    def __init__(self):
        self.now = 1_800_000_000.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def response(status=200, products=None, headers=None, **extra):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = dict(products=products or [], **extra)
    return result


class ExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_path = d.PROJECT_ROOT / "data/raw/food_products_raw.json"
        cls.original_bytes = cls.original_path.read_bytes()
        cls.products = json.loads(cls.original_bytes)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.clock = FakeClock()
        self.session = Mock()
        self.session.headers = {}
        self.policy = dict(interval_seconds=10, max_retries=3, backoff_seconds=10,
                           timeout_seconds=45, max_wait_seconds=300, max_pages=20)
        # Any accidental real HTTP request fails the test immediately.
        self.network = patch.object(requests.Session, "request", side_effect=AssertionError("Live HTTP forbidden in tests"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.output = redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def args(self, *extra):
        return d.parse_args(["--data-dir", str(self.root), "--contact-email", "student@university.edu",
                             "--page-size", "2", "--target", "3", *extra])

    def run_extraction(self, *extra):
        return d.run(self.args(*extra), self.session, self.clock.sleep, self.clock.time)

    def fetcher(self):
        return d.Fetcher(self.session, self.root / "cooldown.json", self.policy,
                         self.clock.sleep, self.clock.time)

    def legacy(self):
        raw = self.root / "raw"
        raw.mkdir()
        (raw / "food_products_raw.json").write_bytes(self.original_bytes)
        (raw / "food_products_extracted.csv").write_bytes(
            self.original_path.with_name("food_products_extracted.csv").read_bytes())

    def test_all_retryable_statuses_retry(self):
        for status in sorted(d.RETRY_STATUSES):
            with self.subTest(status=status):
                self.session.get.reset_mock()
                self.session.get.side_effect = [response(status), response(products=self.products[:2])]
                payload, metadata = self.fetcher().fetch(d.make_config(page_size=2), 1)
                self.assertEqual(payload["products"], self.products[:2])
                self.assertEqual(metadata["attempts"], 2)
                self.assertEqual(self.session.get.call_count, 2)

    def test_backoff_is_exponential_and_bounded(self):
        self.session.get.side_effect = [response(503) for _ in range(4)]
        with self.assertRaisesRegex(d.ExtractionError, "exhausted 4 attempts"):
            self.fetcher().fetch(d.make_config(), 1)
        self.assertEqual(sum(self.clock.sleeps), 70)
        self.assertEqual(self.session.get.call_count, 4)

    def test_retry_after_seconds_overrides_backoff(self):
        self.session.get.side_effect = [response(429, headers={"Retry-After": "90"}), response()]
        self.fetcher().fetch(d.make_config(), 1)
        self.assertEqual(sum(self.clock.sleeps), 90)

    def test_retry_after_http_date(self):
        date = format_datetime(datetime.fromtimestamp(self.clock.now + 75, timezone.utc), usegmt=True)
        self.session.get.side_effect = [response(503, headers={"Retry-After": date}), response()]
        self.fetcher().fetch(d.make_config(), 1)
        self.assertEqual(sum(self.clock.sleeps), 75)

    def test_invalid_retry_after_falls_back_to_backoff(self):
        self.session.get.side_effect = [response(503, headers={"Retry-After": "invalid"}), response()]
        self.fetcher().fetch(d.make_config(), 1)
        self.assertEqual(sum(self.clock.sleeps), 10)

    def test_long_retry_after_stops_and_persists_cooldown(self):
        self.session.get.side_effect = [response(429, headers={"Retry-After": "3600"})]
        with self.assertRaisesRegex(d.ExtractionError, "cooldown exceeds"):
            self.fetcher().fetch(d.make_config(), 1)
        self.assertEqual(self.session.get.call_count, 1)
        with self.assertRaisesRegex(d.ExtractionError, "cooldown exceeds"):
            self.fetcher().fetch(d.make_config(), 1)
        self.assertEqual(self.session.get.call_count, 1)
        self.assertEqual(self.clock.sleeps, [])

    def test_final_failure_keeps_retry_after_for_next_run(self):
        self.policy["max_retries"] = 0
        self.session.get.return_value = response(429, headers={"Retry-After": "120"})
        with self.assertRaises(d.ExtractionError):
            self.fetcher().fetch(d.make_config(), 1)
        self.session.get.return_value = response()
        self.fetcher().fetch(d.make_config(), 1)
        self.assertEqual(sum(self.clock.sleeps), 120)

    def test_transient_network_errors_retry(self):
        self.session.get.side_effect = [requests.Timeout("timeout"), requests.ConnectionError("offline"), response()]
        self.fetcher().fetch(d.make_config(), 1)
        self.assertEqual(self.session.get.call_count, 3)
        self.assertEqual(sum(self.clock.sleeps), 30)

    def test_non_retryable_http_stops_immediately(self):
        self.session.get.return_value = response(403)
        with self.assertRaisesRegex(d.ExtractionError, "Non-retryable HTTP 403"):
            self.fetcher().fetch(d.make_config(), 1)
        self.assertEqual(self.session.get.call_count, 1)

    def test_malformed_response_does_not_complete_page(self):
        for payload in ({}, {"products": None}, {"products": [None]}, {"page": 9, "products": []}):
            with self.subTest(payload=payload):
                self.session.get.return_value = response()
                self.session.get.return_value.json.return_value = payload
                result = self.run_extraction()
                self.assertEqual(result["completed_pages"], [])
                self.assertEqual(result["status"], "incomplete")

    def test_invalid_json_stops_without_completion(self):
        self.session.get.return_value = response()
        self.session.get.return_value.json.side_effect = ValueError("not JSON")
        result = self.run_extraction()
        self.assertEqual(result["completed_pages"], [])
        self.assertIn("Invalid JSON", result["error"])

    def test_resume_skips_completed_pages_after_retry_failure(self):
        self.session.get.side_effect = [response(products=self.products[:2]), response(503), response(503)]
        first = self.run_extraction("--max-retries", "1")
        self.assertEqual(first["completed_pages"], [1])
        self.assertEqual(first["status"], "incomplete")
        self.assertEqual(first["row_counts"]["unique_products"], 2)
        self.session.get.reset_mock()
        self.session.get.side_effect = [response(products=self.products[2:4])]
        second = self.run_extraction()
        self.assertEqual(second["status"], "complete")
        self.assertEqual(self.session.get.call_count, 1)
        self.assertEqual(self.session.get.call_args.kwargs["params"]["page"], 2)
        self.assertIn("student@university.edu", self.session.headers["User-Agent"])
        self.assertGreaterEqual(sum(self.clock.sleeps), 30)

    def test_completed_target_does_not_request_again(self):
        self.session.get.return_value = response(products=self.products[:2])
        self.run_extraction("--target", "2")
        self.session.get.reset_mock()
        self.run_extraction("--target", "2")
        self.session.get.assert_not_called()

    def test_recover_page_written_before_checkpoint(self):
        store = d.Store(self.root, d.make_config(page_size=2))
        store.commit_page({"products": self.products[:2]}, 1)
        store.publish(3, "in_progress", self.policy)
        store.commit_page({"products": self.products[2:4]}, 2)
        # Simulate process death before the second checkpoint publication.
        result = self.run_extraction()
        self.assertEqual(result["completed_pages"], [1, 2])
        self.session.get.assert_not_called()

    def test_corrupt_checkpoint_recovers_and_preserves_evidence(self):
        store = d.Store(self.root, d.make_config(page_size=2))
        store.commit_page({"products": self.products[:2]}, 1)
        store.checkpoint_path.write_text('{"incomplete":', encoding="utf-8")
        result = self.run_extraction("--offline")
        self.assertEqual(result["completed_pages"], [1])
        self.assertEqual(len(list(store.root.glob("checkpoint.corrupt-*.json"))), 1)
        self.session.get.assert_not_called()

    def test_missing_committed_page_fails_closed(self):
        store = d.Store(self.root, d.make_config(page_size=2))
        store.commit_page({"products": self.products[:2]}, 1)
        store.publish(3, "in_progress", self.policy)
        (store.pages_dir / "page_000001.json").unlink()
        with self.assertRaisesRegex(d.ExtractionError, "checkpointed page is missing"):
            self.run_extraction()
        self.session.get.assert_not_called()

    def test_corrupt_raw_page_fails_closed(self):
        store = d.Store(self.root, d.make_config(page_size=2))
        store.commit_page({"products": self.products[:2]}, 1)
        path = store.pages_dir / "page_000001.json"
        page = d.read_json(path)
        page["response"]["products"].pop()
        d.save_json(path, page)
        with self.assertRaisesRegex(d.ExtractionError, "checksum mismatch"):
            self.run_extraction()
        self.session.get.assert_not_called()

    def test_query_changes_use_separate_extractions(self):
        first = d.Store(self.root, d.make_config())
        second = d.Store(self.root, d.make_config(category="fruits"))
        third = d.Store(self.root, d.make_config(page_size=50))
        self.assertEqual(len({first.root, second.root, third.root}), 3)

    def test_deduplication_and_invalid_barcodes_preserve_raw(self):
        products = copy.deepcopy(self.products[:5])
        products[1]["code"] = products[0]["code"]
        products[2].pop("code")
        products[3]["code"] = "not-a-barcode"
        products[4]["code"] = 12345678
        original = copy.deepcopy(products)
        store = d.Store(self.root, d.make_config())
        store.commit_page({"products": products}, 1)
        result = store.publish(500, "offline", self.policy)
        self.assertEqual(result["row_counts"], dict(raw_records=5, unique_products=1,
                         duplicate_barcodes=1, missing_barcodes=1, invalid_barcodes=2))
        self.assertEqual(d.read_json(store.pages_dir / "page_000001.json")["response"]["products"], original)
        self.assertEqual(len(d.read_json(store.root / "barcode_issues.json")), 4)

    def test_duplicate_across_pages_keeps_first_record(self):
        store = d.Store(self.root, d.make_config(page_size=2))
        store.commit_page({"products": self.products[:2]}, 1)
        later = copy.deepcopy(self.products[:1])
        later[0]["product_name"] = "Changed name in mocked later response"
        store.commit_page({"products": later}, 2)
        rows, _, counts = d.analytical_records(store.pages, store.extraction_id)
        self.assertEqual(rows[0]["product_name"], self.products[0].get("product_name", ""))
        self.assertEqual(counts["duplicate_barcodes"], 1)

    def test_analysis_schema_and_null_nutrients(self):
        products = copy.deepcopy(self.products[:1])
        products[0]["nutriments"] = {"salt_100g": 0, "proteins_100g": "3.2", "sugars_100g": "nan", "fat_100g": -1}
        store = d.Store(self.root, d.make_config())
        store.commit_page({"products": products}, 1)
        store.publish(500, "offline", self.policy)
        with store.analysis_path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
        self.assertEqual(reader.fieldnames, d.ANALYSIS_FIELDS)
        self.assertEqual(len(reader.fieldnames), 21)
        self.assertEqual(rows[0]["salt_g_100g"], "0.0")
        self.assertEqual(rows[0]["protein_g_100g"], "3.2")
        self.assertEqual(rows[0]["sugars_g_100g"], "")
        self.assertEqual(rows[0]["fat_g_100g"], "")

    def test_leading_zeroes_are_preserved(self):
        # Identifier-only edge case; no product is created or written.
        barcode = "00012345"
        self.assertEqual(d.barcode_value(barcode), (barcode, None))
        self.assertEqual(d.barcode_value("  ")[1], "missing_barcode")
        self.assertEqual(d.barcode_value("123")[1], "invalid_barcode")

    def test_legacy_import_backs_up_and_skips_page_one(self):
        self.legacy()
        self.session.get.return_value = response(products=[])
        result = self.run_extraction("--page-size", "100", "--target", "500", "--import-legacy")
        self.assertEqual(result["row_counts"]["raw_records"], 100)
        self.assertEqual(self.session.get.call_args.kwargs["params"]["page"], 2)
        self.assertEqual((self.root / "raw/food_products_raw.json").read_bytes(), self.original_bytes)
        backup = next((self.root / "backups").glob("legacy_*"))
        self.assertEqual((backup / "food_products_raw.json").read_bytes(), self.original_bytes)
        page = next((self.root / "raw/extractions").glob("*/pages/page_000001.json"))
        self.assertIsNone(d.read_json(page)["extracted_at_utc"])
        self.assertEqual(d.read_json(page)["origin"], "legacy_import")

    def test_legacy_import_requires_original_configuration(self):
        self.legacy()
        with self.assertRaisesRegex(d.ExtractionError, "requires the original"):
            self.run_extraction("--import-legacy", "--offline")

    def test_legacy_data_requires_explicit_migration(self):
        self.legacy()
        with self.assertRaisesRegex(d.ExtractionError, "Use --import-legacy"):
            self.run_extraction("--page-size", "100")
        self.session.get.assert_not_called()

    def test_atomic_replace_failure_preserves_existing_file(self):
        path = self.root / "saved.json"
        path.write_bytes(b"original")
        with patch.object(d.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                d.atomic_write(path, b"new")
        self.assertEqual(path.read_bytes(), b"original")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_atomic_fsync_failure_preserves_existing_file(self):
        path = self.root / "saved.json"
        path.write_bytes(b"original")
        with patch.object(d.os, "fsync", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                d.atomic_write(path, b"new")
        self.assertEqual(path.read_bytes(), b"original")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_checkpoint_write_failure_recovers_without_refetch(self):
        self.session.get.return_value = response(products=self.products[:2])
        real_save = d.save_json

        def fail_after_page(path, value):
            if Path(path).name == "checkpoint.json" and value["completed_pages"]:
                raise OSError("checkpoint disk failure")
            real_save(path, value)

        with patch.object(d, "save_json", side_effect=fail_after_page):
            with self.assertRaises(OSError):
                self.run_extraction("--target", "2")
        self.session.get.reset_mock()
        result = self.run_extraction("--target", "2")
        self.assertEqual(result["status"], "complete")
        self.session.get.assert_not_called()

    def test_short_page_is_incomplete_and_does_not_repeat(self):
        self.session.get.return_value = response(products=self.products[:1])
        first = self.run_extraction()
        self.assertEqual(first["reason"], "source_exhausted")
        self.assertEqual(first["status"], "incomplete")
        self.session.get.reset_mock()
        self.run_extraction()
        self.session.get.assert_not_called()

    def test_maximum_page_budget_stops_duplicate_only_pages(self):
        self.session.get.return_value = response(products=self.products[:2])
        result = self.run_extraction("--max-pages", "2")
        self.assertEqual(result["reason"], "page_budget_reached")
        self.assertEqual(self.session.get.call_count, 2)
        self.assertEqual(result["row_counts"]["unique_products"], 2)

    def test_page_count_is_not_treated_as_total_pages(self):
        self.session.get.side_effect = [response(products=self.products[:2], page_count=2),
                                        response(products=self.products[2:4], page_count=2)]
        result = self.run_extraction()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(self.session.get.call_count, 2)

    def test_offline_mode_has_no_network_or_email_requirement(self):
        args = d.parse_args(["--data-dir", str(self.root), "--offline"])
        result = d.run(args, self.session)
        self.assertEqual(result["status"], "incomplete")
        self.session.get.assert_not_called()

    def test_keyboard_interrupt_preserves_progress(self):
        self.session.get.side_effect = [response(products=self.products[:2]), KeyboardInterrupt()]
        result = self.run_extraction()
        self.assertEqual(result["reason"], "interrupted")
        self.assertEqual(result["completed_pages"], [1])

    def test_lock_rejects_concurrent_writer_and_releases(self):
        with d.extraction_lock(self.root):
            with self.assertRaises(d.ExtractionError):
                with d.extraction_lock(self.root):
                    self.fail("Second writer acquired the lock")
        with d.extraction_lock(self.root):
            pass


if __name__ == "__main__":
    unittest.main()
