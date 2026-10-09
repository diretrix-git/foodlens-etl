"""Offline cleaning tests; edited real-record fixtures never leave temporary data."""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import requests

from src import clean_transform as c


class TransformationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(requests.Session, "request", side_effect=AssertionError("Live HTTP forbidden")):
            cls.frame, cls.sources = c.load_inputs()
            cls.tables, cls.rules = c.transform(cls.frame, cls.sources)

    def setUp(self):
        blocker = patch.object(requests.Session, "request", side_effect=AssertionError("Live HTTP forbidden"))
        blocker.start()
        self.addCleanup(blocker.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def one_record(self, **values):
        # Deliberately modified copies test boundary/failure cases only.
        frame = self.frame.iloc[:1].copy().reset_index(drop=True)
        sources = self.sources.iloc[:1].copy().reset_index(drop=True)
        for column, _ in c.NUTRIENTS.values():
            frame[column] = pd.Series([pd.NA], dtype="string")
        sources["measurement_basis"] = "100g"
        sources["reported_measurement_basis"] = "100g"
        for column, value in values.items():
            frame[column] = pd.Series([value], dtype="string")
        return frame, sources

    def test_real_baseline_and_overlap(self):
        self.assertEqual({k: len(v) for k, v in self.tables.items()},
                         dict(brands=525, products=1987, categories=4, product_categories=2000, nutrition=1987))
        links = self.tables["product_categories"]
        self.assertEqual(int(links.groupby("barcode").size().gt(1).sum()), 13)
        self.assertEqual(links.category_id.value_counts().to_dict(), {k: 500 for k in c.CATEGORIES})
        self.assertEqual(self.sources.measurement_basis.value_counts().to_dict(),
                         {"100g": 1254, "unknown": 728, "100ml": 5})
        self.assertEqual(int(self.rules.any(axis=1).sum()), 91)
        self.assertEqual(int(self.rules.ENERGY_DISAGREEMENT.sum()), 83)

    def test_missing_nutrients_are_not_zero_or_numeric_errors(self):
        f, s = self.one_record()
        nutrition, rules = c.build_nutrition(f, s)
        for name in c.NUTRIENTS:
            self.assertTrue(pd.isna(nutrition.loc[0, f"{name}_per_100"]))
            self.assertTrue(pd.isna(nutrition.loc[0, f"{name}_flags"]))
            self.assertFalse(nutrition.loc[0, f"{name}_eligible"])
        self.assertFalse(rules.any().any())
        self.assertEqual(nutrition.loc[0, "nutrition_completeness_pct"], 0)

    def test_text_and_first_nonempty_brand(self):
        self.assertEqual(c.primary_brand(" ,  Brand  A ,Brand B"), "Brand A")
        self.assertEqual(c.normalize_text("  Cafe\u0301\t  bar  "), "Caf\u00e9 bar")
        self.assertTrue(pd.isna(c.primary_brand(" , , ")))
        self.assertNotEqual(c.primary_brand("Brand"), c.primary_brand("BRAND"))
        f, s = self.one_record()
        f.loc[0, "brands"] = " ,  Brand  A ,Brand B"
        f.loc[0, "product_name"] = "  Sample\t name "
        tables, _ = c.transform(f, s)
        row = tables["products"].iloc[0]
        self.assertEqual(row.original_brands, f.loc[0, "brands"])
        self.assertEqual(row.original_product_name, f.loc[0, "product_name"])
        self.assertEqual(row.product_name, "Sample name")
        self.assertEqual(row.brand_id, "brand:Brand A")

    def test_missing_names_brands_classifications_retained(self):
        f, s = self.one_record()
        for name in ["product_name", "brands", "nutriscore_grade", "nova_group"]:
            f.loc[0, name] = pd.NA
        tables, _ = c.transform(f, s)
        self.assertEqual(len(tables["products"]), 1)
        self.assertEqual(len(tables["brands"]), 0)
        self.assertTrue(tables["products"][["product_name", "brand_id", "nutriscore_grade", "nova_group"]].isna().all().all())

    def test_invalid_or_duplicate_barcode_is_rejected(self):
        for barcode in [pd.NA, " 00123456", "1234567", "abcdefgh", 12345678]:
            f, s = self.one_record()
            f["barcode"] = pd.Series([barcode], dtype="object")
            with self.subTest(barcode=barcode), self.assertRaises(ValueError):
                c.transform(f, s)
        f, s = self.one_record()
        with self.assertRaises(ValueError):
            c.transform(pd.concat([f, f], ignore_index=True), pd.concat([s, s], ignore_index=True))

    def test_numeric_invalidity_preserves_reported_value(self):
        for raw, reason in [("-1", "NUM_NEGATIVE"), ("oops", "NUM_PARSE"), ("inf", "NUM_NONFINITE"), ("True", "NUM_PARSE")]:
            f, s = self.one_record(protein_g_100g=raw)
            n, _ = c.build_nutrition(f, s)
            self.assertEqual(n.loc[0, "reported_protein_g_per_100"], raw)
            self.assertTrue(pd.isna(n.loc[0, "protein_g_per_100"]))
            self.assertIn(reason, n.loc[0, "protein_g_flags"])
        f, s = self.one_record()
        f["protein_g_100g"] = pd.Series([True], dtype=object)
        n, _ = c.build_nutrition(f, s)
        self.assertTrue(pd.isna(n.loc[0, "protein_g_per_100"]))

    def test_known_extremes_clear_only_the_individual_measurement(self):
        n = self.tables["nutrition"].set_index("barcode")
        for barcode, name, value in [("8901063139329", "salt_g", 295),
                                     ("0602652419263", "carbohydrates_g", 120),
                                     ("8410376033267", "energy_kcal", 3305.1094890511)]:
            self.assertAlmostEqual(float(n.loc[barcode, f"reported_{name}_per_100"]), value, places=5)
            self.assertTrue(pd.isna(n.loc[barcode, f"{name}_per_100"]))
        self.assertEqual(sum(int((n[f"reported_{k}_per_100"].notna() & n[f"{k}_per_100"].isna()).sum()) for k in c.NUTRIENTS), 5)
        self.assertEqual(n.loc["8410376033267", "energy_kj_per_100"], 1835)

    def test_cross_field_review_keeps_values_and_excludes_both_operands(self):
        f, s = self.one_record(sugars_g_100g="16", carbohydrates_g_100g="4.5",
                               fat_g_100g="1", saturated_fat_g_100g="3")
        n, _ = c.build_nutrition(f, s)
        for name, expected in [("sugars_g", 16), ("carbohydrates_g", 4.5), ("fat_g", 1), ("saturated_fat_g", 3)]:
            self.assertEqual(n.loc[0, f"{name}_per_100"], expected)
            self.assertFalse(n.loc[0, f"{name}_eligible"])
        self.assertTrue(pd.isna(n.loc[0, "sugar_to_carbohydrate_ratio"]))

    def test_energy_review_does_not_choose_one_source(self):
        f, s = self.one_record(energy_kcal_100g="400", energy_kj_100g="1000", protein_g_100g="10")
        n, _ = c.build_nutrition(f, s)
        self.assertEqual(n.loc[0, "energy_kcal_per_100"], 400)
        self.assertEqual(n.loc[0, "energy_kj_per_100"], 1000)
        self.assertFalse(n.loc[0, "energy_kcal_eligible"])
        self.assertFalse(n.loc[0, "energy_kj_eligible"])
        self.assertTrue(pd.isna(n.loc[0, "protein_g_per_100kcal"]))

    def test_strict_threshold_boundaries(self):
        f, s = self.one_record(salt_g_100g="100", energy_kcal_100g="1000",
                               energy_kj_100g="4184", sugars_g_100g="10.5", carbohydrates_g_100g="10",
                               fat_g_100g="10", saturated_fat_g_100g="10.5", protein_g_100g="85")
        _, rules = c.build_nutrition(f, s)
        self.assertFalse(rules.any().any())
        f.loc[0, "salt_g_100g"] = "100.01"
        f.loc[0, "protein_g_100g"] = "85.01"
        _, rules = c.build_nutrition(f, s)
        self.assertTrue(rules.loc[0, "GRAM_GT100"])
        self.assertTrue(rules.loc[0, "MACRO_SUM_GT105"])

    def test_basis_and_derived_values(self):
        f, s = self.one_record(energy_kcal_100g="200", protein_g_100g="10",
                               sugars_g_100g="5", carbohydrates_g_100g="20")
        for basis in ["100g", "100ml", "unknown"]:
            s["measurement_basis"] = basis
            n, _ = c.build_nutrition(f, s)
            if basis == "unknown":
                self.assertTrue(pd.isna(n.loc[0, "protein_g_per_100kcal"]))
                self.assertTrue(pd.isna(n.loc[0, "sugar_to_carbohydrate_ratio"]))
            else:
                self.assertEqual(n.loc[0, "protein_g_per_100kcal"], 5)
                self.assertEqual(n.loc[0, "sugar_to_carbohydrate_ratio"], .25)
            strict = n.measurement_basis.eq("100g") & n.energy_kcal_eligible
            self.assertEqual(bool(strict.iloc[0]), basis == "100g")
        s["measurement_basis"] = "100ml"
        f.loc[0, "salt_g_100g"] = "101"
        n, _ = c.build_nutrition(f, s)
        self.assertEqual(n.loc[0, "salt_g_per_100"], 101)
        self.assertIn("VOLUME_GRAM_GT100", n.loc[0, "salt_g_flags"])

    def test_zero_and_missing_denominators(self):
        for denominator in ["0", pd.NA]:
            f, s = self.one_record(energy_kcal_100g=denominator, protein_g_100g="0",
                                   carbohydrates_g_100g=denominator, sugars_g_100g="0")
            n, _ = c.build_nutrition(f, s)
            self.assertTrue(pd.isna(n.loc[0, "protein_g_per_100kcal"]))
            self.assertTrue(pd.isna(n.loc[0, "sugar_to_carbohydrate_ratio"]))
        f, s = self.one_record(energy_kcal_100g="100", energy_kj_100g="418.4", protein_g_100g="0")
        n, _ = c.build_nutrition(f, s)
        self.assertEqual(n.loc[0, "protein_g_per_100kcal"], 0)
        self.assertEqual(n.loc[0, "nutrition_completeness_pct"], 25)

    def test_iqr_extreme_alone_is_not_removed(self):
        n = self.tables["nutrition"].set_index("barcode")
        self.assertEqual(n.loc["3159470001424", "fiber_g_per_100"], 27)
        self.assertTrue(n.loc["3159470001424", "fiber_g_eligible"])

    def test_broken_foreign_key_or_membership_is_rejected(self):
        for table, column, value in [("products", "brand_id", "brand:nonexistent"),
                                      ("nutrition", "barcode", "00000000"),
                                      ("product_categories", "category_id", "unexpected")]:
            tables = copy.deepcopy(self.tables)
            tables[table].loc[0, column] = value
            with self.subTest(table=table), self.assertRaises(ValueError):
                c.validate_tables(tables, self.frame)
        tables = copy.deepcopy(self.tables)
        tables["product_categories"] = tables["product_categories"].iloc[1:]
        with self.assertRaises(ValueError):
            c.validate_tables(tables, self.frame)

    def test_csv_reload_leading_zeros_and_repeat_publication(self):
        destination = c.publish(self.tables, self.root)
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in destination.glob("*.csv")}
        loaded = c.reload_tables(destination)
        c.validate_tables(loaded, self.frame)
        self.assertEqual(int(loaded["products"].barcode.str.startswith("0").sum()), 83)
        for name in c.TABLES:
            pd.testing.assert_frame_equal(self.tables[name], loaded[name], check_exact=False, rtol=1e-12, atol=1e-12)
        c.publish(self.tables, self.root)
        self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in destination.glob("*.csv")})

    def test_output_conflict_is_not_overwritten(self):
        destination = self.root / "data/cleaned"
        destination.mkdir(parents=True)
        conflict = destination / "nutrition.csv"
        conflict.write_bytes(b"existing output\n")
        with self.assertRaises(ValueError):
            c.publish(self.tables, self.root)
        self.assertEqual(conflict.read_bytes(), b"existing output\n")
        self.assertEqual(len(list(destination.iterdir())), 1)

    def test_atomic_failure_leaves_no_partial_csv(self):
        with patch.object(c.extraction.os, "replace", side_effect=OSError("mocked disk failure")):
            with self.assertRaises(OSError):
                c.publish(self.tables, self.root)
        self.assertEqual(list((self.root / "data/cleaned").iterdir()), [])

    def test_full_run_preserves_sources_and_repeats(self):
        shutil.copytree(c.PROJECT_ROOT / "data/raw/extractions", self.root / "data/raw/extractions")
        (self.root / c.INPUT.parent).mkdir(parents=True)
        for suffix in [".csv", ".json"]:
            shutil.copy2((c.PROJECT_ROOT / c.INPUT).with_suffix(suffix), (self.root / c.INPUT).with_suffix(suffix))
        before = c.protected_snapshot(self.root)
        first = c.run(self.root)
        second = c.run(self.root)
        self.assertEqual(first, second)
        self.assertEqual(before, c.protected_snapshot(self.root))
        self.assertEqual(first["new_null_measurements"], 5)
        page = next((self.root / "data/raw/extractions").glob("*/pages/page_000001.json"))
        saved = page.read_bytes()
        envelope = json.loads(saved)
        envelope["response"]["products"][0]["code"] = "00000000"
        page.write_text(json.dumps(envelope), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "checksum"):
            c.load_inputs(self.root)
        page.write_bytes(saved)
        source = self.root / c.INPUT
        source.write_bytes(source.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            c.load_inputs(self.root)

if __name__ == "__main__":
    unittest.main()
