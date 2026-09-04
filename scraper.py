"""Scrapes HK university social science talk listings into talks.json."""

import json
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; hk-academic-events-bot/1.0)"
REQUEST_TIMEOUT = 20

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


def fetch_soup(url):
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def scrape_hku():
    url = "https://web.socsc.hku.hk/events/"
    talks = []
    try:
        soup = fetch_soup(url)
        items = soup.select("article") or soup.select(".event") or soup.select("li")
        for item in items:
            link_tag = item.find("a", href=True)
            title_tag = item.find(["h1", "h2", "h3", "h4"]) or link_tag
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not title:
                continue
            date_tag = item.find(class_=lambda c: c and "date" in c.lower()) if item.find(class_=True) else None
            date = date_tag.get_text(strip=True) if date_tag else ""
            link = link_tag["href"] if link_tag else url
            if link.startswith("/"):
                link = "https://web.socsc.hku.hk" + link
            talks.append({
                "title": title,
                "institution": "HKU",
                "department": "Faculty of Social Sciences",
                "date": date,
                "disciplines": classify_disciplines(title),
                "link": link,
            })
    except Exception as exc:
        print(f"HKU scrape failed: {exc}")
    return talks


def scrape_cuhk():
    url = "https://www.soc.cuhk.edu.hk/about/seminars-workshops/"
    talks = []
    try:
        soup = fetch_soup(url)
        items = soup.select("article") or soup.select(".event") or soup.select("li")
        for item in items:
            link_tag = item.find("a", href=True)
            title_tag = item.find(["h1", "h2", "h3", "h4"]) or link_tag
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not title:
                continue
            date_tag = item.find(class_=lambda c: c and "date" in c.lower()) if item.find(class_=True) else None
            date = date_tag.get_text(strip=True) if date_tag else ""
            link = link_tag["href"] if link_tag else url
            if link.startswith("/"):
                link = "https://www.soc.cuhk.edu.hk" + link
            talks.append({
                "title": title,
                "institution": "CUHK",
                "department": "Department of Sociology",
                "date": date,
                "disciplines": classify_disciplines(title),
                "link": link,
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
