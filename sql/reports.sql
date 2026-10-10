-- FoodLens Phase 7: SQL reporting and insights
-- Eight read-only SELECT queries demonstrating JOINs, aggregations, HAVING,
-- CASE WHEN and PostgreSQL PERCENTILE_CONT.
-- All queries execute inside a single read-only, repeatable-read transaction.
-- No INSERT, UPDATE, DELETE, TRUNCATE, DROP or ALTER statements appear here.
-- Column names and eligibility rules follow sql/schema.sql and Phase 3 cleaning.
-- Per-100-g comparisons use measurement_basis = '100g' AND <nutrient>_eligible = TRUE.
-- Category memberships are counted from product_categories (bridge table); a product
-- that belongs to two categories is counted once in each.  Overall unique-product
-- totals must deduplicate barcodes from the bridge.

-- ============================================================
-- Q1: How many products belong to each food category?
-- Techniques: INNER JOIN, GROUP BY, COUNT, ORDER BY
-- ============================================================
-- Uses the bridge table so that the 13 dual-category products are counted in
-- each of their two categories separately (500 memberships each by design).
-- Also shows each category's share of the full 2,000-membership total.
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
ORDER BY total_memberships DESC;


-- ============================================================
-- Q2: Which categories have the highest median sugar content per 100 g?
-- Techniques: INNER JOIN, WHERE, GROUP BY, PERCENTILE_CONT, ORDER BY
-- ============================================================
-- Restricted to measurement_basis = '100g' AND sugars_g_eligible = TRUE
-- to match Phase 3's strict per-100-g comparison policy (phase3_validation.md).
-- Phase 4 found medians: Biscuits 26.00, Cereal bars 24.00,
-- Breakfast cereals 17.00, Yogurts 8.10 (same subset; SQL must reproduce them).
SELECT
    c.category_name,
    -- Median using PostgreSQL ordered-set aggregate
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
ORDER BY median_sugars_g_per_100g DESC;


-- ============================================================
-- Q3: Which categories have the highest median protein content per 100 g?
-- Techniques: INNER JOIN, WHERE, GROUP BY, PERCENTILE_CONT, ORDER BY
-- ============================================================
-- Same basis/eligibility filter as Q2 but for protein_g.
-- Phase 4 found medians: Breakfast cereals 9.40, Cereal bars 7.10,
-- Biscuits 6.80, Yogurts 3.50.
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
ORDER BY median_protein_g_per_100g DESC;


-- ============================================================
-- Q4: Which products have the highest protein per 100 kcal, with brand info?
-- Techniques: LEFT JOIN, WHERE, NULLIF (division-by-zero guard), ORDER BY, LIMIT
-- ============================================================
-- Phase 3 stores protein_g_per_100kcal as a derived column when both operands
-- are eligible and energy_kcal > 0 (NULLIF(energy_kcal_per_100, 0) denominator).
-- The column is already NULL when the ratio cannot be calculated safely.
-- Basis is restricted to explicit 100g or 100ml (the per-100 denominator cancels).
-- Phase 4 top-10 ranking is reproduced here using the stored metric.
-- LEFT JOIN brands: a product without a brand still appears in the ranking.
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
  -- Confirm measurement basis is explicit 100g or 100ml (not unknown)
  AND n.measurement_basis IN ('100g', '100ml')
  -- Both operands must be eligible (Phase 3 policy)
  AND n.protein_g_eligible      = TRUE
  AND n.energy_kcal_eligible    = TRUE
  -- Energy must be positive (stored metric already guards this, but explicit for clarity)
  AND n.energy_kcal_per_100 > 0
ORDER BY n.protein_g_per_100kcal DESC,
         p.barcode ASC       -- break exact ties reproducibly
LIMIT 10;


-- ============================================================
-- Q5: How are Nutri-Score grades distributed across the categories?
-- Techniques: LEFT JOIN, CASE WHEN, GROUP BY, COUNT, ORDER BY
-- ============================================================
-- Uses all 2,000 memberships (500 per category) so unknown/not_applicable
-- grades remain visible in the denominator, matching Phase 4 policy.
-- products.nutriscore_grade is NULL when nutriscore_status != 'reported'.
SELECT
    c.category_name,
    COUNT(*)                                           AS total_memberships,
    -- Grade counts
    COUNT(CASE WHEN p.nutriscore_grade = 'a' THEN 1 END)   AS grade_a,
    COUNT(CASE WHEN p.nutriscore_grade = 'b' THEN 1 END)   AS grade_b,
    COUNT(CASE WHEN p.nutriscore_grade = 'c' THEN 1 END)   AS grade_c,
    COUNT(CASE WHEN p.nutriscore_grade = 'd' THEN 1 END)   AS grade_d,
    COUNT(CASE WHEN p.nutriscore_grade = 'e' THEN 1 END)   AS grade_e,
    -- Non-grade status counts
    COUNT(CASE WHEN p.nutriscore_status = 'unknown'        THEN 1 END) AS status_unknown,
    COUNT(CASE WHEN p.nutriscore_status = 'not_applicable' THEN 1 END) AS status_not_applicable,
    COUNT(CASE WHEN p.nutriscore_status IN ('missing', 'invalid') THEN 1 END) AS status_missing_invalid,
    -- Percentage of reported grades (a-e) within each category
    ROUND(
        COUNT(CASE WHEN p.nutriscore_grade IS NOT NULL THEN 1 END) * 100.0
        / NULLIF(COUNT(*), 0),
        1
    )                                                  AS pct_with_grade
FROM public.categories          c
INNER JOIN public.product_categories pc ON pc.category_id = c.category_id
INNER JOIN public.products      p  ON p.barcode = pc.barcode
GROUP BY c.category_id, c.category_name
ORDER BY c.category_name;


-- ============================================================
-- Q6: How do NOVA processing classifications differ by category?
-- Techniques: LEFT JOIN, CASE WHEN, GROUP BY, COUNT, ORDER BY
-- ============================================================
-- products.nova_group is nullable (130 products have no NOVA classification).
-- All 2,000 memberships are counted so NULL NOVA values are visible.
SELECT
    c.category_name,
    COUNT(*)                                               AS total_memberships,
    COUNT(CASE WHEN p.nova_group = 1 THEN 1 END)           AS nova_1_unprocessed,
    COUNT(CASE WHEN p.nova_group = 2 THEN 1 END)           AS nova_2_processed_ingredients,
    COUNT(CASE WHEN p.nova_group = 3 THEN 1 END)           AS nova_3_processed,
    COUNT(CASE WHEN p.nova_group = 4 THEN 1 END)           AS nova_4_ultra_processed,
    COUNT(CASE WHEN p.nova_group IS NULL THEN 1 END)        AS nova_unknown,
    -- Percentage ultra-processed (NOVA 4) among members with a NOVA classification
    ROUND(
        COUNT(CASE WHEN p.nova_group = 4 THEN 1 END) * 100.0
        / NULLIF(COUNT(CASE WHEN p.nova_group IS NOT NULL THEN 1 END), 0),
        1
    )                                                       AS pct_nova4_of_classified
FROM public.categories          c
INNER JOIN public.product_categories pc ON pc.category_id = c.category_id
INNER JOIN public.products      p  ON p.barcode = pc.barcode
GROUP BY c.category_id, c.category_name
ORDER BY c.category_name;


-- ============================================================
-- Q7: Which brands have the most products?
-- Techniques: INNER JOIN, GROUP BY, HAVING, ORDER BY, COUNT
-- ============================================================
-- Each product counts once (unique barcode FK to brands), so no double-counting
-- from dual-category membership.
-- HAVING filters to brands with more than 5 products to keep the result meaningful.
SELECT
    b.brand_name,
    COUNT(p.barcode)          AS product_count,
    -- Show how many of their products carry a Nutri-Score grade
    COUNT(CASE WHEN p.nutriscore_grade IS NOT NULL THEN 1 END) AS products_with_grade,
    -- Average nutrition completeness for this brand's products (all basis types)
    ROUND(AVG(n.nutrition_completeness_pct)::numeric, 2)       AS avg_nutrition_completeness_pct
FROM public.brands      b
INNER JOIN public.products  p ON p.brand_id = b.brand_id
INNER JOIN public.nutrition n ON n.barcode   = p.barcode
GROUP BY b.brand_id, b.brand_name
HAVING COUNT(p.barcode) > 5
ORDER BY product_count DESC,
         b.brand_name  ASC
LIMIT 20;


-- ============================================================
-- Q8: Which categories have the most missing or flagged nutritional measurements?
-- Techniques: INNER JOIN, CASE WHEN, GROUP BY, COUNT, AVG, ORDER BY
-- ============================================================
-- Counts three distinct data-quality dimensions per category membership:
--   a) has_numeric_flags: at least one numeric flag present (cross-field issues)
--   b) Missing measurements: the nine core nutrient numeric columns are NULL
--   c) Ineligible due to non-100g basis: excluded from strict per-100-g analysis
-- Covers all 2,000 memberships; unique products may be counted in two categories.
SELECT
    c.category_name,
    COUNT(pc.barcode)                                               AS total_memberships,
    -- Products with at least one numeric quality flag
    COUNT(CASE WHEN n.has_numeric_flags = TRUE THEN 1 END)         AS flagged_memberships,
    ROUND(
        COUNT(CASE WHEN n.has_numeric_flags = TRUE THEN 1 END) * 100.0
        / NULLIF(COUNT(*), 0), 1
    )                                                               AS pct_flagged,
    -- Memberships not on confirmed 100g basis (unknown or 100ml)
    COUNT(CASE WHEN n.measurement_basis != '100g' THEN 1 END)      AS non_100g_basis_memberships,
    -- Mean missing nutrient count across the nine core fields
    -- Each NULL field is a missing measurement.
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
    -- Mean nutrition completeness score (stored derived field, 0-100)
    ROUND(AVG(n.nutrition_completeness_pct)::numeric, 2)            AS avg_completeness_pct
FROM public.categories          c
INNER JOIN public.product_categories pc ON pc.category_id = c.category_id
INNER JOIN public.nutrition     n  ON n.barcode = pc.barcode
GROUP BY c.category_id, c.category_name
ORDER BY avg_missing_nutrients_per_product DESC,
         pct_flagged DESC;
