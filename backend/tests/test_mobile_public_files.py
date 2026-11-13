import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("path,expected", [
    ("mobile/App.tsx", True),
    ("mobile/assets/icon.png", True),
    ("mobile/src/api.ts", True),
    ("mobile/eas.json", True),
    ("mobile/.env.example", True),
    ("mobile/.env", False),
    ("mobile/credentials.json", False),
    ("mobile/assets/upload.jks", False),
    ("mobile/assets/signing.p12", False),
    ("mobile/assets/profile.mobileprovision", False),
    ("mobile/assets/AuthKey.p8", False),
    ("mobile/assets/signing.PFX", False),
    ("mobile/assets/debug.apk", False),
    ("mobile/assets/release.aab", False),
    ("mobile/assets/release.ipa", False),
    ("mobile/ios/ORTAK/Info.plist", False),
    ("mobile/android/gradle.properties", False),
    ("mobile/.expo/settings.json", False),
])
def test_mobile_public_allowlist(path, expected):
    filename = Path(__file__).resolve().parents[2] / "scripts/scan_public.py"
    spec = importlib.util.spec_from_file_location("scan_public", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.allowed(path) is expected
