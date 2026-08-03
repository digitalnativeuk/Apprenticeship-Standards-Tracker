# Apprenticeship Standards Tracker

Watches specific Skills England apprenticeship standard pages and flags
status, version, date, and guidance changes — so nobody has to keep
re-checking the site by hand.

**What it tracks per standard** (metadata level, not the full KSB/duties text):
- Page title
- The banner/notice text between the heading and "Contents" (this is where
  "in development", "in revision", go-live dates, funding-band mentions and
  guidance notes all live — a single hash catches any wording change here)
- The Version log table (version number, change detail, earliest/latest
  start dates)
- The LARS code (see the caveat under "Validated against the live site")
- The trailblazer contact email

**Cost: £0.** Runs entirely on GitHub's free tier (Actions + Pages).

## How it works

```
GitHub Actions (on a daily schedule)
  -> run_check.py
       -> scraper.py fetches each URL in standards.json
       -> diff_engine.py compares it to data/<REF>.json (last snapshot)
            -> logs any changes to data/changelog.json
       -> generate_site.py rebuilds site/index.html
  -> commits the updated data/ and site/ back to the repo
  -> publishes site/ to GitHub Pages
```

## What the published page shows

Three sections, top to bottom:

1. **Change log** — most recent detected changes, newest first.
2. **Standards In Revision/Pending Updates** — one combined table covering
   every standard whose notice text flags it as in development/revision/
   review. One row per standard showing only its most recent version-log
   entry: Standard Number, LARS Code, Standard Title, Version, Change
   detail, Earliest start date, Latest start date.
3. **Current status** — one collapsible card per standard, sorted
   alphabetically by title. Collapsed, a card shows just the reference and
   the linked title as `Title (LARS code)`; expanding it reveals the notice
   text and that standard's full version log. Built on native
   `<details>`/`<summary>`, so there's no JavaScript on the page.

Standard titles are displayed in Title Case via a single `format_title()`
helper in `generate_site.py`, used everywhere a title is rendered. Words
that are already fully upper-case in the source are treated as acronyms and
left alone, so "HR support" displays as "HR Support", not "Hr Support".
This is display-only — the raw scraped title is what gets stored in
snapshots and compared by the diff engine, so casing never affects change
detection.

Where a standard has no LARS code (brand-new standards not yet approved for
delivery), the table cell reads "Not Available" and the card title reads
"No LARS Code Available".

## First-time setup (10 minutes, no cost)

1. **Create a new GitHub repository** (private is fine — GitHub Pages can
   serve from a private repo on the free plan too).
2. Push everything in this folder to that repo.
3. In the repo: **Settings > Pages > Source** → select **GitHub Actions**.
4. In the repo: **Settings > Actions > General > Workflow permissions** →
   select **Read and write permissions** (the workflow needs this to commit
   the snapshot/changelog back).
5. Go to the **Actions** tab, select "Check apprenticeship standards", and
   click **Run workflow** to trigger the first check manually.
6. Once it finishes, your page will be live at:
   `https://<your-username>.github.io/<repo-name>/`
   — that's the link you share with anyone.

After that, it checks automatically every day at 06:00 UTC
(edit the `cron:` line in `.github/workflows/check.yml` to change this).

## Adding or removing standards

Edit `standards.json` — add an entry with a name, reference, and the
standard's own page URL (not the search/list page). No code changes needed.

## Validated against the live site

`scraper.py` has been run against the live URLs in `standards.json` and its
output checked field-by-field against what's actually on the pages
(ST1472 and ST0135 in detail). The notice-text extraction now targets the site's
`div.overviewSection` container directly (with a heading/stop-word based
fallback for pages that lack it), which fixed duplicated/truncated output
from the original heading-heuristic approach. Version log and trailblazer
email extraction matched the live pages without changes.

If the site's markup changes in future, each `_get_*` function in
`scraper.py` is independent, so fixing one won't break the others — rerun
`python scraper.py <url>` and compare against the page.

### LARS code: read indirectly, and why

The "Key information" panel that displays `Lars code:` to a human is
rendered client-side. It is **not** in the HTML this scraper receives —
searching the raw response for "Lars" returns nothing. Rather than add a
headless browser just for one field, `_get_lars_code()` reads the code from
the "find an assessment organisation" link, which is present server-side and
points at `find-epao.../courses/<lars>/assessment-organisations`.

This was verified against the rendered panel for ST1472 (838), ST0135 (430)
and ST0071 (278), and all tracked standards carry exactly one such link. If
that link ever stops carrying the code, `_get_lars_code()` returns `None`
and the site falls back to the "not available" wording rather than showing a
wrong number. If a standard ever shows a LARS code on the page but "Not
Available" on ours, that link is the thing to check first.

## Extending later

- **Email alerts**: bolt-on, not built by default. Cheapest free options:
  a Gmail account + app password sending via `smtplib` in `run_check.py`,
  or a free-tier transactional email API (e.g. Resend, 100 emails/day free,
  no card required). Ask for this to be added once the base tracker is
  proven out.
- **Full standard/EPA content diffing** (not just metadata): the site
  loads that content via JavaScript, so this would need a headless browser
  step (Playwright) in the GitHub Action. More to maintain — worth adding
  only if the metadata-level tracking proves insufficient.
- **More standards**: just add rows to `standards.json`.

## Files

| File | Purpose |
|---|---|
| `standards.json` | List of standards to track |
| `scraper.py` | Fetches + parses one standard page |
| `diff_engine.py` | Snapshot storage + change detection |
| `generate_site.py` | Builds the static `site/index.html` |
| `run_check.py` | Orchestrates the above; the script Actions runs |
| `.github/workflows/check.yml` | Daily schedule + manual trigger + deploy |
| `data/` | Snapshots + changelog (created/updated automatically) |
| `site/` | The generated static site (published to Pages) |
| `tests/` | Fixture HTML + a pipeline test, no network required |

Note: `tests/test_pipeline.py` writes to the real `data/ST1472.json` and
`data/changelog.json` rather than a scratch directory, so running it
overwrites live snapshot data. Check `git diff data/` afterwards if you do
run it.
