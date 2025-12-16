#!/usr/bin/env python3
import json
import datetime as dt
from tenable.io import TenableIO

# ---- INSERT YOUR KEYS HERE ----
TIO_ACCESS_KEY = "PASTE_ACCESS_KEY_HERE"
TIO_SECRET_KEY = "PASTE_SECRET_KEY_HERE"
TIO_URL = "https://cloud.tenable.com"
# -------------------------------

RAW_OUT = "tenable_agents_raw.ndjson"
DUP_SUMMARY_LOG = "tenable_agents_duplicates_summary.log"
DUP_REMOVE_OUT = "tenable_agents_duplicates_to_remove.ndjson"


def to_iso_utc(epoch):
    if epoch is None:
        return ""
    try:
        val = float(epoch)
        if val <= 0:
            return ""
        return dt.datetime.fromtimestamp(val, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def as_int(v, default=0):
    try:
        return int(float(v)) if v is not None else default
    except Exception:
        return default


def main():
    tio = TenableIO(TIO_ACCESS_KEY, TIO_SECRET_KEY, url=TIO_URL)

    # 1) Dump raw agents + load into memory for analysis
    agents = []
    with open(RAW_OUT, "w", encoding="utf-8") as f:
        for agent in tio.agents.list():
            f.write(json.dumps(agent, ensure_ascii=False, default=str) + "\n")
            agents.append(agent)

    # 2) Group by name
    groups = {}
    for a in agents:
        name = a.get("name")
        if name is None:
            name = ""
        if not isinstance(name, str):
            name = str(name)
        groups.setdefault(name, []).append(a)

    # 3) Find duplicates, keep latest last_connect (tie-breaker: highest id)
    dup_names = 0
    dup_to_remove = 0

    with open(DUP_SUMMARY_LOG, "w", encoding="utf-8") as slog, open(DUP_REMOVE_OUT, "w", encoding="utf-8") as rlog:
        slog.write("=== Tenable Agent Duplicate Report (by exact agent.name) ===\n")

        for name in sorted(groups.keys()):
            items = groups[name]
            if len(items) <= 1:
                continue

            dup_names += 1

            # Sort: last_connect desc, id desc
            items_sorted = sorted(
                items,
                key=lambda x: (as_int(x.get("last_connect"), 0), as_int(x.get("id"), 0)),
                reverse=True,
            )

            keep = items_sorted[0]
            removes = items_sorted[1:]
            dup_to_remove += len(removes)

            keep_lc = keep.get("last_connect")
            keep_iso = to_iso_utc(keep_lc)
            safe_name = name if name else "<EMPTY_NAME>"

            slog.write(
                f'Workstation "{safe_name}" has {len(items)} entries ({len(items)-1} duplicates). '
                f'KEEP id={keep.get("id")} uuid={keep.get("uuid")} '
                f'last_connect={keep_lc} ({keep_iso or "N/A"})\n'
            )

            remove_ids = [r.get("id") for r in removes]
            slog.write(f"  REMOVE ids={remove_ids}\n")

            for r in removes:
                entry = {
                    "name": safe_name,
                    "keep": {
                        "id": keep.get("id"),
                        "uuid": keep.get("uuid"),
                        "last_connect": keep_lc,
                        "last_connect_utc": keep_iso,
                    },
                    "remove": {
                        "id": r.get("id"),
                        "uuid": r.get("uuid"),
                        "last_connect": r.get("last_connect"),
                        "last_connect_utc": to_iso_utc(r.get("last_connect")),
                    },
                    "remove_record": r,
                }
                rlog.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

        slog.write("\n")
        slog.write(f"Workstation names with duplicates: {dup_names}\n")
        slog.write(f"Duplicate records to remove: {dup_to_remove}\n")

    print(f"Wrote raw dump: {RAW_OUT}")
    print(f"Wrote duplicate summary: {DUP_SUMMARY_LOG}")
    print(f"Wrote duplicates-to-remove list: {DUP_REMOVE_OUT}")


if __name__ == "__main__":
    main()
