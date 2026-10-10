"""Verify the exact delivered file set and SHA-256 hashes using only Python stdlib."""
import hashlib
import json
from pathlib import Path


def verify(root):
    manifest = root / 'SUBMISSION_MANIFEST.json'
    rows = json.loads(manifest.read_text(encoding='utf-8'))['files']
    expected = {item['path']: item for item in rows}
    if len(expected) != len(rows):
        raise ValueError('Duplicate manifest paths')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != manifest}
    if actual != set(expected):
        raise ValueError('File set differs: missing=' + str(sorted(set(expected)-actual)) + '; extra=' + str(sorted(actual-set(expected))))
    for name, item in expected.items():
        path = root / name
        if Path(name).is_absolute() or '..' in Path(name).parts or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Unsafe manifest path')
        data = path.read_bytes()
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('File content differs: ' + name)
    print(f'PASS: {len(rows)} manifest entries; exact file set, byte sizes and SHA-256 hashes.')


if __name__ == '__main__':
    verify(Path(__file__).resolve().parents[1])
