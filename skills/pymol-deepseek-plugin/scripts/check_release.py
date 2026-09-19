"""Lightweight release-tree checks; uses only the Python standard library."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "pymol_deepseek_plugin.py",
    "README.md",
    "CHANGELOG.md",
    "requirements.txt",
    "LICENSE_PENDING.md",
    "THIRD_PARTY_NOTICES.md",
    "tests/test_plugin_mock.py",
}
FORBIDDEN_PARTS = {"__pycache__", ".pytest_cache", ".git"}
SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"DEEPSEEK_API_KEY\s*=\s*[\"'][^\"'\n]{8,}[\"']"),
]
TEXT_SUFFIXES = {".py", ".md", ".txt", ".yml", ".yaml", ".json", ".toml"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


missing = sorted(path for path in REQUIRED if not (ROOT / path).is_file())
if missing:
    fail(f"missing required files: {', '.join(missing)}")

for path in ROOT.rglob("*"):
    if any(part in FORBIDDEN_PARTS for part in path.parts):
        fail(f"forbidden generated path found: {path.relative_to(ROOT)}")
    if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                token = match.group(0)
                if "your_API_key" in token or "your-" in token.lower():
                    continue
                fail(f"possible secret in {path.relative_to(ROOT)}")

subprocess.run(
    [sys.executable, "-m", "py_compile", str(ROOT / "pymol_deepseek_plugin.py")],
    check=True,
)
print("Release checks passed.")
