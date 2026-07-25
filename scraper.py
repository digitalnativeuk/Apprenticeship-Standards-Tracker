"""
Fetches and parses a Skills England apprenticeship standard page.

Extracts the metadata-level fields that matter for spotting changes:
  - page title
  - the notice/status text block between the H1 and the "Contents" section
    (captured as one text blob + a hash, so ANY wording change in a banner,
    a date, or guidance text is caught -- even without knowing its exact
    HTML class)
  - the "Version log" table (version, change detail, earliest/latest start
    dates)
  - the trailblazer contact email

This is built against the GOV.UK Design System structure the site uses.
If the markup changes, extraction may need small tweaks -- start by
re-running scraper.py directly against one URL and checking the output.
"""
import re
import hashlib
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ApprenticeshipStandardsTracker/1.0; "
        "internal training-provider compliance tool)"
    )
}


def fetch_standard(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return parse_standard(resp.text, url)


def parse_standard(html_text: str, url: str) -> dict:
    """Split out from fetch_standard so it can be unit-tested against a
    saved HTML fixture without hitting the network."""
    soup = BeautifulSoup(html_text, "html.parser")

    title = _get_title(soup)
    notice_text = _get_notice_text(soup)
    version_log = _get_version_log(soup)
    contact_email = _get_trailblazer_email(soup)

    return {
        "url": url,
        "title": title,
        "notice_text": notice_text,
        "notice_hash": _hash(notice_text),
        "version_log": version_log,
        "trailblazer_email": contact_email,
    }


def _get_title(soup):
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else None


def _get_notice_text(soup):
    """The status banner block between the H1 and 'Contents' -- on the live
    site this is a single 'overviewSection' container (in-development /
    in-revision notices, funding-band mentions, guidance text). Collect the
    direct block-level children's text so wording changes anywhere in the
    block are caught without swallowing the rest of the page."""
    section = soup.find("div", class_="overviewSection")
    if section is not None:
        chunks = []
        for el in section.find_all(["div", "p", "h2", "h3", "li"], recursive=True):
            if el.find(["div", "p", "h2", "h3", "li"]) is not None:
                continue  # keep only leaf blocks to avoid nested duplication
            text = el.get_text(" ", strip=True)
            if text and text not in chunks:
                chunks.append(text)
        return "\n".join(chunks)

    # Fallback for pages without the overviewSection container: walk
    # forward from the H1 until something that looks like the "Contents"
    # section, taking only top-level (non-nested) blocks.
    h1 = soup.find("h1")
    if not h1:
        return None
    chunks = []
    stop_words = ("contents", "occupational standard", "apprenticeship summary")
    for el in h1.find_all_next(["p", "h2", "h3", "li"]):
        if el.find_parent(["p", "h2", "h3", "li"]) is not None:
            continue
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if text.lower().startswith(stop_words):
            break
        if text not in chunks:
            chunks.append(text)
        if len(chunks) > 15:  # safety valve
            break
    return "\n".join(chunks)


def _get_version_log(soup):
    heading = soup.find(string=re.compile(r"version log", re.I))
    if not heading:
        return []
    table = None
    node = heading
    for _ in range(20):
        node = node.find_next(["table"])
        if node is not None:
            table = node
            break
    if table is None:
        return []
    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if cells:
            rows.append(cells)
    return rows


def _get_trailblazer_email(soup):
    match = re.search(r"[\w.+-]+@education\.gov\.uk", soup.get_text())
    return match.group(0) if match else None


def _hash(text):
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    # Manual smoke test: python scraper.py <url>
    import sys
    import json

    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://skillsengland.education.gov.uk/apprenticeships/st1472"
    output = json.dumps(fetch_standard(test_url), indent=2, ensure_ascii=False)
    # Windows consoles are often cp1252 and can't encode characters like
    # curly quotes or £ -- write raw UTF-8 bytes so the smoke test doesn't
    # crash on real page content.
    sys.stdout.buffer.write(output.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
