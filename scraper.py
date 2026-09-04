"""Scrapes HK university social science talk listings into talks.json.

HKU and CUHK both expose their event listings as a WordPress REST API
custom post type (/wp-json/wp/v2/event), but the listing itself carries no
date or speaker info - that only lives on each event's own page. So for
every listed event we fetch its individual page and parse the date/time/
venue/speaker fields out of its (site-specific) HTML structure.
"""

import html
import json
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

USER_AGENT = "Mozilla/5.0 (compatible; hk-academic-events-bot/1.0)"
REQUEST_TIMEOUT = 20
REQUEST_DELAY_SECONDS = 0.2
MAX_EVENTS_PER_SITE = 80
MAX_PAST_DAYS = 3
HK_TZ = timezone(timedelta(hours=8))

DISCIPLINE_KEYWORDS = {
    "Sociology": ["sociolog", "social theory", "social stratification", "inequality", "social movement"],
    "Political Science & Public Admin": ["politic", "public admin", "governance", "policy", "public sector", "international relations"],
    "Economics": ["econom", "market", "trade", "finance", "labor", "labour"],
    "Psychology": ["psycholog", "cognit", "behavio", "mental health"],
    "Media & Communication": ["media", "communication", "journalism", "digital culture", "social media"],
    "Geography & Urban Planning": ["geograph", "urban", "planning", "spatial", "city", "cities", "housing"],
    "Interdisciplinary/Computational Social Science": ["computational social science", "data science", "network analysis", "machine learning", "interdisciplinary", "big data"],
}

DEFAULT_DISCIPLINE = "General Social Science"

FALLBACK_TALKS = [
    {
        "title": "Sample Talk: Social Inequality in East Asia",
        "institution": "HKU",
        "department": "Faculty of Social Sciences",
        "date": "TBD",
        "speaker": "TBD",
        "description": "Sample entry shown when live scraping returns no results.",
        "disciplines": ["Sociology"],
        "link": "https://web.socsc.hku.hk/events/",
    },
    {
        "title": "Sample Talk: Comparative Public Policy in Greater China",
        "institution": "CUHK",
        "department": "Department of Sociology",
        "date": "TBD",
        "speaker": "TBD",
        "description": "Sample entry shown when live scraping returns no results.",
        "disciplines": ["Political Science & Public Admin"],
        "link": "https://www.soc.cuhk.edu.hk/about/seminars-workshops/",
    },
]


def classify_disciplines(text):
    text_lower = text.lower()
    matched = []
    for discipline, keywords in DISCIPLINE_KEYWORDS.items():
        if any(keyword in text_lower for keyword in keywords):
            matched.append(discipline)
    return matched if matched else [DEFAULT_DISCIPLINE]


def clean_text(raw):
    unescaped = html.unescape(raw or "")
    return BeautifulSoup(unescaped, "html.parser").get_text().strip()


def strip_title_date_prefix(raw_title):
    """Some listings prefix titles with a date before '|', e.g. 'Aug 20 | Talk name'."""
    if "|" in raw_title:
        prefix, rest = raw_title.split("|", 1)
        prefix, rest = prefix.strip(), rest.strip()
        if rest and len(prefix) <= 40 and any(ch.isdigit() for ch in prefix):
            return rest
    return raw_title


def _parse_one_date(text, year_hint):
    try:
        return dateparser.parse(text, fuzzy=True, default=datetime(year_hint, 1, 1))
    except (ValueError, OverflowError):
        return None


def parse_event_date(raw_text):
    """Returns (start, end, display_text). end == start for a single-day event.

    end is used for the "still upcoming" cutoff check so multi-day ranges
    (e.g. "31 August - 3 September 2026") aren't dropped just because they
    started more than MAX_PAST_DAYS ago.
    """
    if not raw_text:
        return None, None, ""
    text = re.sub(r"\([^)]*\)", "", raw_text).strip()
    parts = re.split(r"\s*[–—-]\s*|\s+to\s+", text, maxsplit=1)
    year_hint = datetime.now(HK_TZ).year

    first = parts[0].strip()
    start = _parse_one_date(first, year_hint)
    if start is None:
        return None, None, text

    end = start
    if len(parts) > 1:
        second = parts[1].strip()
        end_year_hint = start.year
        year_match = re.search(r"\d{4}", second)
        parsed_end = _parse_one_date(second, end_year_hint)
        if parsed_end is not None:
            end = parsed_end
            if not re.search(r"\d{4}", first) and year_match:
                start = start.replace(year=end.year)
                end = end.replace(year=end.year)

    return start, end, text


def fetch_events(api_base):
    url = f"{api_base}/wp-json/wp/v2/event"
    params = {"per_page": MAX_EVENTS_PER_SITE, "orderby": "date", "order": "desc"}
    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def fetch_event_page(url):
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


ROLE_LABELS = {"speaker", "speakers", "moderator", "chair", "discussant", "respondent", "panelist", "host"}
SKIP_LINES = ROLE_LABELS | {"biography", "download bio", "bio"}


def _clean_speaker_lines(raw_lines):
    lines = []
    for line in raw_lines:
        normalized = line.strip().rstrip(":").lower()
        if not normalized or normalized in SKIP_LINES:
            continue
        if lines and lines[-1] == line:
            continue  # drop consecutive duplicates (e.g. swiper loop clones)
        lines.append(line)
    return lines


def extract_hku_details(soup):
    info = {}
    for row in soup.select(".hkusocsc-event-detail-info-box-row"):
        labels = row.find_all("h5")
        if len(labels) >= 2:
            key = labels[0].get_text(strip=True).rstrip(":").lower()
            value = labels[1].get_text(" ", strip=True)
            info[key] = value

    speakers = []
    for block in soup.select(".swiper-slide:not(.swiper-slide-duplicate) .event-speaker-info"):
        raw_lines = [line for line in block.get_text("\n", strip=True).split("\n") if line]
        lines = _clean_speaker_lines(raw_lines)
        if lines:
            name = lines[0]
            detail = ", ".join(lines[1:])
            speakers.append((name, detail))

    date_text = info.get("date", "")
    time_text = info.get("time", "")
    full_date_text = f"{date_text}, {time_text}" if date_text and time_text else date_text

    if speakers:
        speaker = "; ".join(s[0] for s in speakers)
        description = "; ".join(f"{s[0]} ({s[1]})" if s[1] else s[0] for s in speakers)
    else:
        speaker = ""
        venue = info.get("venue", "")
        description = f"Venue: {venue}" if venue else ""

    return date_text, full_date_text, speaker, description


def extract_cuhk_details(soup):
    data = {}
    key = None
    for el in soup.select(".saw-entry-details-a, .saw-entry-details-b"):
        classes = el.get("class", [])
        if "saw-entry-details-a" in classes:
            key = el.get_text(strip=True).rstrip(":").lower()
        elif "saw-entry-details-b" in classes and key:
            data[key] = el.get_text(" ", strip=True)
            key = None

    date_text = data.get("date", "")
    time_text = data.get("time", "")
    full_date_text = f"{date_text}, {time_text}" if date_text and time_text else date_text

    speaker_raw = data.get("speakers", "")
    if "," in speaker_raw:
        speaker, description = speaker_raw.split(",", 1)
        speaker, description = speaker.strip(), description.strip()
    else:
        speaker, description = speaker_raw, ""
    if not description:
        venue = data.get("venue", "")
        description = f"Venue: {venue}" if venue else ""

    return date_text, full_date_text, speaker, description


def cutoff_datetime():
    now_hk = datetime.now(HK_TZ)
    return (now_hk - timedelta(days=MAX_PAST_DAYS)).replace(hour=0, minute=0, second=0, microsecond=0)


def scrape_site(api_base, institution, department, extractor):
    talks = []
    cutoff = cutoff_datetime()
    try:
        events = fetch_events(api_base)
        for event in events:
            raw_title = clean_text(event.get("title", {}).get("rendered", ""))
            link = event.get("link", api_base)
            if not raw_title or not link:
                continue
            try:
                soup = fetch_event_page(link)
                date_text, full_date_text, speaker, description = extractor(soup)
            except Exception as exc:
                print(f"{institution} event page failed ({link}): {exc}")
                continue
            finally:
                time.sleep(REQUEST_DELAY_SECONDS)

            start_date, end_date, _ = parse_event_date(date_text)
            if start_date is None:
                continue
            if end_date.replace(tzinfo=HK_TZ) < cutoff:
                continue

            title = strip_title_date_prefix(raw_title)
            talks.append({
                "title": title,
                "institution": institution,
                "department": department,
                "date": full_date_text,
                "speaker": speaker,
                "description": description,
                "disciplines": classify_disciplines(f"{title} {description}"),
                "link": link,
            })
    except Exception as exc:
        print(f"{institution} scrape failed: {exc}")
    return talks


def scrape_hku():
    return scrape_site(
        "https://web.socsc.hku.hk",
        "HKU",
        "Faculty of Social Sciences",
        extract_hku_details,
    )


def scrape_cuhk():
    return scrape_site(
        "https://www.soc.cuhk.edu.hk",
        "CUHK",
        "Department of Sociology",
        extract_cuhk_details,
    )


def main():
    talks = scrape_hku() + scrape_cuhk()
    if not talks:
        talks = FALLBACK_TALKS

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_talks": len(talks),
        "talks": talks,
    }

    with open("talks.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(talks)} talks to talks.json")


if __name__ == "__main__":
    main()
