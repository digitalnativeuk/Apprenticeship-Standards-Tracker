"""
Compares a freshly-scraped record against the last saved snapshot for the
same standard, and produces a list of human-readable change descriptions.
"""
import json
import os
from datetime import datetime, timezone

DATA_DIR = "data"


def _snapshot_path(reference):
    return os.path.join(DATA_DIR, f"{reference}.json")


def load_previous(reference):
    path = _snapshot_path(reference)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(reference, record):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_snapshot_path(reference), "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)


def compare(previous, current):
    """Returns a list of change strings. Empty list = no change."""
    if previous is None:
        return []  # first-ever check: nothing to compare against yet

    changes = []

    if previous.get("title") != current.get("title"):
        changes.append(
            f'Title changed: "{previous.get("title")}" -> "{current.get("title")}"'
        )

    if previous.get("notice_hash") != current.get("notice_hash"):
        changes.append(
            "Status/notice text changed on the page (banner, revision note, "
            "date, or guidance wording) -- check the standard's page for detail."
        )

    prev_versions = {tuple(r) for r in previous.get("version_log", [])}
    curr_versions = {tuple(r) for r in current.get("version_log", [])}
    new_rows = curr_versions - prev_versions
    for row in new_rows:
        changes.append(f"Version log entry added/changed: {' | '.join(row)}")

    if previous.get("trailblazer_email") != current.get("trailblazer_email"):
        changes.append(
            f'Trailblazer contact changed: {previous.get("trailblazer_email")} '
            f'-> {current.get("trailblazer_email")}'
        )

    return changes


def append_changelog(reference, name, changes):
    if not changes:
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "changelog.json")
    log = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            log = json.load(f)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "reference": reference,
        "name": name,
        "changes": changes,
    }
    log.insert(0, entry)  # newest first
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
