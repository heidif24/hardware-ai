import tempfile
import unittest
from pathlib import Path

from app.engines import generate_firmware, generate_mechanical, generate_proprietary_connector
from app.pcb_engine import generate_pcb


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

    def test_pcb_refuses_missing_layout_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            result = generate_pcb(Path(directory), {"pcb_design": {}})
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(result["passed"])

    def test_pcb_refuses_unproven_board_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = {"pcb_design": {"native_layout": {
                "width_mm": {"value": 40, "value_basis": "provisional_target"},
                "height_mm": {"value": 30, "value_basis": "user_specified"},
                "thickness_mm": {"value": 1.6, "value_basis": "source_verified"},
                "copper_layers": 2, "outline_basis": "user_specified",
                "components": [], "nets": [], "tracks": [], "footprint_libraries": {}
            }}}
            result = generate_pcb(Path(directory), plan)
            self.assertEqual(result["status"], "BLOCKED_OR_FAILED")
            self.assertIn("provenance", result["detail"])

    def test_pcb_requires_explicit_component_net_and_track_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = {"pcb_design": {"native_layout": {
                "width_mm": {"value": 40, "value_basis": "user_specified"},
                "height_mm": {"value": 30, "value_basis": "user_specified"},
                "thickness_mm": {"value": 1.6, "value_basis": "source_verified"},
                "copper_layers": 2, "outline_basis": "user_specified",
                "components": [], "nets": [{"name": "GND"}], "tracks": [],
                "footprint_libraries": {}
            }}}
            result = generate_pcb(Path(directory), plan)
            self.assertEqual(result["status"], "BLOCKED_OR_FAILED")
            self.assertIn("components", result["detail"])

    def test_mechanical_refuses_unproven_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = {"mechanical_design": {"parameters": {
                "length": {"value": 100, "value_basis": "provisional_target"}
            }}}
            result = generate_mechanical(Path(directory), plan)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("width", " ".join(result["missing_inputs"]))

    def test_connector_refuses_unverified_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            result = generate_proprietary_connector(Path(directory), {"interface_design": {"connector_geometry": {}}})
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("pin_count", " ".join(result["missing_inputs"]))

    def test_mechanical_refuses_inconsistent_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            p = {k: {"value": v, "value_basis": "user_specified"} for k, v in {
                "length": 20, "width": 15, "height": 10, "wall": 12, "floor": 2, "corner": 1
            }.items()}
            result = generate_mechanical(Path(directory), {"mechanical_design": {"parameters": p}})
            self.assertEqual(result["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
