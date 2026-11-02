"""
One-off: rebuild data/events.json by replaying the git history of the
snapshots in data/, using each commit's date as the "noticed" date.

Run from the project root:  python backfill_events.py
"""
import json
import subprocess
import glob
import os

from events import derive_events, save_events


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def main():
    all_events = []
    for path in sorted(glob.glob("data/ST*.json")):
        ref = os.path.basename(path)[:-5]
        commits = git("log", "--reverse", "--format=%H %cI", "--", path).split("\n")
        previous = None
        for line in filter(None, commits):
            sha, stamp = line.split(" ", 1)
            snap = json.loads(git("show", f"{sha}:{path.replace(os.sep, '/')}"))
            evs = derive_events(previous, snap)
            for ev in evs:
                all_events.append({"run": stamp[:16], "reference": ref,
                                   "name": snap["title"], "text": ev["text"],
                                   "effective": ev["effective"]})
            previous = snap
    all_events.sort(key=lambda e: e["run"], reverse=True)
    save_events(all_events)
    print(f"{len(all_events)} events written")


if __name__ == "__main__":
    main()
