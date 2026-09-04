"""Temporary: deeper structure inspection for HKUST, CityU, PolyU, EdUHK."""

import ssl

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

UA = {"User-Agent": "Mozilla/5.0 (compatible; hk-academic-events-bot/1.0)"}


class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.options |= 0x4  # SSL_OP_LEGACY_SERVER_CONNECT
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def hkust():
    print("\n===== HKUST detail =====")
    r = requests.get("https://sosc.hkust.edu.hk/event", headers=UA, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.select(".views-row")[:3]
    for row in rows:
        print("--- row ---")
        print(row.prettify()[:1500])


def cityu():
    print("\n===== CityU detail =====")
    r = requests.get("https://ssweb.cityu.edu.hk/en/news-events/upcoming-events", headers=UA, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    articles = soup.select("article")[:3]
    for a in articles:
        print("--- article ---")
        print(a.prettify()[:1500])


def polyu():
    print("\n===== PolyU full text (2000-6000 chars) =====")
    r = requests.get("https://www.polyu.edu.hk/apss/news-and-events/event/", headers=UA, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text("\n", strip=True)
    print(text[2000:6000])
    print("\n--- candidate selectors ---")
    for sel in ["article", ".event-item", ".list-item", ".event-list-item", "li", "[class*='card']", "[class*='item']"]:
        found = soup.select(sel)
        if found:
            print(f"{sel!r}: {len(found)} matches")


def eduhk():
    print("\n===== EdUHK with legacy SSL adapter =====")
    session = requests.Session()
    session.mount("https://", LegacySSLAdapter())
    try:
        r = session.get("https://www.eduhk.hk/ssps/news-events/events", headers=UA, timeout=20)
        print("status:", r.status_code, "len:", len(r.text))
        soup = BeautifulSoup(r.text, "html.parser")
        print(soup.get_text("\n", strip=True)[:2000])
    except Exception as exc:
        print("still failing:", exc)


if __name__ == "__main__":
    hkust()
    cityu()
    polyu()
    eduhk()
