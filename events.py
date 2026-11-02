"""
Turns a before/after pair of scraped records into short, plain-English change
events for the site's change log.

Each event records WHEN we noticed the change (the run that saw it) and, where
there is one, the date the change takes effect, so the site can show how far
ahead of (or behind) the effective date it became known. That gap is what the
quality team acts on, not the effective date itself.

data/events.json is the history these events accumulate in (newest first).
The raw text diffs in data/changelog.json are left alone as an audit trail.
"""
import json
import os
from datetime import datetime

EVENTS_PATH = os.path.join("data", "events.json")
_PENDING_LABEL = "revised version"


def _rows(record):
    log = (record or {}).get("version_log") or []
    if len(log) < 2:
        return {}
    header = log[0]
    return {r[0]: dict(zip(header, r)) for r in log[1:] if r}


def _is_set(value):
    return bool(value) and value.strip().lower() != "not set"


def parse_date(text):
    try:
        return datetime.strptime((text or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def fmt_date(text):
    d = parse_date(text)
    return f"{d.day} {d:%b %Y}" if d else text


def _label(version):
    if version.lower().startswith(_PENDING_LABEL):
        return "Revised version"
    return f"Version {version}"


def _short_detail(row):
    detail = (row.get("Change detail") or "").strip().rstrip(".")
    return f" ({detail})" if detail and len(detail) <= 70 else ""


def derive_events(previous, current):
    """List of {"text", "effective"} dicts. Empty if nothing worth logging.
    No previous snapshot (first check) means no events."""
    if previous is None:
        return []

    events = []
    if previous.get("title") != current.get("title"):
        events.append({
            "text": f'Title changed from "{previous.get("title")}" to "{current.get("title")}"',
            "effective": None,
        })

    old, new = _rows(previous), _rows(current)
    pending_gone = [v for v in old if v.lower().startswith(_PENDING_LABEL) and v not in new]
    added_numbered = [v for v in new if v not in old and not v.lower().startswith(_PENDING_LABEL)]

    for version, row in new.items():
        start, end = row.get("Earliest start date"), row.get("Latest start date")
        if version not in old:
            if version.lower().startswith(_PENDING_LABEL):
                when = f"starts {fmt_date(start)}" if _is_set(start) else "start date not yet set"
                events.append({"text": f"Revised version announced: {when}{_short_detail(row)}",
                               "effective": start if _is_set(start) else None})
            else:
                verb = "published" if pending_gone else "added"
                when = f"starts {fmt_date(start)}" if _is_set(start) else "start date not yet set"
                events.append({"text": f"Version {version} {verb}: {when}{_short_detail(row)}",
                               "effective": start if _is_set(start) else None})
            continue

        before = old[version]
        label = _label(version)
        for key, field_name, phrase in (
            ("Earliest start date", "start", "start date"),
            ("Latest start date", "end", "last start date"),
        ):
            was, now = before.get(key), row.get(key)
            if was == now:
                continue
            if not _is_set(was) and _is_set(now):
                text = (f"{label}: {phrase} confirmed as {fmt_date(now)}"
                        if field_name == "start"
                        else f"{label}: last start date set to {fmt_date(now)}")
            elif _is_set(was) and _is_set(now):
                text = f"{label}: {phrase} moved from {fmt_date(was)} to {fmt_date(now)}"
            else:
                text = f"{label}: {phrase} removed (was {fmt_date(was)})"
            events.append({"text": text, "effective": now if _is_set(now) else None})

    if pending_gone and not added_numbered:
        events.append({"text": "Pending revised version no longer listed", "effective": None})

    return events


def load_events():
    if not os.path.exists(EVENTS_PATH):
        return []
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_events(events):
    os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)
    with open(EVENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)


def append_events(reference, name, events, run):
    """run: ISO timestamp (minute precision) of the check that saw them."""
    if not events:
        return
    log = load_events()
    for ev in reversed(events):
        log.insert(0, {"run": run, "reference": reference, "name": name,
                       "text": ev["text"], "effective": ev["effective"]})
    save_events(log)
