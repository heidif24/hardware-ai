import json
import sys
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.dossier import build_dossier

class DossierTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "idea": "A solar-powered GPS tracker for livestock",
            "constraints": "Low power, outdoor enclosure, cellular connectivity",
            "quantity": 100,
            "design": {
                "product_name": "Livestock Tracker",
                "summary": "A low-power outdoor tracking device.",
                "modules": [
                    {"name": "Power", "purpose": "Power management", "interfaces": ["battery bus"], "parts": ["charger", "DC-DC converter"]},
                    {"name": "Connectivity", "purpose": "Position and transmit", "interfaces": ["UART", "RF"], "parts": ["GNSS module", "cellular module"]}
                ],
                "assumptions": ["Duty cycle remains to be quantified."],
                "risks": ["RF performance requires validation."],
                "requirements": ["Define required position accuracy."],
                "electrical_design": ["Create a verified power tree."],
                "interface_control": ["Define connector pinout."],
                "firmware_plan": ["Implement watchdog and fault handling."],
                "mechanical_plan": ["Confirm enclosure ingress protection."],
                "verification_plan": ["Run outdoor field tests."],
                "validation_status": "concept_only"
            }
        }

    def test_dossier_contains_vendor_neutral_engineering_documents(self):
        archive_bytes, filename = build_dossier(self.payload)
        self.assertTrue(filename.endswith("_Engineering_Dossier.zip"))
        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            names = set(archive.namelist())
            expected = {
                "README.md", "package_manifest.json", "product_brief.json",
                "design_architecture.json", "engineering_design_report.md",
                "candidate_bom.csv", "functional_architecture.svg",
                "requirements_baseline.md", "electrical_design_plan.md",
                "interface_control_document.md", "firmware_architecture.md",
                "verification_test_plan.md", "mechanical_design_brief.md",
                "manufacturing_handoff.md", "engineering_release_checklist.csv",
                "NDA_template.md"
            }
            self.assertTrue(expected.issubset(names))
            manifest = json.loads(archive.read("package_manifest.json"))
            self.assertFalse(manifest["contains_fabrication_outputs"])
            self.assertFalse(manifest["vendor_pricing_or_procurement_data"])
            self.assertIn("Gerber X2", manifest["missing_fabrication_outputs"])
            self.assertIn("NDA", archive.read("README.md").decode("utf-8"))
            requirements = archive.read("requirements_baseline.md").decode("utf-8")
            self.assertIn("\n", requirements)
            self.assertNotIn("\\n", requirements)

    def test_invalid_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            build_dossier({"idea": "too short", "design": {}})

if __name__ == "__main__":
    unittest.main()
