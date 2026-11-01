import tempfile
import unittest
from pathlib import Path

from app.engines import generate_firmware, generate_mechanical


class NativeEngineTests(unittest.TestCase):
    def test_firmware_refuses_unverified_target(self):
        with tempfile.TemporaryDirectory() as directory:
            result = generate_firmware(Path(directory), {"firmware_design": {}})
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(result["passed"])

    def test_firmware_requires_application_source(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = {"firmware_design": {"target": {"platformio_board": "esp32dev"}, "platform": "espressif32"}}
            result = generate_firmware(Path(directory), plan)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse((Path(directory) / "05_Firmware").exists())

    def test_mechanical_refuses_unproven_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = {"mechanical_design": {"parameters": {
                "length": {"value": 100, "value_basis": "provisional_target"}
            }}}
            result = generate_mechanical(Path(directory), plan)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("width", " ".join(result["missing_inputs"]))

    def test_mechanical_refuses_inconsistent_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            p = {k: {"value": v, "value_basis": "user_specified"} for k, v in {
                "length": 20, "width": 15, "height": 10, "wall": 12, "floor": 2, "corner": 1
            }.items()}
            result = generate_mechanical(Path(directory), {"mechanical_design": {"parameters": p}})
            self.assertEqual(result["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
