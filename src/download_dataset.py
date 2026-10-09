"""Conservative, restartable Open Food Facts extraction (no requests at import)."""

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

BASE_URL = "https://world.openfoodfacts.org/api/v2/search"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Preserve the original query so that the saved first page can be resumed.
FIELDS = ["code", "product_name", "brands", "categories_tags", "nutriments",
          "nutriscore_grade", "nova_group"]
RETRY_STATUSES = {429, 500, 502, 503, 504}
ANALYSIS_FIELDS = [
    "barcode", "product_name", "brands", "categories", "energy_kcal_100g",
    "energy_kj_100g", "protein_g_100g", "carbohydrates_g_100g", "sugars_g_100g",
    "fat_g_100g", "saturated_fat_g_100g", "fiber_g_100g", "salt_g_100g",
    "nutriscore_grade", "nova_group", "source_page", "source_record_index",
    "extracted_at_utc", "source_url", "record_origin", "extraction_id",
]


class ExtractionError(Exception):
    """A failure that must leave saved pages available for recovery."""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, data):
    """Flush a temporary sibling, then replace; failure leaves the old file intact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp",
                                     dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_json(path, value):
    atomic_write(path, json_bytes(value))


def read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


@contextmanager
def extraction_lock(root):
    """OS lock released even after a process crash; serialize all local runs."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".extraction.lock").open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ExtractionError("Another extraction is using this data directory.") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def make_config(category="breakfast-cereals", page_size=100):
    return {"source_url": BASE_URL, "query_parameters": {
        "categories_tags_en": category, "fields": ",".join(FIELDS),
        "page_size": page_size,
    }}


def barcode_value(value):
    """Keep string identifiers verbatim, including leading zeroes; no guessing."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, "missing_barcode"
    # OFF includes non-GTIN internal identifiers. Do not impose a GTIN checksum.
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{8,14}", value):
        return None, "invalid_barcode"
    return value, None


def numeric(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def text_value(value):
    return value if isinstance(value, str) else ""


def analytical_records(pages, extraction_id):
    rows, issues, seen = [], [], set()
    counts = dict(raw_records=0, unique_products=0, duplicate_barcodes=0,
                  missing_barcodes=0, invalid_barcodes=0)
    for page in pages:
        for index, product in enumerate(page["response"]["products"]):
            counts["raw_records"] += 1
            barcode, issue = barcode_value(product.get("code"))
            if issue is None and barcode in seen:
                issue = "duplicate_barcode"
            if issue:
                counts[issue + "s"] += 1
                issues.append({"page": page["page"], "record_index": index,
                               "barcode": product.get("code"), "reason": issue})
                continue
            seen.add(barcode)
            nutrients = product.get("nutriments")
            nutrients = nutrients if isinstance(nutrients, dict) else {}
            categories = product.get("categories_tags")
            categories = ";".join(x for x in categories if isinstance(x, str)) if isinstance(categories, list) else ""
            grade = text_value(product.get("nutriscore_grade")).lower()
            nova = numeric(product.get("nova_group"))
            row = {
                "barcode": barcode, "product_name": text_value(product.get("product_name")),
                "brands": text_value(product.get("brands")), "categories": categories,
                "energy_kcal_100g": numeric(nutrients.get("energy-kcal_100g")),
                "energy_kj_100g": numeric(nutrients.get("energy-kj_100g")),
                "nutriscore_grade": grade if grade in {"a", "b", "c", "d", "e"} else "",
                "nova_group": int(nova) if nova in (1, 2, 3, 4) else None,
                "source_page": page["page"], "source_record_index": index,
                "extracted_at_utc": page["extracted_at_utc"],
                "source_url": page["request_url"], "record_origin": page["origin"],
                "extraction_id": extraction_id,
            }
            for column, key in {
                "protein_g_100g": "proteins", "carbohydrates_g_100g": "carbohydrates",
                "sugars_g_100g": "sugars", "fat_g_100g": "fat",
                "saturated_fat_g_100g": "saturated-fat", "fiber_g_100g": "fiber",
                "salt_g_100g": "salt",
            }.items():
                row[column] = numeric(nutrients.get(key + "_100g"))
            rows.append(row)
    counts["unique_products"] = len(rows)
    return rows, issues, counts


def validate_response(payload, page, page_size):
    if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
        raise ExtractionError("Response has no products list; page was not completed.")
    if any(not isinstance(product, dict) for product in payload["products"]):
        raise ExtractionError("Response contains a non-object product.")
    if len(payload["products"]) > page_size:
        raise ExtractionError("Response exceeds the requested page size.")
    if "page" in payload and str(payload["page"]) != str(page):
        raise ExtractionError("Response page does not match the requested page.")


class Store:
    def __init__(self, data_dir, config):
        self.data_dir = Path(data_dir)
        self.config = config
        self.extraction_id = digest(json_bytes(config))[:16]
        self.root = self.data_dir / "raw" / "extractions" / self.extraction_id
        self.pages_dir = self.root / "pages"
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path = self.root / "checkpoint.json"
        self.analysis_path = self.data_dir / "processed" / f"food_products_analysis_{self.extraction_id}.csv"
        manifest_path = self.root / "manifest.json"
        if manifest_path.exists():
            manifest = read_json(manifest_path)
            if manifest["configuration"] != config:
                raise ExtractionError("Extraction configuration does not match the manifest.")
        else:
            save_json(manifest_path, {"schema_version": 1, "created_at_utc": utc_now(),
                                     "configuration": config, "extraction_id": self.extraction_id})
        self.pages = []
        self.recover()

    def recover(self):
        """Page files commit first; recover pages saved before a checkpoint failure."""
        old_checkpoint = {}
        if self.checkpoint_path.exists():
            try:
                old_checkpoint = read_json(self.checkpoint_path)
                if not isinstance(old_checkpoint, dict):
                    raise ValueError("Checkpoint must be an object")
            except (ValueError, UnicodeError):
                damaged = self.checkpoint_path.read_bytes()
                atomic_write(self.root / f"checkpoint.corrupt-{digest(damaged)[:12]}.json", damaged)
                old_checkpoint = {}
            if old_checkpoint and old_checkpoint.get("configuration") != self.config:
                raise ExtractionError("Checkpoint configuration mismatch.")
        for path in sorted(self.pages_dir.glob("page_*.json")):
            page = read_json(path)
            number = page["page"]
            if page["configuration"] != self.config or path.name != f"page_{number:06d}.json":
                raise ExtractionError(f"Invalid page configuration or filename: {path}")
            if page["response_sha256"] != digest(json_bytes(page["response"])):
                raise ExtractionError(f"Saved response checksum mismatch: {path}")
            validate_response(page["response"], number, self.config["query_parameters"]["page_size"])
            if page["row_count"] != len(page["response"]["products"]):
                raise ExtractionError(f"Saved page row count mismatch: {path}")
            self.pages.append(page)
        completed = [page["page"] for page in self.pages]
        if completed != list(range(1, len(completed) + 1)):
            raise ExtractionError("Saved pages have a gap; restore files before resuming.")
        if not set(old_checkpoint.get("completed_pages", [])).issubset(completed):
            raise ExtractionError("A checkpointed page is missing; restore it from backup.")
        for page in self.pages:
            expected = old_checkpoint.get("page_response_sha256", {}).get(str(page["page"]))
            if expected and expected != page["response_sha256"]:
                raise ExtractionError("Saved page differs from its checkpoint checksum.")

    def commit_page(self, payload, page, *, origin="api", extracted_at=None, extra=None):
        validate_response(payload, page, self.config["query_parameters"]["page_size"])
        params = dict(self.config["query_parameters"], page=page)
        envelope = {
            "schema_version": 1, "configuration": self.config, "page": page,
            "request_parameters": params,
            "request_url": requests.Request("GET", BASE_URL, params=params).prepare().url,
            "extracted_at_utc": extracted_at, "saved_at_utc": utc_now(), "origin": origin,
            "response": payload, "response_sha256": digest(json_bytes(payload)),
            "row_count": len(payload["products"]), "metadata": extra or {},
        }
        path = self.pages_dir / f"page_{page:06d}.json"
        if path.exists() or page != len(self.pages) + 1:
            raise ExtractionError("Refusing to replace a completed page or create a page gap.")
        save_json(path, envelope)
        self.pages.append(envelope)

    def import_legacy(self):
        if self.pages:
            return
        if self.config != make_config():
            raise ExtractionError("Legacy page import requires the original breakfast-cereals query and page_size=100.")
        raw = self.data_dir / "raw" / "food_products_raw.json"
        products = read_json(raw)
        if not isinstance(products, list) or len(products) != 100:
            raise ExtractionError("Legacy import expects the known, complete 100-record first page.")
        validate_response({"products": products}, 1, 100)
        backup = self.data_dir / "backups" / ("legacy_" + digest(raw.read_bytes())[:16])
        files = {}
        for path in [raw, raw.with_name("food_products_extracted.csv")]:
            if not path.exists():
                continue
            content = path.read_bytes()
            destination = backup / path.name
            if destination.exists():
                if destination.read_bytes() != content:
                    raise ExtractionError(f"Existing backup differs: {destination}")
            else:
                atomic_write(destination, content)
            files[path.name] = {"sha256": digest(content), "bytes": len(content)}
        if not (backup / "manifest.json").exists():
            save_json(backup / "manifest.json", {"backed_up_at_utc": utc_now(), "files": files})
        self.commit_page({"products": products}, 1, origin="legacy_import", extra={
            "backup_directory": str(backup.resolve()), "source_sha256": digest(raw.read_bytes()),
            "provenance": "Page 1 inferred from the original script and user-confirmed successful 100-record page. Original extraction timestamp and response envelope were not saved.",
        })

    def source_exhausted(self):
        if not self.pages:
            return False
        last = self.pages[-1]
        size = self.config["query_parameters"]["page_size"]
        count = last["response"].get("count")
        # OFF page_count means records in this page, NOT total pages.
        return (last["row_count"] < size or
                (isinstance(count, int) and not isinstance(count, bool) and count >= 0
                 and last["page"] * size >= count))

    def publish(self, target, reason, policy, error=None):
        rows, issues, counts = analytical_records(self.pages, self.extraction_id)
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=ANALYSIS_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        csv_data = stream.getvalue().encode("utf-8")
        atomic_write(self.analysis_path, csv_data)
        save_json(self.root / "barcode_issues.json", issues)
        checkpoint = {
            "schema_version": 1, "extraction_id": self.extraction_id,
            "configuration": self.config, "updated_at_utc": utc_now(),
            "status": "complete" if len(rows) >= target else "incomplete",
            "reason": "target_reached" if len(rows) >= target else reason,
            "error": error, "target_unique_products": target,
            "completed_pages": [page["page"] for page in self.pages],
            "next_page": len(self.pages) + 1, "source_exhausted": self.source_exhausted(),
            "page_response_sha256": {str(p["page"]): p["response_sha256"] for p in self.pages},
            "row_counts": counts, "request_policy": policy,
            "analysis_csv": str(self.analysis_path.resolve()),
            "analysis_csv_sha256": digest(csv_data), "analysis_columns": ANALYSIS_FIELDS,
            "barcode_policy": "Exact ASCII digit strings, length 8-14; no checksum test or padding. First occurrence wins; all raw records retained.",
            "nutrient_policy": "API _100g values only; g except energy (kcal/kJ). Missing, negative or non-finite values are blank; no imputation or serving conversion.",
        }
        # Final publication marker. CSV/issues can be rebuilt from committed pages.
        save_json(self.checkpoint_path, checkpoint)
        return checkpoint


def retry_after_seconds(value, now):
    if not value:
        return 0.0
    try:
        value = value.strip()
        if re.fullmatch(r"[0-9]+", value):
            return float(value)
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return max(0.0, date.timestamp() - now)
    except (ValueError, TypeError, OverflowError):
        return 0.0


class Fetcher:
    def __init__(self, session, rate_path, policy, sleep=time.sleep, clock=time.time):
        self.session, self.rate_path, self.policy = session, Path(rate_path), policy
        self.sleep, self.clock = sleep, clock
        self.not_before = 0.0
        if self.rate_path.exists():
            self.not_before = read_json(self.rate_path)["not_before_epoch"]
            if not isinstance(self.not_before, (int, float)) or not math.isfinite(self.not_before):
                raise ExtractionError("Invalid persisted rate-limit state; inspect it before resuming.")

    def defer(self, seconds):
        self.not_before = max(self.not_before, self.clock() + seconds)
        save_json(self.rate_path, {"not_before_epoch": self.not_before,
                                   "updated_at_utc": utc_now()})

    def wait(self):
        remaining = self.not_before - self.clock()
        if remaining > self.policy["max_wait_seconds"]:
            raise ExtractionError(f"Server cooldown exceeds this run's wait budget; resume after {datetime.fromtimestamp(self.not_before, timezone.utc).isoformat()}.")
        while remaining > 0:
            self.sleep(min(remaining, 30))
            remaining = self.not_before - self.clock()

    def fetch(self, config, page):
        for attempt in range(self.policy["max_retries"] + 1):
            self.wait()
            self.defer(self.policy["interval_seconds"])
            retry_after = 0.0
            try:
                response = self.session.get(config["source_url"],
                                            params=dict(config["query_parameters"], page=page),
                                            timeout=(10, self.policy["timeout_seconds"]),
                                            allow_redirects=False)
                try:
                    if response.status_code in RETRY_STATUSES:
                        retry_after = retry_after_seconds(response.headers.get("Retry-After"), self.clock())
                        failure = f"HTTP {response.status_code} on page {page}"
                    elif response.status_code != 200:
                        raise ExtractionError(f"Non-retryable HTTP {response.status_code} on page {page}")
                    else:
                        try:
                            payload = response.json()
                        except ValueError as error:
                            raise ExtractionError(f"Invalid JSON on page {page}") from error
                        validate_response(payload, page, config["query_parameters"]["page_size"])
                        return payload, {"http_status": 200, "attempts": attempt + 1,
                                         "response_date": response.headers.get("Date")}
                finally:
                    response.close()
            except (requests.Timeout, requests.ConnectionError) as error:
                failure = f"{type(error).__name__} on page {page}: {error}"
            except requests.RequestException as error:
                raise ExtractionError(str(error)) from error
            backoff = min(self.policy["backoff_seconds"] * (2 ** attempt), 120)
            self.defer(max(self.policy["interval_seconds"], backoff, retry_after))
            if attempt == self.policy["max_retries"]:
                raise ExtractionError(f"{failure}; exhausted {attempt + 1} attempts.")
            print(f"{failure}; retry {attempt + 1}/{self.policy['max_retries']} after cooldown.", flush=True)
        raise AssertionError("Unreachable")


def run(args, session=None, sleep=time.sleep, clock=time.time):
    config = make_config(args.category, args.page_size)
    policy = {"interval_seconds": args.interval, "max_retries": args.max_retries,
              "backoff_seconds": args.backoff, "timeout_seconds": args.timeout,
              "max_wait_seconds": args.max_wait, "max_pages": args.max_pages}
    with extraction_lock(args.data_dir):
        store = Store(args.data_dir, config)
        if args.import_legacy:
            store.import_legacy()
        elif not store.pages and (Path(args.data_dir) / "raw" / "food_products_raw.json").exists() and config == make_config():
            raise ExtractionError("Existing legacy data found. Use --import-legacy to preserve and resume its first page.")
        checkpoint = store.publish(args.target, "offline" if args.offline else "ready", policy)
        if args.offline or checkpoint["status"] == "complete":
            return checkpoint
        own_session = session is None
        session = session or requests.Session()
        session.headers.update({"User-Agent": f"FoodLensStudentProject/2.0 ({args.contact_email})"})
        policy["user_agent"] = session.headers["User-Agent"]
        try:
            fetcher = Fetcher(session, Path(args.data_dir) / "request_cooldown.json", policy, sleep, clock)
            while checkpoint["row_counts"]["unique_products"] < args.target:
                if store.source_exhausted():
                    return store.publish(args.target, "source_exhausted", policy)
                if len(store.pages) >= args.max_pages:
                    return store.publish(args.target, "page_budget_reached", policy)
                page = len(store.pages) + 1
                payload, metadata = fetcher.fetch(config, page)
                metadata["user_agent"] = session.headers["User-Agent"]
                metadata["request_policy"] = dict(policy)
                store.commit_page(payload, page, extracted_at=utc_now(), extra=metadata)
                checkpoint = store.publish(args.target, "in_progress", policy)
                print(f"Page {page} saved: {checkpoint['row_counts']['raw_records']} raw records, "
                      f"{checkpoint['row_counts']['unique_products']}/{args.target} unique products.", flush=True)
            return checkpoint
        except (ExtractionError, requests.RequestException, KeyboardInterrupt) as error:
            return store.publish(args.target, "interrupted" if isinstance(error, KeyboardInterrupt) else "request_failed",
                                 policy, str(error) or "Interrupted by user")
        finally:
            if own_session:
                session.close()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--contact-email", default=os.environ.get("FOODLENS_CONTACT_EMAIL"))
    parser.add_argument("--category", default="breakfast-cereals")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--target", type=int, default=500)
    parser.add_argument("--max-pages", type=int, default=20, help="Total completed page budget, including earlier runs")
    parser.add_argument("--max-retries", type=int, default=3, help="Retries after the first attempt (0-10)")
    parser.add_argument("--interval", type=float, default=10, help="Minimum seconds between attempts, at least 10")
    parser.add_argument("--backoff", type=float, default=10)
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--max-wait", type=float, default=300, help="Stop instead of sleeping beyond this cooldown; never ignore Retry-After")
    parser.add_argument("--import-legacy", action="store_true", help="Import the known saved 100-record page 1 once")
    parser.add_argument("--offline", action="store_true", help="Recover checkpoint and rebuild CSV without any API calls")
    args = parser.parse_args(argv)
    if not (1 <= args.page_size <= 100 and args.target > 0 and args.max_pages > 0 and 0 <= args.max_retries <= 10):
        parser.error("Require page-size 1-100, positive target/max-pages and max-retries 0-10.")
    if any(not math.isfinite(v) or v <= 0 for v in (args.interval, args.backoff, args.timeout, args.max_wait)) or args.interval < 10:
        parser.error("Timing settings must be finite and positive; interval must be at least 10 seconds.")
    if not args.category.strip():
        parser.error("category cannot be empty")
    if not args.offline and (not args.contact_email or not re.fullmatch(r"[^\s@()<>]+@[^\s@()<>]+\.[^\s@()<>]+", args.contact_email)
                             or args.contact_email.endswith("@example.com")):
        parser.error("Set --contact-email or FOODLENS_CONTACT_EMAIL to your real contact email.")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        checkpoint = run(args)
    except (ExtractionError, OSError, ValueError, KeyError, TypeError) as error:
        print(f"Extraction incomplete: {error}. Saved raw files are retained; recover with --offline after fixing the cause.", file=sys.stderr)
        return 1
    print(f"Extraction {checkpoint['status']}: {checkpoint['reason']}; "
          f"{checkpoint['row_counts']['unique_products']}/{args.target} unique products.\n"
          f"Analysis CSV: {checkpoint['analysis_csv']}")
    if checkpoint["error"]:
        print(checkpoint["error"], file=sys.stderr)
    return 0 if args.offline or checkpoint["status"] == "complete" else 2


if __name__ == "__main__":
    sys.exit(main())
