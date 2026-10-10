-- FoodLens Phase 5: empty PostgreSQL schema; no data loading.
-- Run once in a fresh database. Fail on existing tables; do not conceal schema drift.
-- CSV columns map directly, in order. Empty CSV fields represent SQL NULL.
-- Exact text identifiers preserve leading zeros and case-sensitive brand labels.
-- Numeric measurements use double precision to match Phase 3 nullable Float64.
-- No gram/energy ceilings or cross-nutrient inequalities: review flags preserve values.
BEGIN;

CREATE TABLE public.brands (
    brand_id text NOT NULL,
    brand_name text NOT NULL,
    CONSTRAINT brands_pk PRIMARY KEY (brand_id),
    CONSTRAINT brands_name_uq UNIQUE (brand_name),
    CONSTRAINT brands_check_01 CHECK (brand_id <> ''),
    CONSTRAINT brands_check_02 CHECK (brand_name <> '')
);

CREATE TABLE public.categories (
    category_id text NOT NULL,
    category_name text NOT NULL,
    CONSTRAINT categories_pk PRIMARY KEY (category_id),
    CONSTRAINT categories_name_uq UNIQUE (category_name),
    CONSTRAINT categories_check_01 CHECK (category_id <> ''),
    CONSTRAINT categories_check_02 CHECK (category_name <> '')
);

CREATE TABLE public.products (
    barcode text NOT NULL,
    product_name text,
    original_product_name text,
    brand_id text,
    original_brands text,
    nutriscore_grade text,
    nutriscore_status text NOT NULL,
    nova_group smallint,
    primary_category_id text NOT NULL,
    extraction_id text NOT NULL,
    source_page integer NOT NULL,
    source_record_index integer NOT NULL,
    extracted_at_utc timestamptz,
    record_origin text NOT NULL,
    source_relative_path text NOT NULL,
    source_response_sha256 text NOT NULL,
    CONSTRAINT products_pk PRIMARY KEY (barcode),
    CONSTRAINT products_brand_id_fk FOREIGN KEY (brand_id) REFERENCES public.brands (brand_id),
    CONSTRAINT products_primary_category_id_fk FOREIGN KEY (primary_category_id) REFERENCES public.categories (category_id),
    CONSTRAINT products_check_01 CHECK (barcode ~ '^[0-9]{8,14}$'),
    CONSTRAINT products_check_02 CHECK (nutriscore_grade IN ('a', 'b', 'c', 'd', 'e')),
    CONSTRAINT products_check_03 CHECK (nutriscore_status IN ('reported', 'unknown', 'not_applicable', 'missing', 'invalid')),
    CONSTRAINT products_check_04 CHECK ((nutriscore_status = 'reported') = (nutriscore_grade IS NOT NULL)),
    CONSTRAINT products_check_05 CHECK (nova_group BETWEEN 1 AND 4),
    CONSTRAINT products_check_06 CHECK (source_page >= 1),
    CONSTRAINT products_check_07 CHECK (source_record_index >= 0),
    CONSTRAINT products_check_08 CHECK (record_origin IN ('api', 'legacy_import'))
);

CREATE TABLE public.product_categories (
    barcode text NOT NULL,
    category_id text NOT NULL,
    CONSTRAINT product_categories_pk PRIMARY KEY (barcode, category_id),
    CONSTRAINT product_categories_barcode_fk FOREIGN KEY (barcode) REFERENCES public.products (barcode),
    CONSTRAINT product_categories_category_id_fk FOREIGN KEY (category_id) REFERENCES public.categories (category_id)
);

CREATE TABLE public.nutrition (
    barcode text NOT NULL,
    measurement_basis text NOT NULL,
    reported_measurement_basis text,
    reported_energy_kcal_per_100 text,
    energy_kcal_per_100 double precision,
    energy_kcal_flags text,
    energy_kcal_eligible boolean NOT NULL,
    reported_energy_kj_per_100 text,
    energy_kj_per_100 double precision,
    energy_kj_flags text,
    energy_kj_eligible boolean NOT NULL,
    reported_protein_g_per_100 text,
    protein_g_per_100 double precision,
    protein_g_flags text,
    protein_g_eligible boolean NOT NULL,
    reported_carbohydrates_g_per_100 text,
    carbohydrates_g_per_100 double precision,
    carbohydrates_g_flags text,
    carbohydrates_g_eligible boolean NOT NULL,
    reported_sugars_g_per_100 text,
    sugars_g_per_100 double precision,
    sugars_g_flags text,
    sugars_g_eligible boolean NOT NULL,
    reported_fat_g_per_100 text,
    fat_g_per_100 double precision,
    fat_g_flags text,
    fat_g_eligible boolean NOT NULL,
    reported_saturated_fat_g_per_100 text,
    saturated_fat_g_per_100 double precision,
    saturated_fat_g_flags text,
    saturated_fat_g_eligible boolean NOT NULL,
    reported_fiber_g_per_100 text,
    fiber_g_per_100 double precision,
    fiber_g_flags text,
    fiber_g_eligible boolean NOT NULL,
    reported_salt_g_per_100 text,
    salt_g_per_100 double precision,
    salt_g_flags text,
    salt_g_eligible boolean NOT NULL,
    protein_g_per_100kcal double precision,
    sugar_to_carbohydrate_ratio double precision,
    nutrition_completeness_pct double precision NOT NULL,
    has_numeric_flags boolean NOT NULL,
    CONSTRAINT nutrition_pk PRIMARY KEY (barcode),
    CONSTRAINT nutrition_barcode_fk FOREIGN KEY (barcode) REFERENCES public.products (barcode),
    CONSTRAINT nutrition_check_01 CHECK (measurement_basis IN ('100g', '100ml', 'unknown')),
    CONSTRAINT nutrition_check_02 CHECK (nutrition_completeness_pct BETWEEN 0 AND 100),
    CONSTRAINT nutrition_check_03 CHECK (energy_kcal_per_100 >= 0 AND energy_kcal_per_100 < 'Infinity'::double precision),
    CONSTRAINT nutrition_check_04 CHECK (energy_kj_per_100 >= 0 AND energy_kj_per_100 < 'Infinity'::double precision),
    CONSTRAINT nutrition_check_05 CHECK (protein_g_per_100 >= 0 AND protein_g_per_100 < 'Infinity'::double precision),
    CONSTRAINT nutrition_check_06 CHECK (carbohydrates_g_per_100 >= 0 AND carbohydrates_g_per_100 < 'Infinity'::double precision),
    CONSTRAINT nutrition_check_07 CHECK (sugars_g_per_100 >= 0 AND sugars_g_per_100 < 'Infinity'::double precision),
    CONSTRAINT nutrition_check_08 CHECK (fat_g_per_100 >= 0 AND fat_g_per_100 < 'Infinity'::double precision),
    CONSTRAINT nutrition_check_09 CHECK (saturated_fat_g_per_100 >= 0 AND saturated_fat_g_per_100 < 'Infinity'::double precision),
    CONSTRAINT nutrition_check_10 CHECK (fiber_g_per_100 >= 0 AND fiber_g_per_100 < 'Infinity'::double precision),
    CONSTRAINT nutrition_check_11 CHECK (salt_g_per_100 >= 0 AND salt_g_per_100 < 'Infinity'::double precision),
    CONSTRAINT nutrition_check_12 CHECK (protein_g_per_100kcal >= 0 AND protein_g_per_100kcal < 'Infinity'::double precision),
    CONSTRAINT nutrition_check_13 CHECK (sugar_to_carbohydrate_ratio >= 0 AND sugar_to_carbohydrate_ratio < 'Infinity'::double precision)
);

-- Reciprocal deferred FK enforces exactly one nutrition row per product at commit.
-- Phase 6 must insert products and nutrition in the same transaction.
ALTER TABLE public.products ADD CONSTRAINT products_nutrition_fk
    FOREIGN KEY (barcode) REFERENCES public.nutrition (barcode) DEFERRABLE INITIALLY DEFERRED;

-- Primary category is extraction provenance; it must also be a membership.
ALTER TABLE public.products ADD CONSTRAINT products_primary_membership_fk
    FOREIGN KEY (barcode, primary_category_id) REFERENCES public.product_categories (barcode, category_id) DEFERRABLE INITIALLY DEFERRED;

-- Supporting FK indexes (PK indexes already cover bridge/nutrition barcodes).
CREATE INDEX products_brand_id_idx ON public.products (brand_id);
CREATE INDEX products_primary_category_id_idx ON public.products (primary_category_id);
CREATE INDEX product_categories_category_id_idx ON public.product_categories (category_id);

COMMIT;
