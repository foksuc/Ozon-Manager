from pathlib import Path
import re


def test_no_real_credentials_in_repository():
    root = Path(__file__).parents[1]
    forbidden = [
        "sk-live-",
        "Authorization: Bearer",
        "Client-Id: 123456",
    ]
    forbidden_patterns = [
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
        re.compile(r"(?i)client[-_ ]?id\s*[:=]\s*\d{8,}"),
    ]

    excluded_dirs = {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
    }

    this_test = Path(__file__).resolve()

    for p in root.rglob("*"):
        if (
            p.resolve() == this_test
            or not p.is_file()
            or any(part in excluded_dirs for part in p.parts)
        ):
            continue

        try:
            data = p.read_bytes()
        except Exception:
            continue

        # Skip binary files. Credential scanning is intended for text files.
        if b"\x00" in data:
            continue

        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            continue

        assert not any(x in text for x in forbidden), p