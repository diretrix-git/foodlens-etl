"""Offline checks for the public snapshot installer; no network or database."""

from pathlib import Path, PurePosixPath
import tempfile
import unittest
from unittest.mock import patch

from scripts import prepare_repro_data


class PublicSnapshotTests(unittest.TestCase):
    def test_reviewed_snapshot_and_response_hashes(self):
        verified = prepare_repro_data.verify_snapshot()
        self.assertEqual(len(verified), 45)

    def test_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.csv'
            source.write_bytes(b'barcode\n00123\n')
            rows = [(PurePosixPath('cleaned/products.csv'), source)]
            with patch.object(prepare_repro_data, 'verify_snapshot', return_value=rows):
                self.assertEqual(prepare_repro_data.install_snapshot(data=root / 'data'), (1, 0))
                self.assertEqual(prepare_repro_data.install_snapshot(data=root / 'data'), (0, 1))
            self.assertEqual((root / 'data/cleaned/products.csv').read_bytes(), source.read_bytes())

    def test_conflict_preflight_prevents_other_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.csv'
            source.write_bytes(b'public')
            conflict = root / 'data/cleaned/products.csv'
            conflict.parent.mkdir(parents=True)
            conflict.write_bytes(b'private')
            rows = [(PurePosixPath('cleaned/brands.csv'), source),
                    (PurePosixPath('cleaned/products.csv'), source)]
            with patch.object(prepare_repro_data, 'verify_snapshot', return_value=rows):
                with self.assertRaisesRegex(ValueError, 'Existing data differs'):
                    prepare_repro_data.install_snapshot(data=root / 'data')
            self.assertEqual(conflict.read_bytes(), b'private')
            self.assertFalse((root / 'data/cleaned/brands.csv').exists())


if __name__ == '__main__':
    unittest.main()
