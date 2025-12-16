import json
import sys
import argparse
from tenable.io import TenableIO

# ----------------------------
# INSERT YOUR KEYS HERE
# ----------------------------
TIO_ACCESS_KEY = "PASTE_ACCESS_KEY_HERE"
TIO_SECRET_KEY = "PASTE_SECRET_KEY_HERE"
TIO_URL = "https://cloud.tenable.com"  


def main() -> int:
    p = argparse.ArgumentParser(description="List all Tenable.io Nessus Agents (full properties).")
    p.add_argument("--scanner-id", type=int, default=1, help="Scanner ID (default: 1)")
    p.add_argument("--out", help="Write output to a file (NDJSON). Default: stdout")
    args = p.parse_args()

    if "PASTE_ACCESS_KEY_HERE" in TIO_ACCESS_KEY or "PASTE_SECRET_KEY_HERE" in TIO_SECRET_KEY:
        print("ERROR: Please paste your Tenable.io API keys into TIO_ACCESS_KEY and TIO_SECRET_KEY.", file=sys.stderr)
        return 2

    tio = TenableIO(TIO_ACCESS_KEY, TIO_SECRET_KEY, url=TIO_URL)

    out_fh = open(args.out, "w", encoding="utf-8") if args.out else sys.stdout
    try:
        # agents.list() returns an iterator; pyTenable handles pagination.
        for agent in tio.agents.list(scanner_id=args.scanner_id):
            out_fh.write(json.dumps(agent, ensure_ascii=False, default=str) + "\n")
    finally:
        if args.out:
            out_fh.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
