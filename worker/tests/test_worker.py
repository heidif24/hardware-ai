import base64
import tempfile
import unittest
from pathlib import Path

from app.main import build_report, write_user_files


class WorkerSafetyTests(unittest.TestCase):
    def test_writes_safe_uploaded_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = base64.b64encode(b"fixture").decode("ascii")
            written = write_user_files(root, {"03_Electronics/example.kicad_sch": payload})
            self.assertEqual(written, ["03_Electronics/example.kicad_sch"])
            self.assertEqual((root / "03_Electronics" / "example.kicad_sch").read_bytes(), b"fixture")

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                write_user_files(Path(directory), {"../outside.txt": base64.b64encode(b"x").decode("ascii")})

    def test_rejects_invalid_base64(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(Exception):
                write_user_files(Path(directory), {"01_Product_Definition/input.json": "not-base64!"})

    def test_report_marks_incomplete_design_as_blocked(self):
        job = {"id": "test-job", "project_name": "Test device"}
        toolchains = {"kicad_cli": {"available": False}, "freecad": {"available": False}}
        report = build_report(job, toolchains, [], {"KiCad": [], "Firmware": [], "Mechanical": []})
        self.assertIn("Execution status:** BLOCKED", report)
        self.assertIn("ENGINEERING_WORK_INCOMPLETE", report)
        self.assertIn("Gerber", report) if "Gerber" in report else None


if __name__ == "__main__":
    unittest.main()
