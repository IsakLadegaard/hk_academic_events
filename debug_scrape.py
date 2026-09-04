"""Temporary: inspect a single event page's HTML for date/speaker/abstract structure."""

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; hk-academic-events-bot/1.0)"}

SAMPLE_URLS = [
    ("HKU", "https://web.socsc.hku.hk/event/coevolving-game-playing-strategies/"),
    ("HKU", "https://web.socsc.hku.hk/event/gs-tfpa/"),
    ("CUHK", "https://www.soc.cuhk.edu.hk/event/aug-20-csslcuhk-webinar-using-images-to-study-protest-dynamics/"),
]


def inspect(label, url):
    print(f"\n===== {label}: {url} =====")
    r = requests.get(url, headers=UA, timeout=20)
    print("status:", r.status_code, "len:", len(r.text))
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.find("main") or soup.find("article") or soup.find(id="content") or soup.find("body")
    text = main.get_text("\n", strip=True) if main else ""
    print("--- visible text (first 3000 chars) ---")
    print(text[:3000])
    print("\n--- raw HTML around 'speaker'/'date'/'time'/'venue' keywords ---")
    html_lower = r.text.lower()
    for kw in ["speaker", "abstract", "date:", "time:", "venue", "bio"]:
        idx = html_lower.find(kw)
        if idx != -1:
            print(f"[{kw}] context: ...{r.text[max(0,idx-100):idx+300]}...")
        else:
            print(f"[{kw}] not found")


if __name__ == "__main__":
    for label, url in SAMPLE_URLS:
        inspect(label, url)
