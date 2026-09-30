import py_compile
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import Provisioner, load_manifest, load_standard, validate
from src.models import Domain, Manifest, Table, Column

STANDARD = ROOT / "standard" / "medallion_standard.yaml"
MANIFEST = ROOT / "config" / "manifest.example.yaml"


class TestProvisioning(unittest.TestCase):
    def setUp(self):
        self.standard = load_standard(STANDARD)
        self.manifest = load_manifest(MANIFEST)
        self.prov = Provisioner(ROOT / "templates")

    def test_example_manifest_is_compliant(self):
        self.assertEqual(validate(self.manifest, self.standard), [])

    def test_generates_scaffold_plus_one_per_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            written = self.prov.generate(self.manifest, self.standard, tmp)
            layer_count = sum(len(t.layers) for _, t in self.manifest.all_tables())
            self.assertEqual(len(written), layer_count + 1)

    def test_all_generated_notebooks_valid_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            for p in self.prov.generate(self.manifest, self.standard, tmp):
                with self.subTest(notebook=p.name):
                    py_compile.compile(str(p), doraise=True)

    def test_audit_columns_injected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.prov.generate(self.manifest, self.standard, tmp)
            bronze = (Path(tmp) / "tables" / "bronze_order.py").read_text()
            self.assertIn("_ingested_at", bronze)
            silver = (Path(tmp) / "tables" / "silver_order.py").read_text()
            self.assertIn("_updated_at", silver)

    def test_layer_prefix_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.prov.generate(self.manifest, self.standard, tmp)
            self.assertTrue((Path(tmp) / "tables" / "gold_order.py").exists())


class TestLinter(unittest.TestCase):
    def setUp(self):
        self.standard = load_standard(STANDARD)

    def _manifest(self, table):
        return Manifest(lakehouse="TestLH",
                        domains=[Domain(name="d", tables=[table])])

    def _good_table(self):
        return Table(
            name="customer", layers=["bronze", "silver"],
            business_keys=["customer_id"],
            columns=[Column("customer_id", "bigint", False),
                     Column("country", "string")],
            partition_by=["country"],
        )

    def test_good_table_passes(self):
        self.assertEqual(validate(self._manifest(self._good_table()),
                                  self.standard), [])

    def test_bad_name_flagged(self):
        t = self._good_table(); t.name = "Customer"
        self.assertTrue(any("naming pattern" in e
                            for e in validate(self._manifest(t), self.standard)))

    def test_reserved_audit_clash_flagged(self):
        t = self._good_table()
        t.columns.append(Column("_ingested_at", "timestamp"))
        self.assertTrue(any("reserved audit" in e
                            for e in validate(self._manifest(t), self.standard)))

    def test_bad_layer_flagged(self):
        t = self._good_table(); t.layers = ["bronze", "platinum"]
        self.assertTrue(any("not a managed zone" in e
                            for e in validate(self._manifest(t), self.standard)))

    def test_too_many_partitions_flagged(self):
        t = self._good_table()
        t.columns += [Column("a", "string"), Column("b", "string")]
        t.partition_by = ["country", "a", "b"]
        self.assertTrue(any("exceeds max" in e
                            for e in validate(self._manifest(t), self.standard)))

    def test_missing_business_key_flagged(self):
        t = self._good_table(); t.business_keys = ["nope"]
        self.assertTrue(any("business key 'nope'" in e
                            for e in validate(self._manifest(t), self.standard)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
