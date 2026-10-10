"""Offline submission check: recompute the eight saved SQL result sets in Pandas.

Run from the project root: python scripts/verify_saved_results.py
No database connection, network request, or output-file mutation occurs.
"""
from pathlib import Path
import sys
import math
from decimal import Decimal, ROUND_HALF_UP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from src.clean_transform import reload_tables, NUTRIENTS


def rounded(value, places):
    return float(Decimal(str(float(value))).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def verify():
    tables = reload_tables(ROOT / 'data/cleaned')
    products = tables['products'].merge(tables['nutrition'], on='barcode', validate='one_to_one')
    products = products.merge(tables['brands'], on='brand_id', how='left', validate='many_to_one')
    products = products.merge(tables['categories'].rename(columns={'category_id': 'primary_category_id', 'category_name': 'primary_category'}), on='primary_category_id', validate='many_to_one')
    members = tables['product_categories'].merge(tables['categories'], on='category_id', validate='many_to_one').merge(products, on='barcode', validate='many_to_one')
    expected = {i: [] for i in range(1, 9)}
    for category, group in members.groupby('category_name'):
        base = {'category_name': category}
        expected[1].append(dict(base, total_memberships=len(group), pct_of_all_memberships=rounded(100*len(group)/len(members), 2), unique_products=group.barcode.nunique()))
        for number, nutrient, label in [(2, 'sugars_g', 'sugars'), (3, 'protein_g', 'protein')]:
            values = group.loc[group.measurement_basis.eq('100g') & group[nutrient+'_eligible'], nutrient+'_per_100']
            expected[number].append(dict(base, **{
                'median_'+label+'_g_per_100g': float(values.median()), 'eligible_memberships': len(values),
                'mean_'+label+'_g_per_100g': rounded(values.mean(), 4),
                'min_'+label+'_g_per_100g': float(values.min()), 'max_'+label+'_g_per_100g': float(values.max())}))
        expected[5].append(dict(base, total_memberships=len(group), **{'grade_'+g: int(group.nutriscore_grade.eq(g).sum()) for g in 'abcde'},
            status_unknown=int(group.nutriscore_status.eq('unknown').sum()), status_not_applicable=int(group.nutriscore_status.eq('not_applicable').sum()),
            status_missing_invalid=int(group.nutriscore_status.isin(['missing','invalid']).sum()), pct_with_grade=rounded(100*group.nutriscore_grade.notna().mean(),1)))
        expected[6].append(dict(base, total_memberships=len(group), **{key:int(group.nova_group.eq(value).sum()) for key,value in [('nova_1_unprocessed',1),('nova_2_processed_ingredients',2),('nova_3_processed',3),('nova_4_ultra_processed',4)]},
            nova_unknown=int(group.nova_group.isna().sum()), pct_nova4_of_classified=rounded(100*group.nova_group.eq(4).sum()/group.nova_group.notna().sum(),1)))
        expected[8].append(dict(base, total_memberships=len(group), flagged_memberships=int(group.has_numeric_flags.sum()), pct_flagged=rounded(100*group.has_numeric_flags.mean(),1),
            non_100g_basis_memberships=int(group.measurement_basis.ne('100g').sum()), avg_missing_nutrients_per_product=rounded(group[[n+'_per_100' for n in NUTRIENTS]].isna().sum(axis=1).mean(),2),
            avg_completeness_pct=rounded(group.nutrition_completeness_pct.mean(),2)))
    eligible = products.loc[products.measurement_basis.isin(['100g','100ml']) & products.protein_g_eligible & products.energy_kcal_eligible & products.energy_kcal_per_100.gt(0) & products.protein_g_per_100kcal.notna()]
    for _, row in eligible.sort_values(['protein_g_per_100kcal','barcode'], ascending=[False, True]).head(10).iterrows():
        item = {key:row[key] for key in ['barcode','product_name','primary_category','measurement_basis','protein_g_per_100','energy_kcal_per_100']}
        item.update(primary_brand=row.brand_name, protein_g_per_100kcal=rounded(row.protein_g_per_100kcal,4))
        expected[4].append(item)
    brands = []
    for brand, group in products.groupby('brand_name'):
        if len(group)>5:
            brands.append(dict(brand_name=brand, product_count=len(group), products_with_grade=int(group.nutriscore_grade.notna().sum()), avg_nutrition_completeness_pct=rounded(group.nutrition_completeness_pct.mean(),2)))
    expected[7] = sorted(brands,key=lambda r:(-r['product_count'],r['brand_name']))[:20]
    total = 0
    for number, rows in expected.items():
        path, = (ROOT/'reports/sql_results').glob(f'q{number}_*.csv')
        saved = pd.read_csv(path, dtype='string', keep_default_na=False)
        key = 'barcode' if number==4 else 'brand_name' if number==7 else 'category_name'
        actual = {row[key]:row for row in saved.to_dict('records')}
        assert len(saved)==len(rows)==len(actual), f'Q{number}: row count'
        assert set(actual)=={row[key] for row in rows}, f'Q{number}: keys'
        assert set(saved.columns)==set(rows[0]), f'Q{number}: columns'
        for row in rows:
            for column, value in row.items():
                found = actual[row[key]][column]
                if isinstance(value, (int,float)):
                    assert math.isclose(float(found), value, rel_tol=1e-11, abs_tol=1e-9), f'Q{number}: {column}'
                else:
                    assert found == ('' if pd.isna(value) else str(value)), f'Q{number}: {column}'
                total += 1
        if number==4:
            assert list(saved.barcode)==[r['barcode'] for r in rows], 'Q4: ranking order'
        print(f'Q{number}: PASS ({len(rows)} rows, all {len(saved.columns)} columns)')
    print(f'PASS: {total} saved result cells agree with offline Pandas calculations; no SQL executed.')


if __name__ == '__main__':
    verify()
