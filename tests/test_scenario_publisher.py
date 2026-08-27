import base64
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from modules.scenario_publisher import ScenarioPublishError, publish_scenario


ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, payload):
        self.data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.data


class ScenarioPublisherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        library = json.loads(
            (ROOT / "sample_patients" / "patient_cases.json").read_text(encoding="utf-8")
        )
        cls.case = library["cases"][0]

    def test_publish_updates_validated_scenario_source(self):
        responses = [
            FakeResponse({"sha": "current-sha"}),
            FakeResponse({"commit": {"html_url": "https://github.test/commit/1"}}),
        ]
        with patch("modules.scenario_publisher.urlopen", side_effect=responses) as mocked:
            url = publish_scenario(
                "example/scenarios", "main", "secret", self.case
            )

        self.assertEqual(url, "https://github.test/commit/1")
        self.assertEqual(mocked.call_count, 2)
        put_request = mocked.call_args_list[1].args[0]
        self.assertTrue(put_request.full_url.endswith("/scenarios/PAT-001.yaml"))
        body = json.loads(put_request.data.decode("utf-8"))
        published = json.loads(base64.b64decode(body["content"]).decode("utf-8"))
        self.assertEqual(body["sha"], "current-sha")
        self.assertEqual(published, self.case)

    def test_invalid_repository_is_rejected_before_network_access(self):
        with patch("modules.scenario_publisher.urlopen") as mocked:
            with self.assertRaises(ScenarioPublishError):
                publish_scenario("not-a-repository", "main", "secret", self.case)
        mocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
