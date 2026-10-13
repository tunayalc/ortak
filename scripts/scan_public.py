"""Fail closed on accidental private files or recognizable secrets before push."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ("backend/app/", "backend/scripts/", "backend/tests/", "frontend/src/", "frontend/public/", "frontend/tests/", "deploy/", "scripts/", ".github/")
EXACT = {"README.md", "LICENSE", "NOTICE.md", ".gitignore", ".dockerignore", ".env.example", "backend/Dockerfile", "backend/requirements.txt", "backend/requirements.lock", "frontend/Dockerfile", "frontend/package.json", "frontend/package-lock.json", "frontend/index.html", "frontend/vite.config.js", "frontend/playwright.config.js", "docs/rapor_uyum_taslagi.md", "docs/yayin_kilavuzu.md", "docs/ai_ve_tema_tamamlama_plani.md", "docs/ollama_dogrulama.md"}
SECRET = re.compile(r"AIza[0-9A-Za-z_-]{35}|(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})|sk-(?:proj-)?[A-Za-z0-9_-]{32,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|\x2fUsers\x2f[^/\s]+\x2f|[A-Za-z0-9._%+-]+@(?:gmail|hotmail|outlook)\.com")
PRIVATE_PARTS = {"node_modules", "__pycache__", ".venv", ".venv-release", "output", "backups", "private", "data", "guard", "dist", ".pytest_cache"}


def allowed(path):
    item = Path(path)
    return (path in EXACT or path.startswith(PUBLIC)) and not (set(item.parts) & PRIVATE_PARTS) and (not item.name.startswith(".env") or item.name == ".env.example") and item.suffix not in {".db", ".sqlite", ".sqlite3", ".pem", ".key", ".pdf", ".docx", ".xlsx", ".gz", ".zip", ".pyc"}


def scan(files):
    failures = []
    for name in files:
        path = ROOT / name
        if not allowed(name) or path.is_symlink():
            failures.append((name, "private or unapproved file"))
            continue
        data = path.read_bytes()
        if len(data) > 2 * 1024 ** 2:
            failures.append((name, "unexpected large file"))
            continue
        for number, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
            if SECRET.search(line):
                failures.append((name, f"potential secret at line {number}"))
    return failures


if __name__ == "__main__":
    staged = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    files = [name for name in staged.decode().split("\0") if name]
    if not files:
        files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode().split("\0")
        files = [name for name in files if name]
    failures = scan(files)
    for name, message in failures:
        print(f"{name}: {message}")
    print(f"Scanned {len(files)} public files; {len(failures)} issues. Secret values are never printed.")
    sys.exit(bool(failures) or not files)
