import json
from pathlib import Path
import tempfile
import unittest

from modules.scenario_repository import ScenarioLibraryError, load_scenario_library
from modules.simulation_engine import load_cases


class ScenarioRepositoryTests(unittest.TestCase):
    def test_compiled_external_library_preserves_studio_features(self):
        external = (
            Path(__file__).resolve().parents[2]
            / "nursing scenario library"
            / "dist"
            / "library.json"
        )
        cases = load_scenario_library(external)
        first = cases[0]
        self.assertIn("prebrief", first)
        self.assertIn("clinical_workspace", first)
        self.assertIn("educator_rubric", first)
        self.assertIn("action_phrases", first["dialogue"])

    def test_invalid_external_content_is_rejected(self):
        payload = {"schema_version": "0.2.0", "cases": [{}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "library.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ScenarioLibraryError):
                load_scenario_library(path)

    def test_bundled_fallback_is_valid(self):
        self.assertEqual(len(load_cases()), 4)


if __name__ == "__main__":
    unittest.main()
