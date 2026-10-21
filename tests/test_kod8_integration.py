from pathlib import Path
import json
import tempfile
import unittest

from services.kod8_adapter import Kod8Adapter
from services.activity_log import ActivityLogger

ROOT = Path(__file__).resolve().parents[1]

class Kod8IntegrationTests(unittest.TestCase):
    def test_cl1_through_cl8_round_trip(self):
        adapter = Kod8Adapter(ROOT / "KOD8_ENC" / "kod8_engine.py")
        sample = "DILARA activity event: module opened; Turkish: ışık; number: 123"
        for cid in (f"CL{i}" for i in range(1, 9)):
            with self.subTest(strategy=cid):
                used, encrypted = adapter.encrypt_text(sample, cid)
                self.assertEqual(used, cid)
                self.assertEqual(adapter.decrypt_text(encrypted, cid), sample)

    def test_activity_log_writes_encrypted_envelope(self):
        adapter = Kod8Adapter(ROOT / "KOD8_ENC" / "kod8_engine.py")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "activity.kod8log"
            ActivityLogger(path, adapter).record("module_opened", "KOD8", {"source": "test"})
            envelope = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(envelope["format"], "DILARA-KOD8-ACTIVITY-1")
            self.assertEqual(envelope["cipher_id"], "CL1")
            self.assertNotIn("module_opened", envelope["ciphertext"])

if __name__ == "__main__":
    unittest.main()
