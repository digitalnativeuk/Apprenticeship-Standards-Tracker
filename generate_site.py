"""
Builds the static site/index.html from the current standards data and the
changelog. Deliberately dependency-free templating (plain f-strings) so the
project only needs requests + beautifulsoup4. Output is committed to /site
and served via GitHub Pages.
"""
import html
import json
import os
import re
from datetime import datetime, timezone

SITE_DIR = "site"
DATA_DIR = "data"

# Matches the wording Skills England uses in the notice banner for standards
# that aren't in their final/live state, e.g. "This apprenticeship is in
# development ..." / "This apprenticeship is in revision ...".
_PENDING_PATTERN = re.compile(
    r"\bin (development|revision|review)\b|\bunder revision\b|\bbeing revised\b",
    re.IGNORECASE,
)


def lars_code(result):
    """The scraped LARS code for a standard, or None if it doesn't have one
    (or the page couldn't be fetched)."""
    return (result.get("current") or {}).get("lars_code") or None


def format_title(title):
    """Title Case for display purposes only. Words that are already fully
    upper-case in the source (acronyms like "HR", "L2") are left untouched;
    everything else gets its first letter capitalised. Never use this on
    text that feeds the diff engine or gets stored in snapshots -- only on
    the rendered/display layer."""
    if not title:
        return title
    return " ".join(
        w if w.isupper() else w[:1].upper() + w[1:].lower()
        for w in title.split(" ")
    )

CSS = """
:root {
  --navy: #0b2340;
  --slate: #33475b;
  --paper: #f7f5f0;
  --line: #d8d3c7;
  --accent: #b5651d;
  --mono: 'Courier New', monospace;
  --serif: Georgia, 'Times New Roman', serif;
  --sans: -apple-system, 'Segoe UI', Arial, sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--navy);
  font-family: var(--sans);
  line-height: 1.5;
}
a { color: var(--navy); }
header.masthead {
  background: var(--navy);
  color: #fff;
  padding: 2rem 1.5rem;
}
header.masthead h1 {
  font-family: var(--serif);
  margin: 0 0 0.25rem 0;
  font-size: 1.6rem;
  font-weight: 600;
}
header.masthead p {
  margin: 0;
  color: #c9d4e0;
  font-size: 0.95rem;
}
main {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
}
h2.section-title {
  font-family: var(--serif);
  font-size: 1.2rem;
  border-bottom: 2px solid var(--navy);
  padding-bottom: 0.4rem;
  margin-top: 2.5rem;
}
.card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
}
.card .ref {
  font-family: var(--mono);
  font-size: 0.78rem;
  color: var(--accent);
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.card h3 { margin: 0.15rem 0 0.5rem 0; font-size: 1.05rem; }
/* Collapsible status cards: native <details>/<summary>, no JS needed.
   Collapsed shows just the reference + title; the chevron rotates on open. */
details.card > summary {
  display: flex;
  align-items: center;
  gap: 1rem;
  cursor: pointer;
  list-style: none;
}
details.card > summary::-webkit-details-marker { display: none; }
details.card > summary h3 { margin-bottom: 0; }
details.card > summary .summary-heading { flex: 1 1 auto; min-width: 0; }
details.card > summary .chevron {
  flex: none;
  width: 0.5rem;
  height: 0.5rem;
  border-right: 2px solid var(--slate);
  border-bottom: 2px solid var(--slate);
  transform: rotate(45deg);
  transition: transform 0.15s ease;
}
details.card[open] > summary .chevron { transform: rotate(-135deg); }
.card .notice {
  font-size: 0.9rem;
  color: var(--slate);
  white-space: pre-line;
  border-left: 3px solid var(--line);
  padding-left: 0.75rem;
  margin-top: 0.5rem;
}
table.version-log {
  width: 100%;
  border-collapse: collapse;
  margin-top: 0.75rem;
  font-size: 0.85rem;
}
table.version-log th, table.version-log td {
  text-align: left;
  padding: 0.35rem 0.5rem;
  border-bottom: 1px solid var(--line);
}
.timeline-entry {
  border-left: 3px solid var(--accent);
  padding: 0.25rem 0 0.25rem 1rem;
  margin-bottom: 1.25rem;
}
.timeline-entry time { font-family: var(--mono); font-size: 0.75rem; color: var(--slate); }
.timeline-entry ul { margin: 0.35rem 0 0 0; padding-left: 1.1rem; }
.empty-state { color: var(--slate); font-style: italic; }
footer { text-align: center; font-size: 0.8rem; color: var(--slate); padding: 2rem 0; }
"""


def build_site(results):
    os.makedirs(SITE_DIR, exist_ok=True)

    changelog = []
    changelog_path = os.path.join(DATA_DIR, "changelog.json")
    if os.path.exists(changelog_path):
        with open(changelog_path, "r", encoding="utf-8") as f:
            changelog = json.load(f)

    # Status cards read alphabetically by title; the pending table below
    # keeps the configured standards.json order.
    status_results = sorted(results, key=lambda r: format_title(r["name"]).casefold())
    cards_html = "".join(_render_card(r) for r in status_results)

    timeline_html = "".join(_render_timeline_entry(e) for e in changelog[:50])
    if not timeline_html:
        timeline_html = '<p class="empty-state">No changes detected yet.</p>'

    pending_results = [
        r for r in results
        if "error" not in r and _PENDING_PATTERN.search(r["current"].get("notice_text") or "")
    ]
    pending_html = _render_pending_table(pending_results)
    if not pending_html:
        pending_html = '<p class="empty-state">No standards currently flagged as in development or in revision.</p>'

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Apprenticeship Standards Tracker</title>
<style>{CSS}</style>
</head>
<body>
<header class="masthead">
  <h1>Apprenticeship Standards Tracker</h1>
  <p>Watching {len(results)} standard(s) on Skills England for status, version and date changes &middot; last checked {now}</p>
</header>
<main>
  <h2 class="section-title">Change log</h2>
  {timeline_html}

  <h2 class="section-title">Standards In Revision/Pending Updates</h2>
  {pending_html}

  <h2 class="section-title">Current status</h2>
  {cards_html}
</main>
<footer>Internal tool &middot; source data from skillsengland.education.gov.uk (Open Government Licence)</footer>
</body>
</html>
"""
    with open(os.path.join(SITE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)


def _card_summary(ref, url, name):
    """The always-visible part of a collapsed status card: reference and
    linked title only, plus the expand/collapse chevron."""
    return f"""
      <summary>
        <div class="summary-heading">
          <div class="ref">{ref}</div>
          <h3><a href="{url}">{name}</a></h3>
        </div>
        <span class="chevron" aria-hidden="true"></span>
      </summary>
    """


def _render_card(result):
    ref = html.escape(result["reference"])
    lars = lars_code(result) or "No LARS Code Available"
    name = html.escape(f"{format_title(result['name'])} ({lars})")
    url = html.escape(result["url"])
    summary_html = _card_summary(ref, url, name)

    if "error" in result:
        return f"""
        <details class="card">
          {summary_html}
          <p class="notice">Could not fetch this page on the last check: {html.escape(result['error'])}</p>
        </details>
        """

    current = result["current"]
    notice = html.escape(current.get("notice_text") or "")
    version_log = current.get("version_log") or []

    table_html = ""
    if version_log:
        header, *rows = version_log
        header_html = "".join(f"<th>{html.escape(h)}</th>" for h in header)
        rows_html = "".join(
            "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>"
            for row in rows
        )
        table_html = f"""
        <table class="version-log">
          <thead><tr>{header_html}</tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        """

    return f"""
    <details class="card">
      {summary_html}
      <div class="notice">{notice}</div>
      {table_html}
    </details>
    """


def _top_version_row(version_log):
    """First data row of the version log (the latest/upcoming entry), keyed
    by its own column headers so column order in the source table doesn't
    matter."""
    if not version_log or len(version_log) < 2:
        return None
    header, first_row = version_log[0], version_log[1]
    return dict(zip(header, first_row))


def _render_pending_table(pending_results):
    """Single table covering every standard flagged as in development/
    revision, one row per standard holding only its most recent version-log
    entry (same row selection as the old per-block layout)."""
    rows_html = ""
    for result in pending_results:
        ref = html.escape(result["reference"])
        lars = html.escape(lars_code(result) or "Not Available")
        name = html.escape(format_title(result["name"]))
        url = html.escape(result["url"])

        top = _top_version_row(result["current"].get("version_log")) or {}
        version = html.escape(top.get("Version") or "—")
        change_detail = html.escape(top.get("Change detail") or "—")
        earliest = html.escape(top.get("Earliest start date") or "—")
        latest = html.escape(top.get("Latest start date") or "—")
        rows_html += f"""
        <tr>
          <td>{ref}</td>
          <td>{lars}</td>
          <td><a href="{url}">{name}</a></td>
          <td>{version}</td>
          <td>{change_detail}</td>
          <td>{earliest}</td>
          <td>{latest}</td>
        </tr>
        """

    if not rows_html:
        return ""

    return f"""
    <table class="version-log">
      <thead>
        <tr>
          <th>Standard Number</th>
          <th>LARS Code</th>
          <th>Standard Title</th>
          <th>Version</th>
          <th>Change detail</th>
          <th>Earliest start date</th>
          <th>Latest start date</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    """


def _render_timeline_entry(entry):
    ts = html.escape(entry["timestamp"])
    ref = html.escape(entry["reference"])
    name = html.escape(format_title(entry["name"]))
    items = "".join(f"<li>{html.escape(c)}</li>" for c in entry["changes"])
    return f"""
    <div class="timeline-entry">
      <time>{ts}</time> &middot; <strong>{ref} &mdash; {name}</strong>
      <ul>{items}</ul>
    </div>
    """
