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


def check_wp_api(label, base):
    print(f"\n===== {label} WP REST API: {base} =====")
    try:
        r = requests.get(f"{base}/wp-json/wp/v2/types", headers=UA, timeout=20)
        print("types status:", r.status_code)
        if r.status_code == 200:
            print(list(r.json().keys()))
    except Exception as exc:
        print("types error:", exc)

    for slug in ["events", "event", "tribe_events", "posts"]:
        try:
            r = requests.get(f"{base}/wp-json/wp/v2/{slug}?per_page=5", headers=UA, timeout=20)
            print(f"{slug}: status {r.status_code}, len {len(r.text)}")
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    print("sample keys:", list(data[0].keys()))
                    print("sample title:", data[0].get("title"))
        except Exception as exc:
            print(f"{slug}: error {exc}")


if __name__ == "__main__":
    inspect("HKU", "https://web.socsc.hku.hk/events/")
    inspect("CUHK", "https://www.soc.cuhk.edu.hk/about/seminars-workshops/")
    check_wp_api("HKU", "https://web.socsc.hku.hk")
    check_wp_api("CUHK", "https://www.soc.cuhk.edu.hk")
