"""Offline Phase 3B: five simple tables, preserved observations, explicit flags.

Run from the repository root: python -m src.clean_transform
Only data/cleaned/*.csv is published. Existing differing outputs are never replaced.
"""

import argparse
import json
import math
from pathlib import Path
import re
import unicodedata

import numpy as np
import pandas as pd

if __package__:
    from . import download_dataset as extraction
else:
    import download_dataset as extraction


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT = Path("data/processed/food_products_analysis_combined_725f8a023f0f8ee6.csv")
CATEGORIES = {
    "breakfast-cereals": "Breakfast cereals", "yogurts": "Yogurts",
    "biscuits": "Biscuits", "cereal-bars": "Cereal bars",
}
# Neutral output name -> (existing CSV column, saved nutriments key).
NUTRIENTS = {
    "energy_kcal": ("energy_kcal_100g", "energy-kcal_100g"),
    "energy_kj": ("energy_kj_100g", "energy-kj_100g"),
    "protein_g": ("protein_g_100g", "proteins_100g"),
    "carbohydrates_g": ("carbohydrates_g_100g", "carbohydrates_100g"),
    "sugars_g": ("sugars_g_100g", "sugars_100g"),
    "fat_g": ("fat_g_100g", "fat_100g"),
    "saturated_fat_g": ("saturated_fat_g_100g", "saturated-fat_100g"),
    "fiber_g": ("fiber_g_100g", "fiber_100g"),
    "salt_g": ("salt_g_100g", "salt_100g"),
}
CORE = [name for name in NUTRIENTS if name != "energy_kj"]
TABLES = ("brands", "products", "categories", "product_categories", "nutrition")


def read_csv(path):
    """Only blank cells are missing; literal NA labels and leading zeros survive."""
    return pd.read_csv(path, dtype="string", keep_default_na=False, na_values=[""])


def normalize_text(value):
    if pd.isna(value):
        return pd.NA
    return " ".join(unicodedata.normalize("NFC", str(value)).split()) or pd.NA


def primary_brand(value):
    if pd.isna(value):
        return pd.NA
    for token in str(value).split(","):
        normalized = normalize_text(token)
        if pd.notna(normalized):
            return normalized
    return pd.NA


def validate_input(frame):
    required = {"barcode", "product_name", "brands", "nutriscore_grade", "nova_group",
                "extraction_categories", "extraction_category", "category_membership_count",
                "extraction_id", "source_page", "source_record_index", "record_origin",
                "extracted_at_utc", *[v[0] for v in NUTRIENTS.values()]}
    if not required.issubset(frame.columns) or frame.empty:
        raise ValueError("Missing required input columns or empty input")
    if frame.barcode.map(lambda x: extraction.barcode_value(x)[1] is not None).any():
        raise ValueError("Missing or invalid barcode; identifiers must remain exact strings")
    if frame.barcode.duplicated().any():
        raise ValueError("Duplicate barcode; do not silently deduplicate the combined input")
    for row in frame.itertuples(index=False):
        members = str(row.extraction_categories).split(";")
        if (len(members) != len(set(members)) or not set(members).issubset(CATEGORIES)
                or row.extraction_category not in members
                or str(len(members)) != str(row.category_membership_count)):
            raise ValueError("Invalid or inconsistent extraction memberships")
    if (frame.nutriscore_grade.notna() & ~frame.nutriscore_grade.isin(list("abcde"))).any():
        raise ValueError("Unexpected Nutri-Score classification")
    nova = pd.to_numeric(frame.nova_group, errors="coerce")
    if (frame.nova_group.notna() & ~nova.isin([1, 2, 3, 4])).any():
        raise ValueError("Unexpected NOVA classification")


def load_inputs(root=PROJECT_ROOT):
    """Verify saved provenance before using raw measurement-basis metadata.

    No extraction Store/runner is used: these reads cannot trigger downloads or
    rebuild checkpoints. Only selected, non-sensitive source fields are returned.
    """
    root = Path(root)
    frame = read_csv(root / INPUT)
    validate_input(frame)
    metadata = extraction.read_json((root / INPUT).with_suffix(".json"))
    if extraction.digest((root / INPUT).read_bytes()) != metadata["output_csv_sha256"]:
        raise ValueError("Combined CSV checksum mismatch")
    if metadata["analysis_columns"] != list(frame.columns):
        raise ValueError("Combined CSV schema mismatch")
    lookup, memberships = {}, {}
    source_count = 0
    for extraction_id in sorted(frame.extraction_id.unique()):
        if not isinstance(extraction_id, str) or not re.fullmatch(r"[0-9a-f]{16}", extraction_id):
            raise ValueError("Invalid extraction ID")
        directory = root / "data/raw/extractions" / extraction_id
        checkpoint = extraction.read_json(directory / "checkpoint.json")
        category = checkpoint["configuration"]["query_parameters"]["categories_tags_en"]
        if checkpoint["status"] != "complete" or category not in CATEGORIES:
            raise ValueError("Incomplete or unexpected source extraction")
        for page in checkpoint["completed_pages"]:
            relative = Path("data/raw/extractions") / extraction_id / "pages" / f"page_{page:06d}.json"
            envelope = extraction.read_json(root / relative)
            checksum = extraction.digest(extraction.json_bytes(envelope["response"]))
            if (checksum != envelope["response_sha256"]
                    or checksum != checkpoint["page_response_sha256"][str(page)]):
                raise ValueError("Saved response checksum mismatch")
            if envelope["page"] != page or envelope["configuration"] != checkpoint["configuration"]:
                raise ValueError("Saved page configuration mismatch")
            for index, product in enumerate(envelope["response"]["products"]):
                source_count += 1
                barcode = product.get("code")
                memberships.setdefault(barcode, set()).add(category)
                lookup[(extraction_id, page, index)] = (product, relative.as_posix(), checksum)
    if source_count != metadata["raw_records"] or len(frame) != metadata["unique_products"]:
        raise ValueError("Source counts do not reconcile")
    sources = []
    for row in frame.itertuples(index=False):
        product, relative, checksum = lookup[(row.extraction_id, int(row.source_page), int(row.source_record_index))]
        if (product.get("code") != row.barcode
                or memberships[row.barcode] != set(row.extraction_categories.split(";"))):
            raise ValueError("Product identity or source memberships do not match")
        for column, raw_key in NUTRIENTS.values():
            original = extraction.numeric((product.get("nutriments") or {}).get(raw_key))
            exported = getattr(row, column)
            if original is None:
                matches = pd.isna(exported)
            else:
                matches = pd.notna(exported) and math.isclose(float(exported), original, rel_tol=1e-12, abs_tol=1e-12)
            if not matches:
                raise ValueError("Nutrient does not match its retained source record")
        declared = product.get("nutrition_data_per")
        grade = product.get("nutriscore_grade")
        sources.append({
            "measurement_basis": declared if declared in ("100g", "100ml") else "unknown",
            "reported_measurement_basis": declared,
            "nutriscore_status": "reported" if pd.notna(row.nutriscore_grade) else
                {"unknown": "unknown", "not-applicable": "not_applicable", None: "missing"}.get(grade, "invalid"),
            "source_relative_path": relative, "source_response_sha256": checksum,
        })
    return frame, pd.DataFrame(sources, index=frame.index).astype("string")


def build_nutrition(frame, sources):
    """Keep individual invalidity separate from unresolved multi-field review.

    Reported strings preserve the CSV observation exactly. Numeric values stay
    present for unresolved comparisons, but eligibility excludes all implicated
    operands symmetrically. No IQR rule removes or suppresses observations.
    """
    values, flags, invalid = {}, {}, {}
    rule_masks = {}
    basis = sources.measurement_basis

    def flag(code, mask, fields, clear=False):
        mask = mask.fillna(False).astype(bool)
        rule_masks[code] = rule_masks.get(code, pd.Series(False, index=frame.index)) | mask
        for name in fields:
            flags[name].loc[mask] += code + ";"
            if clear:
                invalid[name] |= mask

    for name, (column, _) in NUTRIENTS.items():
        reported = frame[column]
        numeric = pd.to_numeric(reported, errors="coerce").astype("Float64")
        boolean_input = reported.map(lambda x: isinstance(x, (bool, np.bool_)))
        values[name] = numeric
        flags[name] = pd.Series("", index=frame.index, dtype="string")
        invalid[name] = pd.Series(False, index=frame.index)
        flag("NUM_PARSE", reported.notna() & (numeric.isna() | boolean_input), [name], True)
        flag("NUM_NONFINITE", numeric.notna() & ~np.isfinite(numeric), [name], True)
        flag("NUM_NEGATIVE", numeric.lt(0), [name], True)
        if name.startswith("energy"):
            limit = 1000 if name == "energy_kcal" else 4184
            flag("ENERGY_EXTREME", numeric.gt(limit), [name], True)
        else:
            # On unknown basis this is a conservative screen, not a verified
            # mass contradiction. Explicit volume concentrations need review.
            flag("GRAM_GT100", numeric.gt(100) & basis.ne("100ml"), [name], True)
            flag("VOLUME_GRAM_GT100", numeric.gt(100) & basis.eq("100ml"), [name])

    numbers = pd.DataFrame(values)
    finite = numbers.where(np.isfinite(numbers))
    flag("SUGAR_GT_CARB", finite.sugars_g.gt(finite.carbohydrates_g + .5),
         ["sugars_g", "carbohydrates_g"])
    flag("SATFAT_GT_FAT", finite.saturated_fat_g.gt(finite.fat_g + .5),
         ["saturated_fat_g", "fat_g"])
    macros = ["protein_g", "carbohydrates_g", "fat_g"]
    flag("MACRO_SUM_GT105", finite[macros].sum(axis=1, min_count=3).gt(105) & basis.ne("100ml"), macros)
    gap = (finite.energy_kcal - finite.energy_kj / 4.184).abs()
    tolerance = np.maximum(20, finite.energy_kcal * .1)
    flag("ENERGY_DISAGREEMENT", gap.gt(tolerance), ["energy_kcal", "energy_kj"])

    output = pd.DataFrame({"barcode": frame.barcode, "measurement_basis": basis,
                           "reported_measurement_basis": sources.reported_measurement_basis})
    eligible = {}
    for name, (column, _) in NUTRIENTS.items():
        output[f"reported_{name}_per_100"] = frame[column].astype("string")
        output[f"{name}_per_100"] = numbers[name].mask(invalid[name]).astype("Float64")
        output[f"{name}_flags"] = flags[name].str.rstrip(";").replace("", pd.NA)
        eligible[name] = output[f"{name}_per_100"].notna() & flags[name].eq("")
        output[f"{name}_eligible"] = eligible[name].astype("boolean")
    explicit_basis = basis.isin(["100g", "100ml"])
    for derived, numerator, denominator, multiplier in [
        ("protein_g_per_100kcal", "protein_g", "energy_kcal", 100),
        ("sugar_to_carbohydrate_ratio", "sugars_g", "carbohydrates_g", 1),
    ]:
        allowed = explicit_basis & eligible[numerator] & eligible[denominator] & numbers[denominator].gt(0)
        ratio = numbers[numerator] / numbers[denominator].where(allowed) * multiplier
        output[derived] = ratio.where(allowed & np.isfinite(ratio)).astype("Float64")
    output["nutrition_completeness_pct"] = frame[[NUTRIENTS[n][0] for n in CORE]].notna().mean(axis=1).mul(100).astype("Float64")
    output["has_numeric_flags"] = pd.DataFrame(rule_masks).any(axis=1).astype("boolean")
    return output, pd.DataFrame(rule_masks).astype(bool)


def transform(frame, sources):
    validate_input(frame)
    if not sources.index.equals(frame.index) or sources.measurement_basis.isna().any():
        raise ValueError("Source metadata is not aligned with input")
    primary = frame.brands.map(primary_brand).astype("string")
    brands = pd.DataFrame({"brand_name": sorted(primary.dropna().unique())}, dtype="string")
    # Exact normalized label IDs stay stable across runs without alias inference.
    brands.insert(0, "brand_id", "brand:" + brands.brand_name)
    products = pd.DataFrame({
        "barcode": frame.barcode,
        "product_name": frame.product_name.map(normalize_text).astype("string"),
        "original_product_name": frame.product_name,
        "brand_id": ("brand:" + primary).astype("string"),
        "original_brands": frame.brands,
        "nutriscore_grade": frame.nutriscore_grade,
        "nutriscore_status": sources.nutriscore_status,
        "nova_group": pd.to_numeric(frame.nova_group).astype("Int64"),
        "primary_category_id": frame.extraction_category,
        "extraction_id": frame.extraction_id,
        "source_page": pd.to_numeric(frame.source_page).astype("Int64"),
        "source_record_index": pd.to_numeric(frame.source_record_index).astype("Int64"),
        "extracted_at_utc": pd.to_datetime(frame.extracted_at_utc, utc=True, errors="raise"),
        "record_origin": frame.record_origin,
        "source_relative_path": sources.source_relative_path,
        "source_response_sha256": sources.source_response_sha256,
    })
    categories = pd.DataFrame(list(CATEGORIES.items()), columns=["category_id", "category_name"], dtype="string")
    links = pd.DataFrame({"barcode": frame.barcode, "category_id": frame.extraction_categories.str.split(";")}).explode("category_id", ignore_index=True).astype("string")
    nutrition, rules = build_nutrition(frame, sources)
    tables = dict(zip(TABLES, [brands, products, categories, links, nutrition]))
    for name, table in tables.items():
        keys = {"brands": ["brand_id"], "categories": ["category_id"],
                "product_categories": ["barcode", "category_id"]}.get(name, ["barcode"])
        tables[name] = table.sort_values(keys, kind="stable").reset_index(drop=True)
    validate_tables(tables, frame)
    return tables, rules


def validate_tables(tables, original):
    """Check identities and relationships on both in-memory and reloaded tables."""
    for name, keys in {"brands": ["brand_id"], "products": ["barcode"],
                       "categories": ["category_id"], "nutrition": ["barcode"],
                       "product_categories": ["barcode", "category_id"]}.items():
        table = tables[name]
        if table[keys].isna().any().any() or table.duplicated(keys).any():
            raise ValueError(f"Invalid primary key in {name}")
    products, nutrition = tables["products"], tables["nutrition"]
    links = tables["product_categories"]
    if set(products.barcode) != set(original.barcode) or set(nutrition.barcode) != set(original.barcode):
        raise ValueError("Product identities were lost or added")
    for child, parent in [(products.brand_id.dropna(), tables["brands"].brand_id),
                          (products.primary_category_id, tables["categories"].category_id),
                          (links.barcode, products.barcode),
                          (links.category_id, tables["categories"].category_id)]:
        if not set(child).issubset(set(parent)):
            raise ValueError("Foreign key does not resolve")
    expected = {(row.barcode, category) for row in original.itertuples()
                for category in row.extraction_categories.split(";")}
    if set(links.itertuples(index=False, name=None)) != expected:
        raise ValueError("Category memberships changed")
    if dict(tables["categories"].itertuples(index=False, name=None)) != CATEGORIES:
        raise ValueError("Category dimension differs from the four extraction groups")
    reported = nutrition.set_index("barcode")
    source = original.set_index("barcode").loc[reported.index]
    for name, (column, _) in NUTRIENTS.items():
        pd.testing.assert_series_equal(reported[f"reported_{name}_per_100"], source[column], check_names=False)


def reload_tables(directory):
    """CSV has no dtype metadata: explicitly restore strings, nullable numbers/flags."""
    tables = {name: read_csv(Path(directory) / f"{name}.csv") for name in TABLES}
    products = tables["products"]
    for column in ("nova_group", "source_page", "source_record_index"):
        products[column] = pd.to_numeric(products[column]).astype("Int64")
    products["extracted_at_utc"] = pd.to_datetime(products.extracted_at_utc, utc=True)
    nutrition = tables["nutrition"]
    for column in nutrition.columns:
        if column.endswith("_eligible") or column == "has_numeric_flags":
            if not nutrition[column].isin(["True", "False"]).all():
                raise ValueError("Invalid Boolean export")
            nutrition[column] = nutrition[column].map({"True": True, "False": False}).astype("boolean")
        elif (column.endswith("_per_100") and not column.startswith("reported_")) or column in (
            "protein_g_per_100kcal", "sugar_to_carbohydrate_ratio", "nutrition_completeness_pct"
        ):
            nutrition[column] = pd.to_numeric(nutrition[column]).astype("Float64")
    return tables


def publish(tables, root=PROJECT_ROOT):
    """Write only the five named outputs; identical reruns leave them untouched.

    Writes are atomic per CSV, not a transaction across all five. An interrupted
    first run can be rerun to finish missing identical files. Different existing
    outputs require explicit human review and are not overwritten.
    """
    root = Path(root).resolve()
    destination = root / "data/cleaned"
    if destination.resolve() != destination or destination.is_symlink():
        raise ValueError("Output directory must not redirect outside data/cleaned")
    payloads = {destination / f"{name}.csv": tables[name].to_csv(index=False, lineterminator="\n").encode("utf-8") for name in TABLES}
    # Check every path before writing the first file.
    for path, payload in payloads.items():
        if path.is_symlink() or (path.exists() and (not path.is_file() or path.read_bytes() != payload)):
            raise ValueError(f"Refusing to replace differing or redirected output: {path.name}")
    for path, payload in payloads.items():
        if not path.exists():
            extraction.atomic_write(path, payload)
    return destination


def protected_snapshot(root=PROJECT_ROOT):
    root = Path(root)
    return {p.relative_to(root).as_posix(): (extraction.digest(p.read_bytes()), p.stat().st_size, p.stat().st_mtime_ns)
            for folder in ("data", "notebooks") for p in (root / folder).rglob("*")
            if p.is_file() and not p.is_relative_to(root / "data/cleaned")}


def run(root=PROJECT_ROOT):
    before = protected_snapshot(root)
    frame, sources = load_inputs(root)
    tables, rules = transform(frame, sources)
    directory = publish(tables, root)
    reloaded = reload_tables(directory)
    validate_tables(reloaded, frame)
    for name in TABLES:
        pd.testing.assert_frame_equal(tables[name], reloaded[name], check_exact=False, rtol=1e-12, atol=1e-12)
    if protected_snapshot(root) != before:
        raise ValueError("Protected dataset/notebook changed during transformation")
    nutrition = tables["nutrition"]
    summary = {
        "rows": {name: len(table) for name, table in tables.items()},
        "measurement_basis": sources.measurement_basis.value_counts().to_dict(),
        "rule_products": {code: int(count) for code, count in rules.sum().items()},
        "products_with_numeric_flags": int(rules.any(axis=1).sum()),
        "new_null_measurements": sum(int((nutrition[f"reported_{name}_per_100"].notna() & nutrition[f"{name}_per_100"].isna()).sum()) for name in NUTRIENTS),
        "validation": "PK/FK, source observations, CSV reload and preservation checks passed",
    }
    return summary


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        print(json.dumps(run(), indent=2))
    except (ValueError, KeyError, OSError, AssertionError) as error:
        # Avoid printing private source payloads or machine-specific paths.
        raise SystemExit(f"Transformation failed ({type(error).__name__}). Review input integrity and output conflicts.") from None


if __name__ == "__main__":
    main()
