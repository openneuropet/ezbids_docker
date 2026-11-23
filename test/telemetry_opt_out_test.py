"""Exercise the real finalization script with disposable data and stubbed tools."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TelemetryOptOutTest(unittest.TestCase):
    def run_finalization(self, enabled):
        with tempfile.TemporaryDirectory(
            prefix="ezbids-telemetry-test-", dir="/tmp"
        ) as temporary:
            work = Path(temporary)
            dataset = work / "session"
            dataset.mkdir()
            (dataset / "finalized.json").write_text(
                '{"datasetDescription":{"Name":"fixture"}}'
            )
            commands = work / "bin"
            commands.mkdir()
            capture = work / "curl-calls"

            def stub(directory, name, body):
                file = directory / name
                file.write_text("#!/bin/bash\nset -e\n" + body + "\n")
                file.chmod(0o755)

            stub(commands, "jq", 'printf "fixture\\n"')
            stub(commands, "tree", 'printf "fixture structure\\n"')
            stub(
                commands,
                "bids-validator",
                """
if [[ "$*" == *"--json"* ]]; then
    printf '{"issues":{"issues":[]}}\\n'
else
    printf 'No validation errors\\n'
fi""",
            )
            stub(commands, "curl", 'printf "%s\\n" "$*" >> "$TEST_CURL_CAPTURE"')
            stub(work, "convert_meg.py", 'mkdir -p "$2"')
            stub(work, "convert.js", "exit 0")
            stub(
                work,
                "telemetry.py",
                '''
printf '{}' > "$1/ezBIDS_core_telemetry.json"
printf '{}' > "$1/ezBIDS_finalized_telemetry.json"''',
            )
            environment = dict(
                os.environ,
                PATH=str(commands) + ":" + os.environ["PATH"],
                TEST_CURL_CAPTURE=str(capture),
            )
            environment.pop("EZBIDS_TELEMETRY_ENABLED", None)
            if enabled is not None:
                environment["EZBIDS_TELEMETRY_ENABLED"] = enabled
            result = subprocess.run(
                ["bash", str(ROOT / "handler/bids.sh"), str(dataset)],
                cwd=work,
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            calls = capture.read_text().splitlines() if capture.exists() else []
            self.assertTrue((dataset / "validator.json").is_file())
            self.assertTrue((dataset / "ezBIDS_template.json").is_file())
            return calls, result.stdout

    def test_disabled_prevents_all_outbound_posts_without_skipping_conversion(self):
        calls, output = self.run_finalization("false")
        self.assertEqual(calls, [])
        self.assertIn("Outbound telemetry disabled", output)

    def test_default_and_explicit_enable_preserve_existing_behavior(self):
        for enabled in (None, "true"):
            with self.subTest(enabled=enabled):
                calls, _ = self.run_finalization(enabled)
                self.assertEqual(len(calls), 3)
                self.assertTrue(
                    all("http://openneuropet.org/telemetry/" in call for call in calls)
                )


if __name__ == "__main__":
    unittest.main()
