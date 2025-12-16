#!/usr/bin/env python3
import json
import time
import datetime as dt
from tenable.io import TenableIO

# =========================
# CONFIG (edit these)
# =========================
TIO_ACCESS_KEY = ""   # <-- paste here
TIO_SECRET_KEY = ""   # <-- paste here
TIO_URL = "https://cloud.tenable.com"

RAW_OUT = "tenable_agents_raw.ndjson"
DUP_SUMMARY_LOG = "tenable_agents_duplicates_summary.log"
DUP_REMOVE_OUT = "tenable_agents_duplicates_to_remove.ndjson"

# Flip to True to actually unlink duplicates:
DO_UNLINK_DUPLICATES = False

# If batch size == 1, unlink returns None (singular)
# If batch size > 1, unlink returns a dict task record (bulk)
UNLINK_BATCH_SIZE = 25
SLEEP_SECONDS_BETWEEN_BATCHES = 0.5

UNLINK_LOG = "tenable_agents_unlink_results.log"
# =========================


def as_int(v, default=0):
    try:
        if v is None:
            return default
        return int(float(v))
    except Exception:
        return default


def to_iso_utc(epoch):
    epoch = as_int(epoch, 0)
    if epoch <= 0:
        return ""
    return dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def pick_keep_and_removes(items):
    """
    Selection rule (per your requirement):
      - If ANY last_connect exists in the group (>0): keep the entry with the newest last_connect.
      - If NO last_connect exists for the entire group: keep the entry with the newest linked_on.
      - Tie-breakers: newest linked_on, then highest id.
    """
    has_any_last_connect = any(as_int(a.get("last_connect"), 0) > 0 for a in items)

    if has_any_last_connect:
        mode = "last_connect"
        items_sorted = sorted(
            items,
            key=lambda a: (
                as_int(a.get("last_connect"), 0),
                as_int(a.get("linked_on"), 0),
                as_int(a.get("id"), 0),
            ),
            reverse=True,
        )
    else:
        mode = "linked_on"
        items_sorted = sorted(
            items,
            key=lambda a: (
                as_int(a.get("linked_on"), 0),
                as_int(a.get("id"), 0),
            ),
            reverse=True,
        )

    keep = items_sorted[0]
    removes = items_sorted[1:]
    return mode, keep, removes


def now_utc():
    return dt.datetime.now(tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def main():
    if not TIO_ACCESS_KEY or not TIO_SECRET_KEY:
        raise SystemExit("ERROR: Paste TIO_ACCESS_KEY and TIO_SECRET_KEY at the top of the script.")

    tio = TenableIO(TIO_ACCESS_KEY, TIO_SECRET_KEY, url=TIO_URL)

    # 1) Dump raw agents + load into memory for analysis
    agents = []
    with open(RAW_OUT, "w", encoding="utf-8") as f:
        for agent in tio.agents.list():
            f.write(json.dumps(agent, ensure_ascii=False, default=str) + "\n")
            agents.append(agent)

    # 2) Group by exact name
    groups = {}
    for a in agents:
        name = a.get("name")
        if name is None:
            name = ""
        if not isinstance(name, str):
            name = str(name)
        groups.setdefault(name, []).append(a)

    dup_names = 0
    dup_remove_count = 0
    to_unlink_ids = []

    # 3) Find duplicates + write logs
    with open(DUP_SUMMARY_LOG, "w", encoding="utf-8") as slog, open(DUP_REMOVE_OUT, "w", encoding="utf-8") as rlog:
        slog.write("=== Tenable Agent Duplicate Report (by exact agent.name) ===\n")
        slog.write("Selection rule:\n")
        slog.write("  - If any last_connect exists in the group: keep newest last_connect\n")
        slog.write("  - Else (no last_connect in group): keep newest linked_on\n")
        slog.write("  - Tie-breakers: newest linked_on, then highest id\n\n")

        for name in sorted(groups.keys()):
            items = groups[name]
            if len(items) <= 1:
                continue

            dup_names += 1
            safe_name = name if name else "<EMPTY_NAME>"

            mode, keep, removes = pick_keep_and_removes(items)
            dup_remove_count += len(removes)

            keep_id = keep.get("id")
            keep_uuid = keep.get("uuid")

            keep_lc = keep.get("last_connect")
            keep_lo = keep.get("linked_on")

            selected_ts = as_int(keep_lc, 0) if mode == "last_connect" else as_int(keep_lo, 0)

            slog.write(
                f'Workstation "{safe_name}" has {len(items)} entries ({len(items)-1} duplicates).\n'
                f"  MODE={mode}\n"
                f"  KEEP id={keep_id} uuid={keep_uuid} "
                f"last_connect={keep_lc} ({to_iso_utc(keep_lc) or 'N/A'}), "
                f"linked_on={keep_lo} ({to_iso_utc(keep_lo) or 'N/A'})\n"
                f"  SELECTED_TS={selected_ts} ({to_iso_utc(selected_ts) or 'N/A'})\n"
            )

            remove_ids = [r.get("id") for r in removes]
            slog.write(f"  REMOVE ids={remove_ids}\n")

            for r in removes:
                rid = r.get("id")
                if rid is not None:
                    to_unlink_ids.append(as_int(rid, 0))

                r_lc = r.get("last_connect")
                r_lo = r.get("linked_on")
                r_selected_ts = as_int(r_lc, 0) if mode == "last_connect" else as_int(r_lo, 0)

                slog.write(
                    f"    - REMOVE id={rid} uuid={r.get('uuid')} "
                    f"last_connect={r_lc} ({to_iso_utc(r_lc) or 'N/A'}), "
                    f"linked_on={r_lo} ({to_iso_utc(r_lo) or 'N/A'}), "
                    f"selected_ts={r_selected_ts} ({to_iso_utc(r_selected_ts) or 'N/A'})\n"
                )

                entry = {
                    "name": safe_name,
                    "mode": mode,
                    "keep": {
                        "id": keep_id,
                        "uuid": keep_uuid,
                        "last_connect": keep_lc,
                        "last_connect_utc": to_iso_utc(keep_lc),
                        "linked_on": keep_lo,
                        "linked_on_utc": to_iso_utc(keep_lo),
                        "selected_ts": selected_ts,
                        "selected_ts_utc": to_iso_utc(selected_ts),
                    },
                    "remove": {
                        "id": rid,
                        "uuid": r.get("uuid"),
                        "last_connect": r_lc,
                        "last_connect_utc": to_iso_utc(r_lc),
                        "linked_on": r_lo,
                        "linked_on_utc": to_iso_utc(r_lo),
                        "selected_ts": r_selected_ts,
                        "selected_ts_utc": to_iso_utc(r_selected_ts),
                    },
                    "remove_record": r,
                    "removal_reason": "duplicate_name_keep_newest_last_connect_else_linked_on",
                }
                rlog.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

            slog.write("\n")

        slog.write(f"Workstation names with duplicates: {dup_names}\n")
        slog.write(f"Duplicate records to remove: {dup_remove_count}\n")
        slog.write(f"DO_UNLINK_DUPLICATES={DO_UNLINK_DUPLICATES}\n")
        slog.write(f"UNLINK_BATCH_SIZE={UNLINK_BATCH_SIZE}\n")

    print(f"Wrote raw dump: {RAW_OUT}")
    print(f"Wrote duplicate summary: {DUP_SUMMARY_LOG}")
    print(f"Wrote duplicates-to-remove list: {DUP_REMOVE_OUT}")

    # 4) Unlink duplicates (optional)
    if not DO_UNLINK_DUPLICATES:
        print("Unlink step skipped (DO_UNLINK_DUPLICATES is False).")
        return

    # De-dupe unlink ids just in case
    to_unlink_ids = sorted({i for i in to_unlink_ids if i and i > 0})

    with open(UNLINK_LOG, "w", encoding="utf-8") as ulog:
        ulog.write("=== Tenable Agent Unlink Results ===\n")
        ulog.write(f"Start: {now_utc()}\n")
        ulog.write(f"Total duplicate agent IDs to unlink: {len(to_unlink_ids)}\n")
        ulog.write("NOTE: unlink(1) returns None; unlink(1,2,3) returns a dict task record.\n\n")

        successes = 0
        failures = 0

        batch_size = max(1, int(UNLINK_BATCH_SIZE))

        for batch in chunks(to_unlink_ids, batch_size):
            try:
                # If len(batch)==1 => None expected. If >1 => dict task expected.
                resp = tio.agents.unlink(*batch)

                if resp is None:
                    # Singular unlink success (or at least no exception)
                    successes += len(batch)
                    ulog.write(f"[{now_utc()}] OK unlink ids={batch} resp=None\n")
                elif isinstance(resp, dict):
                    # Bulk unlink task record returned
                    # We don't assume field names; log full dict.
                    successes += len(batch)
                    ulog.write(f"[{now_utc()}] OK unlink ids={batch} resp=dict task={json.dumps(resp, default=str)}\n")
                else:
                    # Unexpected type, but call did not throw
                    successes += len(batch)
                    ulog.write(f"[{now_utc()}] OK unlink ids={batch} resp_type={type(resp).__name__} resp={repr(resp)}\n")

            except Exception as e:
                failures += len(batch)
                ulog.write(f"[{now_utc()}] FAIL unlink ids={batch} error={repr(e)}\n")

            if SLEEP_SECONDS_BETWEEN_BATCHES:
                time.sleep(SLEEP_SECONDS_BETWEEN_BATCHES)

        ulog.write("\n")
        ulog.write(f"End: {now_utc()}\n")
        ulog.write(f"Success count (ids): {successes}\n")
        ulog.write(f"Failure count (ids): {failures}\n")

    print(f"Wrote unlink results: {UNLINK_LOG}")


if __name__ == "__main__":
    main()
