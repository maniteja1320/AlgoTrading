"""Generate VAPID keys and append to backend/.env (does not print private key)."""
from __future__ import annotations

import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization

try:
    from py_vapid import Vapid01
    from py_vapid.utils import b64urlencode
except ImportError:
    print("Install dependencies first: pip install pywebpush py-vapid")
    sys.exit(1)

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
MARKER = "VAPID_PUBLIC_KEY="


def _strip_existing_vapid(text: str) -> str:
    lines = []
    skip = False
    for line in text.splitlines():
        if line.startswith("# Web push") or line.startswith("VAPID_"):
            skip = True
            continue
        if skip and line.strip() == "":
            skip = False
            continue
        if not skip:
            lines.append(line)
    return "\n".join(lines).rstrip()


def main() -> None:
    text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    text = _strip_existing_vapid(text)

    vapid = Vapid01()
    vapid.generate_keys()
    raw_pub = vapid.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    public_key = b64urlencode(raw_pub)
    private_pem = vapid.private_pem().decode("utf-8").replace("\n", "\\n")

    block = (
        "\n# Web push notifications (VAPID)\n"
        f"VAPID_PUBLIC_KEY={public_key}\n"
        f'VAPID_PRIVATE_KEY="{private_pem}"\n'
        "VAPID_CLAIMS_EMAIL=mailto:algotradingcrypto@gmail.com\n"
    )
    ENV_PATH.write_text(text + block + "\n", encoding="utf-8")
    print(f"VAPID keys written to {ENV_PATH}")


if __name__ == "__main__":
    main()
