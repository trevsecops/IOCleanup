#!/usr/bin/env python3
import json
import datetime as dt
from tenable.io import TenableIO

# ---- INSERT YOUR KEYS HERE ----
TIO_ACCESS_KEY = "61d28279e786d7beadb01891a5665037ea6eebeb5ec3b29250d2295078b86bbc"
TIO_SECRET_KEY = "0add369bf2193e7b7464b9da461e960737c0c3c0ddb982c33d28a36e4424210d"
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
        if v is None:
            return default
        return int(float(v))
    except Exception:
        return default


def best_timestamp(agent):
    """
    Decide which timestamp to use for "most recent":
      1) last_connect (preferred) if present (>0)
      2) linked_on if last_connect is missing/invalid
    Returns: (chosen_ts:int, chosen_field:str)
    """
    lc = as_int(agent.get("last_connect"), 0)
    if lc > 0:
        return lc, "last_connect"

    lo = as_int(agent.get("linked_on"), 0)
    if lo > 0:
        return lo, "linked_on"

    return 0, "none"


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

    # 3) Find duplicates, keep "most recent" by:
    #    - last_connect if available
    #    - else linked_on
    #    Tie-breaker: highest id
    dup_names = 0
    dup_to_remove = 0

    with open(DUP_SUMMARY_LOG, "w", encoding="utf-8") as slog, open(DUP_REMOVE_OUT, "w", encoding="utf-8") as rlog:
        slog.write("=== Tenable Agent Duplicate Report (by exact agent.name) ===\n")
        slog.write('Selection rule: keep newest last_connect; if missing, keep newest linked_on; tie-breaker: highest id\n\n')

        for name in sorted(groups.keys()):
            items = groups[name]
            if len(items) <= 1:
                continue

            dup_names += 1

            def sort_key(x):
                ts, field = best_timestamp(x)
                # prefer last_connect over linked_on when timestamps tie
                field_rank = 2 if field == "last_connect" else (1 if field == "linked_on" else 0)
                return (ts, field_rank, as_int(x.get("id"), 0))

            items_sorted = sorted(items, key=sort_key, reverse=True)
            keep = items_sorted[0]
            removes = items_sorted[1:]
            dup_to_remove += len(removes)

            keep_ts, keep_field = best_timestamp(keep)
            safe_name = name if name else "<EMPTY_NAME>"

            keep_lc = keep.get("last_connect")
            keep_lo = keep.get("linked_on")

            slog.write(
                f'Workstation "{safe_name}" has {len(items)} entries ({len(items)-1} duplicates).\n'
                f'  KEEP id={keep.get("id")} uuid={keep.get("uuid")} '
                f'last_connect={keep_lc} ({to_iso_utc(keep_lc) or "N/A"}), '
                f'linked_on={keep_lo} ({to_iso_utc(keep_lo) or "N/A"})\n'
                f'  KEEP_REASON: selected_by={keep_field} selected_ts={keep_ts} ({to_iso_utc(keep_ts) or "N/A"})\n'
            )

            remove_ids = [r.get("id") for r in removes]
            slog.write(f"  REMOVE ids={remove_ids}\n")

            for r in removes:
                r_ts, r_field = best_timestamp(r)
                entry = {
                    "name": safe_name,
                    "keep": {
                        "id": keep.get("id"),
                        "uuid": keep.get("uuid"),
                        "last_connect": keep_lc,
                        "last_connect_utc": to_iso_utc(keep_lc),
                        "linked_on": keep_lo,
                        "linked_on_utc": to_iso_utc(keep_lo),
                        "selected_by": keep_field,
                        "selected_ts": keep_ts,
                        "selected_ts_utc": to_iso_utc(keep_ts),
                    },
                    "remove": {
                        "id": r.get("id"),
                        "uuid": r.get("uuid"),
                        "last_connect": r.get("last_connect"),
                        "last_connect_utc": to_iso_utc(r.get("last_connect")),
                        "linked_on": r.get("linked_on"),
                        "linked_on_utc": to_iso_utc(r.get("linked_on")),
                        "selected_by": r_field,
                        "selected_ts": r_ts,
                        "selected_ts_utc": to_iso_utc(r_ts),
                    },
                    "remove_record": r,
                    "removal_reason": "duplicate_name_keep_most_recent_last_connect_else_linked_on",
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
