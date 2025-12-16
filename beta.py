import json
from tenable.io import TenableIO

# INSERT YOUR KEYS HERE
TIO_ACCESS_KEY = "PASTE_ACCESS_KEY_HERE"
TIO_SECRET_KEY = "PASTE_SECRET_KEY_HERE"
TIO_URL = "https://cloud.tenable.com"  # change only if needed

OUTFILE = "tenable_agents.ndjson"  # newline-delimited JSON (1 agent per line)

def main():
    tio = TenableIO(TIO_ACCESS_KEY, TIO_SECRET_KEY, url=TIO_URL)

    with open(OUTFILE, "w", encoding="utf-8") as f:
        for agent in tio.agents.list():
            f.write(json.dumps(agent, ensure_ascii=False, default=str) + "\n")

    print(f"Wrote agents to: {OUTFILE}")

if __name__ == "__main__":
    main()
SystemExit(main())
