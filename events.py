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
import re
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


_IN_DEVELOPMENT = re.compile(r"(?<![A-Za-z])in development(?![A-Za-z])", re.IGNORECASE)
_BEING_REVISED = re.compile(
    r"in the process of being revised|apprenticeship (standard )?is (in|under) revision",
    re.IGNORECASE,
)

IN_DEVELOPMENT = "In development"
APPROVED = "Approved"
BEING_REVISED = "Being revised"
REVISION_PENDING = "Revision pending"


def status_of(record):
    """Where the standard is in its life cycle, worked out from the page:
    in development (no approved version yet), approved, being revised (a
    revision is under way but no new version is listed), or revision pending
    (a revised version is listed, awaiting its start date). None if the
    record is missing or has no recognisable state."""
    if not record:
        return None
    notice = record.get("notice_text") or ""
    rows = _rows(record)
    if _IN_DEVELOPMENT.search(notice):
        return IN_DEVELOPMENT
    if any(v.lower().startswith(_PENDING_LABEL) for v in rows):
        return REVISION_PENDING
    if _BEING_REVISED.search(notice):
        return BEING_REVISED
    if any(v for v in rows):
        return APPROVED
    return None


def _label(version):
    if version.lower().startswith(_PENDING_LABEL):
        return "Revised version"
    return f"Version {version}"


def _short_detail(row):
    detail = (row.get("Change detail") or "").strip().rstrip(".")
    return f" ({detail})" if detail and len(detail) <= 70 else ""


def _status_event(previous, current, old, new):
    was, now = status_of(previous), status_of(current)
    if was == now or not was or not now:
        return None

    def start_of(version):
        row = new.get(version) or {}
        start = row.get("Earliest start date")
        return (version, start if _is_set(start) else None, _short_detail(row))

    if now == REVISION_PENDING:
        version = next(v for v in new if v.lower().startswith(_PENDING_LABEL))
        _, start, detail = start_of(version)
        when = f"new version starts {fmt_date(start)}" if start else "start date not yet set"
        lead = "New version announced" if was == BEING_REVISED else "Now in revision"
        return {"text": f"{lead}: {when}{detail}", "effective": start}

    if now == APPROVED:
        added = [v for v in new if v not in old and v]
        version = added[0] if added else next(v for v in new if v)
        _, start, detail = start_of(version)
        when = f"version {version} starts {fmt_date(start)}" if start else f"version {version}, start date not yet set"
        lead = "Revision complete" if was in (BEING_REVISED, REVISION_PENDING) else "Approved for delivery"
        arrow = f"{was} → approved" if was == IN_DEVELOPMENT else lead
        return {"text": f"{arrow}: {when}{detail}", "effective": start}

    if now == BEING_REVISED:
        return {"text": "Now in revision: new version not yet published", "effective": None}

    return {"text": f"{was} → {now.lower()}", "effective": None}


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
    status_event = _status_event(previous, current, old, new)
    if status_event:
        events.append(status_event)
    pending_gone = [v for v in old if v.lower().startswith(_PENDING_LABEL) and v not in new]
    added_numbered = [v for v in new if v not in old and not v.lower().startswith(_PENDING_LABEL)]

    for version, row in new.items():
        start, end = row.get("Earliest start date"), row.get("Latest start date")
        if version not in old:
            if status_event:
                continue  # already covered by the status headline
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

    if pending_gone and not added_numbered and not status_event:
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
