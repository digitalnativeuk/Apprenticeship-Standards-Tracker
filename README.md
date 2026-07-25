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

`scraper.py` has been run against both live URLs in `standards.json`
(ST1472 and ST0135) and its output checked field-by-field against what's
actually on the pages. The notice-text extraction now targets the site's
`div.overviewSection` container directly (with a heading/stop-word based
fallback for pages that lack it), which fixed duplicated/truncated output
from the original heading-heuristic approach. Version log and trailblazer
email extraction matched the live pages without changes.

If the site's markup changes in future, each `_get_*` function in
`scraper.py` is independent, so fixing one won't break the others — rerun
`python scraper.py <url>` and compare against the page.

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
