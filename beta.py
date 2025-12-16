import json
from tenable.io import TenableIO

# INSERT YOUR KEYS HERE
TIO_ACCESS_KEY = "61d28279e786d7beadb01891a5665037ea6eebeb5ec3b29250d2295078b86bbc"
TIO_SECRET_KEY = "0add369bf2193e7b7464b9da461e960737c0c3c0ddb982c33d28a36e4424210d"
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
