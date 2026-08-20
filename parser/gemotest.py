# -*- coding: utf-8 -*-
"""
Скрейпер каталога Гемотеста (Москва). Цены в серверном HTML (Bitrix SSR),
headless не нужен. Обходим дерево каталога крови и собираем карточки анализов.

Карточка: .analysis-item  ->  <a href=".../slug/"> название,  первая .catalog-cart-button__price = обычная цена.
"""
import re, time, json, sys, io
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "https://gemotest.ru"
ROOT = "/moskva/catalog/issledovaniya-krovi/"      # ветка «Исследования крови»
PREFIX = "/moskva/catalog/"                          # обходим только каталог Москвы
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ru-RU,ru;q=0.9"}

session = requests.Session()
session.headers.update(UA)

def get(url, tries=3):
    for i in range(tries):
        try:
            r = session.get(url, timeout=25)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
        time.sleep(1.5 * (i + 1))
    return None

_price_re = re.compile(r"(\d[\d\s]*)\s*₽")

def parse_page(html):
    """Вернёт список карточек анализов на странице: [{name, slug, price}]."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for item in soup.select(".analysis-item"):
        a = item.select_one('a[href*="/catalog/"]')
        price_el = item.select_one(".catalog-cart-button__price")
        if not a or not price_el:
            continue
        m = _price_re.search(price_el.get_text())
        if not m:
            continue
        name = a.get_text(" ", strip=True)
        slug = a.get("href", "").strip()
        price = int(re.sub(r"\D", "", m.group(1)))
        if name and slug:
            out.append({"name": name, "slug": slug, "price": price})
    return out

def category_links(html):
    """Ссылки внутри каталога крови для дальнейшего обхода."""
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.select('a[href^="' + ROOT + '"]'):
        href = a.get("href", "").split("?")[0].split("#")[0]
        if href.startswith(ROOT):
            links.add(href)
    return links

def crawl(max_pages=400, delay=0.35, verbose=True):
    seen_pages, queue = set(), [ROOT]
    products = {}          # slug -> {name, price, section}
    pages_done = 0
    while queue and pages_done < max_pages:
        path = queue.pop(0)
        if path in seen_pages:
            continue
        seen_pages.add(path)
        html = get(urljoin(BASE, path))
        pages_done += 1
        if not html:
            if verbose: print(f"  ! пропуск {path}")
            continue
        cards = parse_page(html)
        for c in cards:
            slug = c["slug"]
            if slug not in products or c["price"] < products[slug]["price"]:
                products[slug] = {"name": c["name"], "price": c["price"], "section": path}
        for link in category_links(html):
            if link not in seen_pages:
                queue.append(link)
        if verbose and pages_done % 10 == 0:
            print(f"  ...{pages_done} стр, товаров {len(products)}, очередь {len(queue)}")
        time.sleep(delay)
    return products, pages_done

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    print(f"Гемотест: обход каталога крови (лимит {limit} стр)...")
    products, pages = crawl(max_pages=limit)
    print(f"Готово: {pages} страниц, {len(products)} уникальных анализов.")
    json.dump(products, open("parser/raw_gemotest.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("Сохранено -> parser/raw_gemotest.json")
    for slug, p in list(products.items())[:15]:
        print(f"  {p['price']:>6} ₽  {p['name']}")
