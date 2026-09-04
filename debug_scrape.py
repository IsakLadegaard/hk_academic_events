"""Temporary: find HKBU seminar card container."""

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; hk-academic-events-bot/1.0)"}


def walk_up_from_text(soup, needle, max_levels=8):
    node = soup.find(string=lambda s: s and needle in s)
    if node is None:
        print(f"text {needle!r} not found")
        return None
    el = node.parent
    for i in range(max_levels):
        if el is None:
            break
        classes = el.get("class")
        print(f"level {i}: <{el.name} class={classes}>")
        el = el.parent
    return node


def hkbu():
    print("\n===== HKBU: walk up from known strings =====")
    r = requests.get("https://socweb.hkbu.edu.hk/research/seminars.html", headers=UA, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    node = walk_up_from_text(soup, "Speaker:")
    if node:
        ancestor = node.parent.parent.parent
        print("\n--- candidate container (level 2 up) HTML ---")
        print(ancestor.prettify()[:2500])
        ancestor4 = node.parent.parent.parent.parent
        print("\n--- candidate container (level 3 up) HTML ---")
        print(ancestor4.prettify()[:3000])


if __name__ == "__main__":
    hkbu()
