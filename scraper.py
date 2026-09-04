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
import ssl
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from requests.adapters import HTTPAdapter

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


class LegacySSLAdapter(HTTPAdapter):
    """EdUHK's server requires legacy TLS renegotiation, which OpenSSL 3 blocks by default."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.options |= 0x4  # SSL_OP_LEGACY_SERVER_CONNECT
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def make_talk(*, title, institution, department, date_text, speaker, description, link, cutoff, display_date=None):
    """Builds a talk dict, or returns None if the date is missing/unparseable/too old.

    date_text is used for cutoff parsing and must be the *date only* (no time
    range) - a trailing "3:30 - 5:00 pm" would otherwise be misread as a date
    range by parse_event_date's range-splitting. Pass display_date separately
    (e.g. "23 September 2026, 3:30 - 5:00 pm") when it should differ from
    date_text; it defaults to parse_event_date's cleaned version of date_text.
    """
    start_date, end_date, cleaned_date_text = parse_event_date(date_text)
    if start_date is None:
        return None
    if end_date.replace(tzinfo=HK_TZ) < cutoff:
        return None
    clean_title = strip_title_date_prefix(title)
    return {
        "title": clean_title,
        "institution": institution,
        "department": department,
        "date": display_date if display_date is not None else cleaned_date_text,
        "speaker": speaker,
        "description": description,
        "disciplines": classify_disciplines(f"{clean_title} {description}"),
        "link": link,
    }


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

            talk = make_talk(
                title=raw_title,
                institution=institution,
                department=department,
                date_text=date_text,
                display_date=full_date_text,
                speaker=speaker,
                description=description,
                link=link,
                cutoff=cutoff,
            )
            if talk:
                talks.append(talk)
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


def scrape_hkust():
    """Listing page has full date/venue per row (Drupal views), no per-event fetch needed."""
    base = "https://sosc.hkust.edu.hk"
    talks = []
    cutoff = cutoff_datetime()
    try:
        r = requests.get(f"{base}/event", headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for row in soup.select(".views-row"):
            link_tag = row.select_one(".detail h2 a") or row.select_one("h2 a")
            if not link_tag:
                continue
            title = clean_text(link_tag.get_text())
            link = urljoin(base, link_tag.get("href", ""))
            time_tag = row.select_one(".date time")
            date_text = re.sub(r"\s+", " ", time_tag.get_text(strip=True)) if time_tag else ""
            venue = clean_text(row.select_one(".venue").get_text()) if row.select_one(".venue") else ""
            talk = make_talk(
                title=title,
                institution="HKUST",
                department="Division of Social Science",
                date_text=date_text,
                speaker="",
                description=f"Venue: {venue}" if venue else "",
                link=link,
                cutoff=cutoff,
            )
            if talk:
                talks.append(talk)
    except Exception as exc:
        print(f"HKUST scrape failed: {exc}")
    return talks


def scrape_cityu():
    """Listing cards have title + date; no per-event fetch needed."""
    base = "https://ssweb.cityu.edu.hk"
    talks = []
    cutoff = cutoff_datetime()
    try:
        r = requests.get(f"{base}/en/news-events/upcoming-events", headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("article.card"):
            title_tag = card.select_one(".card__title")
            date_tag = card.select_one(".card__date")
            if not title_tag or not date_tag:
                continue
            title = clean_text(title_tag.get_text())
            link = urljoin(base, title_tag.get("href", ""))
            date_text = clean_text(date_tag.get_text())
            talk = make_talk(
                title=title,
                institution="CityU",
                department="Department of Social and Behavioural Sciences",
                date_text=date_text,
                speaker="",
                description="",
                link=link,
                cutoff=cutoff,
            )
            if talk:
                talks.append(talk)
    except Exception as exc:
        print(f"CityU scrape failed: {exc}")
    return talks


HKBU_FIELD_RE = re.compile(
    r"Speaker:\s*(?P<speaker>.*?)\s*Date:\s*(?P<date>.*?)\s*Time:\s*(?P<time>.*?)\s*"
    r"Location:\s*(?P<location>.*?)\s*(?:Registration link:|Learn More|$)"
)


def scrape_hkbu():
    """Listing page has full speaker/date/time/location per seminar text block."""
    base = "https://socweb.hkbu.edu.hk"
    url = f"{base}/research/seminars.html"
    talks = []
    cutoff = cutoff_datetime()
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for block in soup.select(".c-text"):
            text = block.get_text(" ", strip=True)
            if "Speaker:" not in text or "Date:" not in text:
                continue
            title = clean_text(text.split("Speaker:")[0])
            match = HKBU_FIELD_RE.search(text)
            if not match:
                continue
            speaker = match.group("speaker").strip()
            date_text = match.group("date").strip()
            time_text = match.group("time").strip()
            location = match.group("location").strip()
            full_date_text = f"{date_text}, {time_text}" if date_text and time_text else date_text
            learn_more = block.find("a", string=lambda s: s and "Learn More" in s)
            link = urljoin(base, learn_more["href"]) if learn_more and learn_more.get("href") else url
            talk = make_talk(
                title=title,
                institution="HKBU",
                department="Department of Sociology",
                date_text=date_text,
                display_date=full_date_text,
                speaker=speaker,
                description=f"Location: {location}" if location else "",
                link=link,
                cutoff=cutoff,
            )
            if talk:
                talks.append(talk)
    except Exception as exc:
        print(f"HKBU scrape failed: {exc}")
    return talks


def scrape_lingnan():
    """Carousel slides carry title, speaker, and date as three stacked text nodes."""
    base = "https://www.ln.edu.hk"
    url = f"{base}/socsp/news-and-events/seminars"
    talks = []
    cutoff = cutoff_datetime()
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select(".portrait-carousel-slider__item"):
            title_tag = item.select_one(".portrait-carousel-slider__title")
            text_tags = item.select(".portrait-carousel-slider__text")
            if not title_tag or len(text_tags) < 2:
                continue
            title = clean_text(title_tag.get_text())
            speaker = clean_text(text_tags[0].get_text())
            date_text = clean_text(text_tags[1].get_text())
            link_tag = item.select_one(".portrait-carousel-slider__link")
            link = urljoin(base, link_tag["href"]) if link_tag and link_tag.get("href") else url
            talk = make_talk(
                title=title,
                institution="Lingnan",
                department="Department of Sociology & Social Policy",
                date_text=date_text,
                speaker=speaker,
                description="",
                link=link,
                cutoff=cutoff,
            )
            if talk:
                talks.append(talk)
    except Exception as exc:
        print(f"Lingnan scrape failed: {exc}")
    return talks


def scrape_eduhk():
    """Server requires legacy TLS renegotiation; listing has title/date/time/venue, no speaker."""
    base = "https://www.eduhk.hk"
    url = f"{base}/ssps/news-events/events"
    talks = []
    cutoff = cutoff_datetime()
    try:
        session = requests.Session()
        session.mount("https://", LegacySSLAdapter())
        r = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select(".event-card"):
            title_tag = card.select_one(".card-title")
            date_tag = card.select_one(".card-date time")
            if not title_tag or not date_tag:
                continue
            title = clean_text(title_tag.get_text())
            date_text = re.sub(r"\s+", " ", date_tag.get_text(strip=True))
            time_text = clean_text(card.select_one(".card-time").get_text()) if card.select_one(".card-time") else ""
            venue = clean_text(card.select_one(".card-address").get_text()) if card.select_one(".card-address") else ""
            full_date_text = f"{date_text}, {time_text}" if date_text and time_text else date_text
            link_tag = card.find("a", href=True)
            link = urljoin(base, link_tag["href"]) if link_tag else url
            talk = make_talk(
                title=title,
                institution="EdUHK",
                department="Department of Social Sciences and Policy Studies",
                date_text=date_text,
                display_date=full_date_text,
                speaker="",
                description=f"Venue: {venue}" if venue else "",
                link=link,
                cutoff=cutoff,
            )
            if talk:
                talks.append(talk)
    except Exception as exc:
        print(f"EdUHK scrape failed: {exc}")
    return talks


def main():
    talks = (
        scrape_hku()
        + scrape_cuhk()
        + scrape_hkust()
        + scrape_cityu()
        + scrape_hkbu()
        + scrape_lingnan()
        + scrape_eduhk()
    )
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
