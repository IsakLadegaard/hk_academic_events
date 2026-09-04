"""Temporary: dumps candidate DOM structure for HKU/CUHK event pages."""

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; hk-academic-events-bot/1.0)"}

CANDIDATES = [
    "article",
    ".event",
    ".event-item",
    ".tribe-events-list-event-title",
    ".type-tribe_events",
    "li.event",
    ".post",
    ".elementor-post",
    "[class*='event']",
    "div.views-row",
    "table tr",
]


def inspect(label, url):
    print(f"\n===== {label}: {url} =====")
    r = requests.get(url, headers=UA, timeout=20)
    print("status:", r.status_code, "len:", len(r.text))
    soup = BeautifulSoup(r.text, "html.parser")
    for sel in CANDIDATES:
        try:
            found = soup.select(sel)
        except Exception as exc:
            print(f"{sel!r}: selector error {exc}")
            continue
        print(f"{sel!r}: {len(found)} matches")
    main = soup.find("main") or soup.find(id="content") or soup.find("body")
    print("\n--- snippet of <main> or fallback (first 3000 chars) ---")
    print(str(main)[:3000] if main else "(none found)")


if __name__ == "__main__":
    inspect("HKU", "https://web.socsc.hku.hk/events/")
    inspect("CUHK", "https://www.soc.cuhk.edu.hk/about/seminars-workshops/")
