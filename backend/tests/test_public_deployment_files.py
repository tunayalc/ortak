import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("path,expected", [
    ("frontend/api/orak-gateway.js", True),
    ("frontend/vercel.json", True),
    ("frontend/.vercelignore", True),
    ("frontend/tests/orak-gateway.unit.mjs", True),
    ("frontend/api/.env", False),
    ("frontend/api/credentials.json", False),
    ("frontend/api/service-account.json", False),
    ("frontend/.vercel/project.json", False),
    ("frontend/.vercel/.env.production.local", False),
    ("frontend/.env.production", False),
    ("output/deployment/domain-20261112/result.json", False),
])
def test_vercel_public_allowlist(path, expected):
    filename = Path(__file__).resolve().parents[2] / "scripts/scan_public.py"
    spec = importlib.util.spec_from_file_location("scan_public", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.allowed(path) is expected
