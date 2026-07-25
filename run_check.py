"""
Orchestrator: reads standards.json, scrapes each standard, diffs it against
the saved snapshot, updates data/, and regenerates the static site.

Run manually with:  python run_check.py
Or on a schedule via .github/workflows/check.yml
"""
import json
import sys
import time

from scraper import fetch_standard
from diff_engine import load_previous, save_snapshot, compare, append_changelog
from generate_site import build_site


def main():
    with open("standards.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    any_changes = False
    results = []

    for standard in config["standards"]:
        name = standard["name"]
        reference = standard["reference"]
        url = standard["url"]

        print(f"Checking {reference} ({name}) ...")
        try:
            current = fetch_standard(url)
        except Exception as exc:
            print(f"  FAILED to fetch {url}: {exc}", file=sys.stderr)
            results.append({"reference": reference, "name": name, "url": url,
                            "error": str(exc)})
            continue

        previous = load_previous(reference)
        changes = compare(previous, current)

        if previous is None:
            print("  first check -- baseline saved, nothing to compare yet")
        elif changes:
            print(f"  {len(changes)} change(s) detected")
            append_changelog(reference, name, changes)
            any_changes = True
        else:
            print("  no change")

        save_snapshot(reference, current)
        results.append({
            "reference": reference,
            "name": name,
            "url": url,
            "current": current,
        })

        time.sleep(1)  # be polite to the site

    build_site(results)
    print(f"Done. Changes detected: {any_changes}")


if __name__ == "__main__":
    main()
