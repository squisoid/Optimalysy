# -*- coding: utf-8 -*-
"""
Скрейпер каталога Helix (Москва).
Стратегия: собираем URL каталога из sitemap-saint-petersburg.xml (единый каталог),
затем обходим каждую товарную страницу с префиксом /moskva/ для московских цен.
Название из h1, цена из первого span.typography.typography-huge.
"""
import re, time, json, sys, io
import requests
from bs4 import BeautifulSoup

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "https://helix.ru"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ru-RU,ru;q=0.9"}

_price_re = re.compile(r"(\d[\d\s\xa0]*)\s*₽")
_suffix_re = re.compile(r"\s+в\s+Москве\s*$", re.I)

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
    xml = get(f"{BASE}/sitemap-saint-petersburg.xml")
    if not xml:
        print("  ! не удалось получить sitemap")
        return []
    urls = re.findall(r"<loc>(https://helix\.ru/catalog/item/[^<]+)</loc>", xml)
    return urls


def parse_product_page(html):
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.select_one("h1")
    if not h1:
        return None
    name = _suffix_re.sub("", h1.get_text(" ", strip=True))

    price_el = soup.select_one("span.typography-huge")
    if not price_el:
        return None
    m = _price_re.search(price_el.get_text())
    if not m:
        return None
    price = int(re.sub(r"\D", "", m.group(1)))

    return {"name": name, "price": price}


def crawl(max_pages=4000, delay=0.3, verbose=True):
    if verbose:
        print("  Собираю URL из sitemap...")
    all_urls = collect_sitemap_urls()
    if verbose:
        print(f"  Найдено {len(all_urls)} URL анализов в sitemap")
    if not all_urls:
        return {}, 0

    all_urls = all_urls[:max_pages]
    products = {}
    pages_done = 0
    skipped = 0

    for url in all_urls:
        slug = url.replace(BASE, "")
        msk_url = f"{BASE}/moskva{slug}"
        html = get(msk_url)
        pages_done += 1
        if not html:
            skipped += 1
            continue
        result = parse_product_page(html)
        if result is None:
            skipped += 1
            continue
        products[slug] = {"name": result["name"], "price": result["price"], "src": "sitemap"}
        if verbose and pages_done % 50 == 0:
            print(f"  ...{pages_done}/{len(all_urls)} стр, товаров {len(products)}, "
                  f"пропущено {skipped}")
        time.sleep(delay)

    return products, pages_done


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    print(f"Helix: обход каталога через sitemap (лимит {limit} стр)...")
    products, pages = crawl(max_pages=limit)
    print(f"Готово: {pages} страниц обработано, {len(products)} уникальных анализов.")
    json.dump(products, open("parser/raw_helix.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("Сохранено -> parser/raw_helix.json")
    for slug, p in list(products.items())[:15]:
        print(f"  {p['price']:>6} ₽  {p['name']}")
