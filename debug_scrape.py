"""Temporary: find the repeating event-card container by anchoring on known text."""

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


def walk_up_from_text(soup, needle, max_levels=6):
    node = soup.find(string=lambda s: s and needle in s)
    if node is None:
        print(f"text {needle!r} not found")
        return
    el = node.parent
    for i in range(max_levels):
        if el is None:
            break
        classes = el.get("class")
        print(f"level {i}: <{el.name} class={classes}>")
        el = el.parent


def lingnan():
    print("\n===== Lingnan: walk up from known strings =====")
    r = requests.get("https://www.ln.edu.hk/socsp/news-and-events/seminars", headers=UA, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    walk_up_from_text(soup, "Dr. Sabrina SU")
    print()
    walk_up_from_text(soup, "Promoting an expanded notion")
    # print the repeating container's full outer HTML once identified
    node = soup.find(string=lambda s: s and "Dr. Sabrina SU" in s)
    if node:
        ancestor = node.parent.parent.parent
        print("\n--- candidate container HTML ---")
        print(ancestor.prettify()[:2500])


def eduhk():
    print("\n===== EdUHK: walk up from known strings =====")
    session = requests.Session()
    session.mount("https://", LegacySSLAdapter())
    r = session.get("https://www.eduhk.hk/ssps/news-events/events", headers=UA, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    walk_up_from_text(soup, "Qualitative Methods with Vulnerable Populations")
    node = soup.find(string=lambda s: s and "Qualitative Methods with Vulnerable Populations" in s)
    if node:
        ancestor = node.parent.parent.parent
        print("\n--- candidate container HTML ---")
        print(ancestor.prettify()[:2500])


if __name__ == "__main__":
    lingnan()
    eduhk()
