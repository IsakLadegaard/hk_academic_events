"""Temporary: raw HTML structure for Lingnan and EdUHK event listings."""

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


def lingnan():
    print("\n===== Lingnan structure =====")
    r = requests.get("https://www.ln.edu.hk/socsp/news-and-events/seminars", headers=UA, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    for sel in [".views-row", "article", ".event-item", ".seminar-item", "li", "[class*='seminar']", "[class*='event']", "[class*='item']"]:
        found = soup.select(sel)
        if found:
            print(f"{sel!r}: {len(found)} matches")
    rows = soup.select(".views-row")[:2] or soup.select("article")[:2]
    for row in rows:
        print("--- row ---")
        print(row.prettify()[:2000])


def eduhk():
    print("\n===== EdUHK structure =====")
    session = requests.Session()
    session.mount("https://", LegacySSLAdapter())
    r = session.get("https://www.eduhk.hk/ssps/news-events/events", headers=UA, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    for sel in [".views-row", "article", ".event-item", "li", "[class*='event']", "[class*='card']", "[class*='item']"]:
        found = soup.select(sel)
        if found:
            print(f"{sel!r}: {len(found)} matches")
    rows = soup.select(".views-row")[:2] or soup.select("article")[:2]
    for row in rows:
        print("--- row ---")
        print(row.prettify()[:2000])


if __name__ == "__main__":
    lingnan()
    eduhk()
