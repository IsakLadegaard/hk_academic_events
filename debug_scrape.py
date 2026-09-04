"""Temporary: inspect structure of candidate event pages for new universities."""

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; hk-academic-events-bot/1.0)"}

SITES = [
    ("HKUST", "https://sosc.hkust.edu.hk", "https://sosc.hkust.edu.hk/event"),
    ("CityU", "https://ssweb.cityu.edu.hk", "https://ssweb.cityu.edu.hk/en/news-events/upcoming-events"),
    ("PolyU-APSS", "https://www.polyu.edu.hk", "https://www.polyu.edu.hk/apss/news-and-events/event/"),
    ("HKBU", "https://socweb.hkbu.edu.hk", "https://socweb.hkbu.edu.hk/research/seminars.html"),
    ("Lingnan", "https://www.ln.edu.hk", "https://www.ln.edu.hk/socsp/news-and-events/seminars"),
    ("EdUHK", "https://www.eduhk.hk", "https://www.eduhk.hk/ssps/news-events/events"),
]


def check_wp_api(label, base):
    try:
        r = requests.get(f"{base}/wp-json/wp/v2/types", headers=UA, timeout=15)
        print(f"[{label}] wp types status: {r.status_code}")
        if r.status_code == 200:
            print(f"[{label}] types: {list(r.json().keys())}")
    except Exception as exc:
        print(f"[{label}] wp check error: {exc}")


def inspect_page(label, url):
    print(f"\n===== {label}: {url} =====")
    try:
        r = requests.get(url, headers=UA, timeout=20)
        print("status:", r.status_code, "len:", len(r.text))
    except Exception as exc:
        print("fetch error:", exc)
        return
    soup = BeautifulSoup(r.text, "html.parser")
    for sel in ["article", ".event", ".event-item", "li.event", ".views-row",
                "[class*='event']", "[class*='seminar']", ".post", "table tr"]:
        try:
            found = soup.select(sel)
        except Exception:
            continue
        if found:
            print(f"{sel!r}: {len(found)} matches")
    main = soup.find("main") or soup.find(id="content") or soup.find("body")
    print("--- text snippet (first 1500 chars) ---")
    print(main.get_text("\n", strip=True)[:1500] if main else "(none)")


if __name__ == "__main__":
    for label, base, url in SITES:
        check_wp_api(label, base)
        inspect_page(label, url)
