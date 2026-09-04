"""Scrapes HK university social science talk listings into talks.json.

HKU and CUHK both expose their event listings as a WordPress REST API
custom post type (/wp-json/wp/v2/event) rather than server-rendered HTML,
so we pull structured JSON instead of parsing markup.
"""

import html
import json
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; hk-academic-events-bot/1.0)"
REQUEST_TIMEOUT = 20
MAX_EVENTS_PER_SITE = 100

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
        "disciplines": ["Sociology"],
        "link": "https://web.socsc.hku.hk/events/",
    },
    {
        "title": "Sample Talk: Comparative Public Policy in Greater China",
        "institution": "CUHK",
        "department": "Department of Sociology",
        "date": "TBD",
        "disciplines": ["Political Science & Public Admin"],
        "link": "https://www.soc.cuhk.edu.hk/about/seminars-workshops/",
    },
]


def classify_disciplines(title):
    title_lower = title.lower()
    matched = []
    for discipline, keywords in DISCIPLINE_KEYWORDS.items():
        if any(keyword in title_lower for keyword in keywords):
            matched.append(discipline)
    return matched if matched else [DEFAULT_DISCIPLINE]


def clean_text(raw):
    unescaped = html.unescape(raw or "")
    return BeautifulSoup(unescaped, "html.parser").get_text().strip()


def split_date_prefix(raw_title):
    """Some sites prefix titles with a date before a '|', e.g. 'Aug 20 | Talk name'."""
    if "|" in raw_title:
        prefix, rest = raw_title.split("|", 1)
        prefix, rest = prefix.strip(), rest.strip()
        if rest and len(prefix) <= 40 and any(ch.isdigit() for ch in prefix):
            return prefix, rest
    return "", raw_title


def fetch_events(api_base):
    url = f"{api_base}/wp-json/wp/v2/event"
    params = {"per_page": MAX_EVENTS_PER_SITE, "orderby": "date", "order": "desc"}
    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def scrape_hku():
    talks = []
    try:
        events = fetch_events("https://web.socsc.hku.hk")
        for event in events:
            raw_title = clean_text(event.get("title", {}).get("rendered", ""))
            if not raw_title:
                continue
            date, title = split_date_prefix(raw_title)
            talks.append({
                "title": title,
                "institution": "HKU",
                "department": "Faculty of Social Sciences",
                "date": date,
                "disciplines": classify_disciplines(title),
                "link": event.get("link", "https://web.socsc.hku.hk/events/"),
            })
    except Exception as exc:
        print(f"HKU scrape failed: {exc}")
    return talks


def scrape_cuhk():
    talks = []
    try:
        events = fetch_events("https://www.soc.cuhk.edu.hk")
        for event in events:
            raw_title = clean_text(event.get("title", {}).get("rendered", ""))
            if not raw_title:
                continue
            date, title = split_date_prefix(raw_title)
            talks.append({
                "title": title,
                "institution": "CUHK",
                "department": "Department of Sociology",
                "date": date,
                "disciplines": classify_disciplines(title),
                "link": event.get("link", "https://www.soc.cuhk.edu.hk/about/seminars-workshops/"),
            })
    except Exception as exc:
        print(f"CUHK scrape failed: {exc}")
    return talks


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
