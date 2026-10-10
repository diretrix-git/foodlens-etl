"""Phase 7: execute eight read-only SQL reports against Neon PostgreSQL.

Connects using DATABASE_URL from the local .env file (never printed).
Runs all eight SELECT reports inside a single read-only, repeatable-read
transaction.  Exports each result to reports/sql_results/<name>.csv.
Verifies that table row counts are identical before and after.

Run from the repository root:
    .venv\\Scripts\\python.exe scripts/run_sql_reports.py

No INSERT, UPDATE, DELETE, TRUNCATE, DROP or ALTER is executed.
"""

import csv
import io
import os
from pathlib import Path
import re
import sys
import textwrap

import certifi
import psycopg
from psycopg.conninfo import conninfo_to_dict
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "reports" / "sql_results"
TABLES = ("brands", "categories", "products", "product_categories", "nutrition")

# ---------------------------------------------------------------------------
# Query definitions: (filename_stem, short label, SQL)
# ---------------------------------------------------------------------------
REPORTS = [
    (
        "q1_products_per_category",
        "Q1: Products per category",
        # Q1: INNER JOIN, GROUP BY, COUNT, window for percentage
        """\
        SELECT
            c.category_name,
            COUNT(pc.barcode)                              AS total_memberships,
            ROUND(
                COUNT(pc.barcode) * 100.0
                / SUM(COUNT(pc.barcode)) OVER (),
                2
            )                                              AS pct_of_all_memberships,
            COUNT(DISTINCT pc.barcode)                     AS unique_products
        FROM public.categories  c
        INNER JOIN public.product_categories pc ON pc.category_id = c.category_id
        GROUP BY c.category_id, c.category_name
        ORDER BY total_memberships DESC
        """,
    ),
    (
        "q2_median_sugar_by_category",
        "Q2: Median sugar content per 100 g by category",
        # Q2: INNER JOIN, WHERE eligibility filter, PERCENTILE_CONT, GROUP BY
        """\
        SELECT
            c.category_name,
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY n.sugars_g_per_100
            )                                              AS median_sugars_g_per_100g,
            COUNT(*)                                       AS eligible_memberships,
            ROUND(AVG(n.sugars_g_per_100)::numeric, 4)    AS mean_sugars_g_per_100g,
            MIN(n.sugars_g_per_100)                        AS min_sugars_g_per_100g,
            MAX(n.sugars_g_per_100)                        AS max_sugars_g_per_100g
        FROM public.categories          c
        INNER JOIN public.product_categories pc ON pc.category_id = c.category_id
        INNER JOIN public.nutrition     n  ON n.barcode = pc.barcode
        WHERE n.measurement_basis = '100g'
          AND n.sugars_g_eligible  = TRUE
        GROUP BY c.category_id, c.category_name
        ORDER BY median_sugars_g_per_100g DESC
        """,
    ),
    (
        "q3_median_protein_by_category",
        "Q3: Median protein content per 100 g by category",
        # Q3: INNER JOIN, WHERE eligibility filter, PERCENTILE_CONT, GROUP BY
        """\
        SELECT
            c.category_name,
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY n.protein_g_per_100
            )                                              AS median_protein_g_per_100g,
            COUNT(*)                                       AS eligible_memberships,
            ROUND(AVG(n.protein_g_per_100)::numeric, 4)   AS mean_protein_g_per_100g,
            MIN(n.protein_g_per_100)                       AS min_protein_g_per_100g,
            MAX(n.protein_g_per_100)                       AS max_protein_g_per_100g
        FROM public.categories          c
        INNER JOIN public.product_categories pc ON pc.category_id = c.category_id
        INNER JOIN public.nutrition     n  ON n.barcode = pc.barcode
        WHERE n.measurement_basis = '100g'
          AND n.protein_g_eligible  = TRUE
        GROUP BY c.category_id, c.category_name
        ORDER BY median_protein_g_per_100g DESC
        """,
    ),
    (
        "q4_top_protein_per_100kcal",
        "Q4: Top products by protein per 100 kcal (with brand)",
        # Q4: LEFT JOIN brands, INNER JOIN, WHERE eligibility, ORDER BY, LIMIT 10
        """\
        SELECT
            p.barcode,
            p.product_name,
            b.brand_name                                   AS primary_brand,
            c.category_name                                AS primary_category,
            n.measurement_basis,
            ROUND(n.protein_g_per_100kcal::numeric, 4)    AS protein_g_per_100kcal,
            n.protein_g_per_100,
            n.energy_kcal_per_100
        FROM public.products    p
        INNER JOIN public.nutrition     n  ON n.barcode = p.barcode
        LEFT  JOIN public.brands        b  ON b.brand_id = p.brand_id
        INNER JOIN public.categories    c  ON c.category_id = p.primary_category_id
        WHERE n.protein_g_per_100kcal IS NOT NULL
          AND n.measurement_basis IN ('100g', '100ml')
          AND n.protein_g_eligible      = TRUE
          AND n.energy_kcal_eligible    = TRUE
          AND n.energy_kcal_per_100 > 0
        ORDER BY n.protein_g_per_100kcal DESC,
                 p.barcode ASC
        LIMIT 10
        """,
    ),
    (
        "q5_nutriscore_by_category",
        "Q5: Nutri-Score grade distribution by category",
        # Q5: INNER JOIN, CASE WHEN counts, GROUP BY, NULLIF
        """\
        SELECT
            c.category_name,
            COUNT(*)                                           AS total_memberships,
            COUNT(CASE WHEN p.nutriscore_grade = 'a' THEN 1 END)   AS grade_a,
            COUNT(CASE WHEN p.nutriscore_grade = 'b' THEN 1 END)   AS grade_b,
            COUNT(CASE WHEN p.nutriscore_grade = 'c' THEN 1 END)   AS grade_c,
            COUNT(CASE WHEN p.nutriscore_grade = 'd' THEN 1 END)   AS grade_d,
            COUNT(CASE WHEN p.nutriscore_grade = 'e' THEN 1 END)   AS grade_e,
            COUNT(CASE WHEN p.nutriscore_status = 'unknown'        THEN 1 END) AS status_unknown,
            COUNT(CASE WHEN p.nutriscore_status = 'not_applicable' THEN 1 END) AS status_not_applicable,
            COUNT(CASE WHEN p.nutriscore_status IN ('missing', 'invalid') THEN 1 END) AS status_missing_invalid,
            ROUND(
                COUNT(CASE WHEN p.nutriscore_grade IS NOT NULL THEN 1 END) * 100.0
                / NULLIF(COUNT(*), 0),
                1
            )                                                  AS pct_with_grade
        FROM public.categories          c
        INNER JOIN public.product_categories pc ON pc.category_id = c.category_id
        INNER JOIN public.products      p  ON p.barcode = pc.barcode
        GROUP BY c.category_id, c.category_name
        ORDER BY c.category_name
        """,
    ),
    (
        "q6_nova_by_category",
        "Q6: NOVA processing classification by category",
        # Q6: INNER JOIN, CASE WHEN, GROUP BY, NULLIF percentage
        """\
        SELECT
            c.category_name,
            COUNT(*)                                               AS total_memberships,
            COUNT(CASE WHEN p.nova_group = 1 THEN 1 END)           AS nova_1_unprocessed,
            COUNT(CASE WHEN p.nova_group = 2 THEN 1 END)           AS nova_2_processed_ingredients,
            COUNT(CASE WHEN p.nova_group = 3 THEN 1 END)           AS nova_3_processed,
            COUNT(CASE WHEN p.nova_group = 4 THEN 1 END)           AS nova_4_ultra_processed,
            COUNT(CASE WHEN p.nova_group IS NULL THEN 1 END)        AS nova_unknown,
            ROUND(
                COUNT(CASE WHEN p.nova_group = 4 THEN 1 END) * 100.0
                / NULLIF(COUNT(CASE WHEN p.nova_group IS NOT NULL THEN 1 END), 0),
                1
            )                                                       AS pct_nova4_of_classified
        FROM public.categories          c
        INNER JOIN public.product_categories pc ON pc.category_id = c.category_id
        INNER JOIN public.products      p  ON p.barcode = pc.barcode
        GROUP BY c.category_id, c.category_name
        ORDER BY c.category_name
        """,
    ),
    (
        "q7_brands_most_products",
        "Q7: Brands with the most products (HAVING > 5)",
        # Q7: INNER JOIN, GROUP BY, HAVING, ORDER BY, LIMIT
        """\
        SELECT
            b.brand_name,
            COUNT(p.barcode)          AS product_count,
            COUNT(CASE WHEN p.nutriscore_grade IS NOT NULL THEN 1 END) AS products_with_grade,
            ROUND(AVG(n.nutrition_completeness_pct)::numeric, 2)       AS avg_nutrition_completeness_pct
        FROM public.brands      b
        INNER JOIN public.products  p ON p.brand_id = b.brand_id
        INNER JOIN public.nutrition n ON n.barcode   = p.barcode
        GROUP BY b.brand_id, b.brand_name
        HAVING COUNT(p.barcode) > 5
        ORDER BY product_count DESC,
                 b.brand_name  ASC
        LIMIT 20
        """,
    ),
    (
        "q8_missing_flagged_by_category",
        "Q8: Missing or flagged nutritional measurements by category",
        # Q8: INNER JOIN, CASE WHEN, GROUP BY, AVG, ORDER BY
        """\
        SELECT
            c.category_name,
            COUNT(pc.barcode)                                               AS total_memberships,
            COUNT(CASE WHEN n.has_numeric_flags = TRUE THEN 1 END)         AS flagged_memberships,
            ROUND(
                COUNT(CASE WHEN n.has_numeric_flags = TRUE THEN 1 END) * 100.0
                / NULLIF(COUNT(*), 0), 1
            )                                                               AS pct_flagged,
            COUNT(CASE WHEN n.measurement_basis != '100g' THEN 1 END)      AS non_100g_basis_memberships,
            ROUND(AVG(
                (CASE WHEN n.energy_kcal_per_100    IS NULL THEN 1 ELSE 0 END) +
                (CASE WHEN n.energy_kj_per_100      IS NULL THEN 1 ELSE 0 END) +
                (CASE WHEN n.protein_g_per_100      IS NULL THEN 1 ELSE 0 END) +
                (CASE WHEN n.carbohydrates_g_per_100 IS NULL THEN 1 ELSE 0 END) +
                (CASE WHEN n.sugars_g_per_100       IS NULL THEN 1 ELSE 0 END) +
                (CASE WHEN n.fat_g_per_100          IS NULL THEN 1 ELSE 0 END) +
                (CASE WHEN n.saturated_fat_g_per_100 IS NULL THEN 1 ELSE 0 END) +
                (CASE WHEN n.fiber_g_per_100        IS NULL THEN 1 ELSE 0 END) +
                (CASE WHEN n.salt_g_per_100         IS NULL THEN 1 ELSE 0 END)
            )::numeric, 2)                                                  AS avg_missing_nutrients_per_product,
            ROUND(AVG(n.nutrition_completeness_pct)::numeric, 2)            AS avg_completeness_pct
        FROM public.categories          c
        INNER JOIN public.product_categories pc ON pc.category_id = c.category_id
        INNER JOIN public.nutrition     n  ON n.barcode = pc.barcode
        GROUP BY c.category_id, c.category_name
        ORDER BY avg_missing_nutrients_per_product DESC,
                 pct_flagged DESC
        """,
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _connection_settings():
    """Load DATABASE_URL from .env; raise with a safe message on misconfiguration."""
    load_dotenv(ROOT / ".env", override=False, interpolate=False)
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit(
            "STOP: DATABASE_URL is missing. "
            "Copy .env.example to .env and configure your Neon URL."
        )
    try:
        if not url.startswith(("postgresql://", "postgres://")):
            raise ValueError
        settings = conninfo_to_dict(url)
        if not all(settings.get(k) for k in ("host", "dbname", "user", "password")):
            raise ValueError
        if any(token in url for token in ("YOUR_", "<", ">", "example.invalid")):
            raise ValueError("Placeholder URL")
        if settings.get("sslmode") not in ("require", "verify-ca", "verify-full"):
            raise ValueError("Weak TLS")
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(
            "STOP: Invalid or incomplete DATABASE_URL. "
            "Check your local configuration. No connection attempted."
        )
    settings.update(sslmode="verify-full", connect_timeout=15)
    settings.setdefault(
        "sslrootcert",
        os.environ.get("PGSSLROOTCERT") or certifi.where(),
    )
    return settings


def _row_counts(cursor):
    """Return {table: count} for all five tables using a read-only cursor."""
    counts = {}
    for table in TABLES:
        cursor.execute(f"SELECT count(*) FROM public.{table}")
        counts[table] = cursor.fetchone()[0]
    return counts


def _dedent(sql):
    return textwrap.dedent(sql).strip()


def _write_csv(path, columns, rows):
    """Write column headers and rows to a CSV file, handling None as empty."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(["" if v is None else v for v in row])


def _column_names(cursor):
    return [desc.name for desc in cursor.description]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("FoodLens Phase 7 — SQL Reporting Runner")
    print("=" * 60)
    print(f"Output directory : {OUTPUT_DIR.relative_to(ROOT)}")
    print(f"Reports          : {len(REPORTS)}")
    print(f"Transaction type : READ ONLY, REPEATABLE READ")
    print()

    settings = _connection_settings()

    print("Connecting to Neon (credentials from local .env — not displayed)...")
    try:
        with psycopg.connect(**settings, autocommit=True) as conn:
            print("Connected.\n")

            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )
                cur.execute("SET LOCAL statement_timeout = '120s'")

                # --- pre-run row counts -----------------------------------------
                print("Pre-run table counts:")
                pre_counts = _row_counts(cur)
                for t, n in pre_counts.items():
                    print(f"  {t:<25} {n:>6,}")
                print()

                # --- execute each report ----------------------------------------
                results = {}
                errors = []
                for stem, label, sql_text in REPORTS:
                    sql_clean = _dedent(sql_text)
                    print(f"Running {label}...")
                    try:
                        cur.execute(sql_clean)
                        columns = _column_names(cur)
                        rows = cur.fetchall()
                        results[stem] = (label, columns, rows)
                        out_path = OUTPUT_DIR / f"{stem}.csv"
                        _write_csv(out_path, columns, rows)
                        print(
                            f"  -> {len(rows)} row(s) -> "
                            f"{out_path.relative_to(ROOT)}"
                        )
                    except Exception as exc:
                        # Sanitise: show SQLSTATE if available, not raw detail.
                        code = getattr(exc, "sqlstate", None)
                        suffix = f" [SQLSTATE {code}]" if code else ""
                        msg = f"  X FAILED{suffix}: {type(exc).__name__}"
                        print(msg)
                        errors.append((stem, label, msg))
                    print()

                # --- post-run row counts ----------------------------------------
                print("Post-run table counts:")
                post_counts = _row_counts(cur)
                for t, n in post_counts.items():
                    print(f"  {t:<25} {n:>6,}")
                print()

                if pre_counts != post_counts:
                    print(
                        "WARNING: Table counts changed during reporting. "
                        "Read-only transaction should prevent this."
                    )
                else:
                    print("Row counts unchanged — database not modified. OK")

    except SystemExit:
        raise
    except psycopg.OperationalError:
        raise SystemExit(
            "STOP: Connection failed. Check network access, TLS and .env configuration."
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise SystemExit(
            f"STOP: Unexpected error during reporting: {e}"
        )

    # --- summary ----------------------------------------------------------------
    print()
    print("=" * 60)
    print("Execution summary")
    print("=" * 60)
    succeeded = [s for s in REPORTS if s[0] not in {e[0] for e in errors}]
    print(f"  Succeeded : {len(succeeded)}/{len(REPORTS)}")
    print(f"  Failed    : {len(errors)}/{len(REPORTS)}")
    if errors:
        for stem, label, msg in errors:
            print(f"  X {label}: {msg}")
        raise SystemExit(1)

    print()
    print("CSV outputs written to:")
    for stem, label, _ in REPORTS:
        out_path = OUTPUT_DIR / f"{stem}.csv"
        print(f"  {out_path.relative_to(ROOT)}")
    print()
    print("Phase 7 SQL reporting complete. No database records were modified.")


if __name__ == "__main__":
    main()
