"""Phase 5 schema contract regression checks; no database or network access."""

import copy
import unittest

from scripts.generate_erd import ROOT, read_schema, dbml
from scripts.validate_phase5 import read_tables, validate


class SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = read_tables()

    def test_actual_outputs_and_editable_erd(self):
        result = validate(self.tables)
        self.assertEqual({t: r["rows"] for t, r in result.items()},
                         dict(brands=525, products=1987, categories=4, product_categories=2000, nutrition=1987))
        schema = read_schema()
        self.assertEqual((ROOT / "reports/erd.dbml").read_text(encoding="utf-8"), dbml(schema))
        self.assertEqual(sum(len(t["refs"]) for t in schema.values()), 7)
        self.assertEqual(sum(r["barcode"].startswith("0") for r in self.tables["products"]), 83)

    def test_duplicate_and_unresolved_keys_rejected(self):
        for table, col, value in [("products", "brand_id", "brand:nonexistent"),
                                   ("product_categories", "category_id", "nonexistent")]:
            tables = copy.deepcopy(self.tables)
            tables[table][0][col] = value
            with self.subTest(table=table), self.assertRaises(AssertionError):
                validate(tables)
        tables = copy.deepcopy(self.tables)
        tables["product_categories"].append(tables["product_categories"][0].copy())
        with self.assertRaisesRegex(AssertionError, "Duplicate key"):
            validate(tables)

    def test_required_nutrition_and_primary_membership(self):
        for table in ("nutrition", "product_categories"):
            tables = copy.deepcopy(self.tables)
            tables[table].pop(0)
            with self.subTest(table=table), self.assertRaisesRegex(AssertionError, "Unresolved FK"):
                validate(tables)

    def test_classification_and_numeric_domain_rejected(self):
        for table, col, value in [("products", "nova_group", "5"),
                                   ("products", "nutriscore_grade", "z"),
                                   ("products", "nutriscore_status", "unknown"),
                                   ("nutrition", "measurement_basis", "serving"),
                                   ("nutrition", "protein_g_per_100", "-1"),
                                   ("nutrition", "protein_g_per_100", "NaN"),
                                   ("nutrition", "nutrition_completeness_pct", "101")]:
            tables = copy.deepcopy(self.tables)
            tables[table][0][col] = value
            with self.subTest(column=col, value=value), self.assertRaises(AssertionError):
                validate(tables)

    def test_suspicious_originals_and_nullable_measurements_allowed(self):
        tables = copy.deepcopy(self.tables)
        row = tables["nutrition"][0]
        row.update(measurement_basis="100ml", protein_g_per_100="101",
                   reported_protein_g_per_100="101", protein_g_flags="VOLUME_GRAM_GT100",
                   protein_g_eligible="False", sugars_g_per_100="16", carbohydrates_g_per_100="4.5",
                   salt_g_per_100="", reported_salt_g_per_100="295")
        validate(tables)

    def test_missing_column_or_required_value_rejected(self):
        tables = copy.deepcopy(self.tables)
        del tables["products"][0]["original_brands"]
        with self.assertRaisesRegex(AssertionError, "column/order"):
            validate(tables)
        tables = copy.deepcopy(self.tables)
        tables["nutrition"][0]["energy_kcal_eligible"] = ""
        with self.assertRaisesRegex(AssertionError, "NOT NULL"):
            validate(tables)


if __name__ == "__main__":
    unittest.main()
