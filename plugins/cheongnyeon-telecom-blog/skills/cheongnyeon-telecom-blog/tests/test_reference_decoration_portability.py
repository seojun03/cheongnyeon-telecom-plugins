from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "validate_reference_decoration.py"
SPEC = importlib.util.spec_from_file_location("validate_reference_decoration", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReferenceDecorationPortabilityTests(unittest.TestCase):
    def test_remote_reference_image_does_not_require_local_asset(self) -> None:
        source_url = "https://postfiles.pstatic.net/reference.jpg?type=w580"
        profile = {
            "mediaSlots": [
                {
                    "sourceUrl": source_url,
                    "localAsset": "assets/reference-media/not-installed.jpg",
                }
            ],
            "renderContract": {
                "requiredRoleCounts": {},
                "requiredOrderedRoles": [],
                "requireExactMediaSources": True,
                "requiredColors": [],
                "minimumCenterRatio": 0,
                "tableRowCounts": [],
                "requiredUnderlineRoleCounts": {},
                "requiredUnderlineCount": 0,
            },
        }
        raw = (
            '<article data-master-reference-id="remote-only">'
            f'<img src="{source_url}" data-reference-source-url="{source_url}">'
            "</article>"
        )
        result = MODULE.validate(raw, profile)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["metrics"]["imageSources"], [source_url])


if __name__ == "__main__":
    unittest.main()
