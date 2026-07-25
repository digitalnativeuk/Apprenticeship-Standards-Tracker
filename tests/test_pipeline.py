"""
Proves the pipeline works end-to-end using saved HTML fixtures instead of a
live network call (this sandbox can't reach skillsengland.education.gov.uk).

Run from the project root:  python tests/test_pipeline.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import parse_standard
from diff_engine import save_snapshot, load_previous, compare, append_changelog
from generate_site import build_site

FIXTURE_DIR = os.path.dirname(os.path.abspath(__file__))
URL = "https://skillsengland.education.gov.uk/apprenticeships/st1472"


def read_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def main():
    # --- "Day 1" check ---
    day1_html = read_fixture("fixture_st1472.html")
    day1_record = parse_standard(day1_html, URL)
    print("=== Day 1 parsed record ===")
    print(f"Title: {day1_record['title']}")
    print(f"Notice text:\n{day1_record['notice_text']}\n")
    print(f"Version log rows: {day1_record['version_log']}")
    print(f"Trailblazer email: {day1_record['trailblazer_email']}")

    save_snapshot("ST1472", day1_record)

    # --- "Day 2" check: go-live date has slipped from 1 Aug to 1 Oct ---
    day2_html = read_fixture("fixture_st1472_updated.html")
    day2_record = parse_standard(day2_html, URL)

    previous = load_previous("ST1472")
    changes = compare(previous, day2_record)

    print("\n=== Day 2 diff result ===")
    if changes:
        for c in changes:
            print(f"  CHANGE DETECTED: {c}")
    else:
        print("  No changes found (this would be a bug -- the date changed!)")

    assert changes, "Expected the date change to be detected"
    append_changelog("ST1472", "Administration assistant", changes)
    save_snapshot("ST1472", day2_record)

    # --- Build the site from this state ---
    results = [{
        "reference": "ST1472",
        "name": "Administration assistant",
        "url": URL,
        "current": day2_record,
    }]
    build_site(results)
    print("\nSite built at site/index.html")
    print("\nPIPELINE TEST PASSED")


if __name__ == "__main__":
    main()
