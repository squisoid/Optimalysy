# -*- coding: utf-8 -*-
"""
Скрейпер каталога KDL (Москва).
Стратегия: собираем ВСЕ московские URL из sitemap (sitemap_stat.xml → sitemap_part_*.xml),
затем обходим каждую товарную страницу и берём название + цену из SSR-разметки.
Хабы-категории (нет .analysis-price__number) пропускаются автоматически.
"""
import re, time, json, sys, io, os
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "https://kdl.ru"
PREFIX = "/analizy-i-tseny/msk/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ru-RU,ru;q=0.9"}

_price_re = re.compile(r"(\d[\d\s\xa0]*)\s*₽")
_suffix_re = re.compile(r"\s+в\s+Москве\s+и\s+МО\s*$", re.I)

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


def collect_sitemap_urls():
    """Собрать все московские URL анализов из sitemap KDL."""
    index_xml = get(f"{BASE}/sitemap_stat.xml")
    if not index_xml:
        print("  ! не удалось получить sitemap_stat.xml")
        return []

    parts = re.findall(r"<loc>(https://kdl\.ru/sitemap_part_\d+\.xml)</loc>", index_xml)
    urls = []
    for part_url in parts:
        xml = get(part_url)
        if not xml:
            continue
        found = re.findall(r"<loc>(https://kdl\.ru" + re.escape(PREFIX) + r"[^<]+)</loc>", xml)
        urls.extend(found)
    return urls


def parse_product_page(html):
    """Извлечь название и цену с товарной страницы. None если это хаб."""
    soup = BeautifulSoup(html, "lxml")
    price_el = soup.select_one(".analysis-price__number")
    if not price_el:
        return None
    m = _price_re.search(price_el.get_text())
    if not m:
        return None
    price = int(re.sub(r"\D", "", m.group(1)))

    h1 = soup.select_one("h1")
    if not h1:
        return None
    name = _suffix_re.sub("", h1.get_text(" ", strip=True))

    return {"name": name, "price": price}


def crawl(max_pages=3000, delay=0.3, verbose=True):
    if verbose:
        print("  Собираю URL из sitemap...")
    all_urls = collect_sitemap_urls()
    if verbose:
        print(f"  Найдено {len(all_urls)} московских URL в sitemap")
    if not all_urls:
        return {}, 0

    all_urls = all_urls[:max_pages]
    products = {}
    pages_done = 0
    skipped = 0

    for url in all_urls:
        html = get(url)
        pages_done += 1
        if not html:
            skipped += 1
            continue
        result = parse_product_page(html)
        if result is None:
            skipped += 1
            continue
        slug = url.replace(BASE, "")
        products[slug] = {"name": result["name"], "price": result["price"], "src": "sitemap"}
        if verbose and pages_done % 50 == 0:
            print(f"  ...{pages_done}/{len(all_urls)} стр, товаров {len(products)}, "
                  f"пропущено {skipped}")
        time.sleep(delay)

    return products, pages_done


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    print(f"KDL: обход каталога через sitemap (лимит {limit} стр)...")
    products, pages = crawl(max_pages=limit)
    print(f"Готово: {pages} страниц обработано, {len(products)} уникальных анализов.")
    json.dump(products, open("parser/raw_kdl.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("Сохранено -> parser/raw_kdl.json")
    for slug, p in list(products.items())[:15]:
        print(f"  {p['price']:>6} ₽  {p['name']}")
