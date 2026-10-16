"""Verify the reviewed public snapshot or install it without replacing local data.

This script uses only the Python standard library. It never reads .env, calls an
API, or connects to a database. Run it from either the repository root or any
other working directory.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'repro_data'
DATA = ROOT / 'data'
EXTRACTION_IDS = (
    '255549a7a8a480c0',
    '34e0ad749f6a0fa6',
    'a7cac53fa4872087',
    'ed4f16ea3c02f6ab',
)


def expected_paths():
    names = {
        'raw/food_products_raw.json',
        'raw/food_products_extracted.csv',
        'processed/food_products_analysis_combined_725f8a023f0f8ee6.csv',
        'processed/food_products_analysis_combined_725f8a023f0f8ee6.json',
    }
    names.update(f'cleaned/{name}.csv' for name in (
        'brands', 'categories', 'nutrition', 'product_categories', 'products'))
    for extraction_id in EXTRACTION_IDS:
        names.add(f'processed/food_products_analysis_{extraction_id}.csv')
        names.update(f'raw/extractions/{extraction_id}/{name}.json' for name in (
            'checkpoint', 'manifest', 'barcode_issues'))
        names.update(
            f'raw/extractions/{extraction_id}/pages/page_{page:06}.json'
            for page in range(1, 6))
    if len(names) != 45:
        raise ValueError('Expected 45 public data paths')
    return names


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_snapshot(snapshot=SNAPSHOT):
    """Return the reviewed paths only after checking exact files and hashes."""
    manifest = snapshot / 'MANIFEST.json'
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError('Missing or symbolic-link public manifest')
    document = json.loads(manifest.read_text(encoding='utf-8'))
    if document.get('format_version') != 1 or not isinstance(document.get('files'), list):
        raise ValueError('Unsupported public manifest')
    rows = document['files']
    expected = expected_paths()
    if (len(rows) != len(expected) or any(not isinstance(row, dict) for row in rows)
            or {row.get('path') for row in rows} != expected):
        raise ValueError('Public manifest does not list the 45 expected data paths')
    actual = {
        path.relative_to(snapshot).as_posix()
        for path in snapshot.rglob('*') if path.is_file()
    } - {'MANIFEST.json', 'README.md'}
    if actual != expected:
        raise ValueError('Public snapshot has missing or extra files')
    verified = []
    response_count = 0
    for row in rows:
        name = row['path']
        relative = PurePosixPath(name)
        if (relative.is_absolute() or '..' in relative.parts or '\\' in name
                or ':' in name or relative.as_posix() != name):
            raise ValueError('Unsafe public path')
        source = snapshot.joinpath(*relative.parts)
        if source.is_symlink() or not source.is_file():
            raise ValueError('Missing or symbolic-link public data file: ' + name)
        raw = source.read_bytes()
        if (not isinstance(row.get('bytes'), int) or len(raw) != row['bytes']
                or sha256(raw) != row.get('sha256')):
            raise ValueError('Public data hash or size mismatch: ' + name)
        if '/pages/page_' in name:
            envelope = json.loads(raw)
            canonical = (json.dumps(envelope['response'], ensure_ascii=False,
                                    sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
            if sha256(canonical) != envelope['response_sha256']:
                raise ValueError('Saved response hash mismatch: ' + name)
            response_count += 1
        verified.append((relative, source))
    if response_count != 20:
        raise ValueError('Expected 20 saved response pages')
    return verified


def install_snapshot(snapshot=SNAPSHOT, data=DATA):
    """Preflight every destination before copying any bytes; never overwrite."""
    verified = verify_snapshot(snapshot)
    if data.is_symlink() or (data.exists() and not data.is_dir()):
        raise ValueError('Data destination is a symbolic link or not a directory')
    missing = []
    identical = 0
    for relative, source in verified:
        target = data.joinpath(*relative.parts)
        for parent in (data, *[data.joinpath(*relative.parts[:index])
                               for index in range(1, len(relative.parts))]):
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ValueError('Unsafe data destination parent: ' + str(parent))
        if target.is_symlink():
            raise ValueError('Symbolic-link data destination: ' + str(target))
        if target.exists():
            if not target.is_file() or sha256(target.read_bytes()) != sha256(source.read_bytes()):
                raise ValueError('Existing data differs; nothing installed: ' + str(target))
            identical += 1
        else:
            missing.append((source, target))
    for source, target in missing:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as output:
            output.write(source.read_bytes())
    return len(missing), identical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--verify', action='store_true', help='Read-only manifest and response checks')
    action.add_argument('--install', action='store_true', help='Copy into data/ after a conflict preflight')
    args = parser.parse_args()
    try:
        if args.verify:
            verified = verify_snapshot()
            print(f'PASS: {len(verified)} public data files and 20 response hashes verified.')
        else:
            installed, identical = install_snapshot()
            print(f'PASS: installed {installed} public data files; {identical} already identical.')
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f'STOP: {exc}\n')


if __name__ == '__main__':
    main()
