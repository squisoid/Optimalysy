# -*- coding: utf-8 -*-
"""
Скрейпер каталога CMD (Москва).
Стратегия: sitemap-iblock-11.part{1-6}.xml -> URL с /msk/ -> товарная страница SSR.
Цена в <span itemprop="price">, имя в h1 (минус " в Москве").
"""
import re, time, json, sys, io
import requests
from bs4 import BeautifulSoup

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "https://www.cmd-online.ru"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ru-RU,ru;q=0.9"}

session = requests.Session()
session.headers.update(UA)


def get(url):
    for attempt in range(3):
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
        time.sleep(2)
    return None


def collect_sitemap_urls():
    urls = set()
    for i in range(1, 7):
        xml = get(f"{BASE}/sitemap-iblock-11.part{i}.xml")
        if not xml:
            continue
        found = re.findall(
            r"<loc>(https://www\.cmd-online\.ru/analizy-i-tseny/katalog-analizov/msk/[^<]+)</loc>",
            xml)
        urls.update(found)
    return sorted(urls)


def parse_product_page(html):
    soup = BeautifulSoup(html, "lxml")
    price_el = soup.find("span", itemprop="price")
    if not price_el:
        return None
    try:
        price = int(price_el.get_text(strip=True).replace(" ", ""))
    except ValueError:
        return None
    h1 = soup.find("h1")
    if not h1:
        return None
    name = h1.get_text(strip=True)
    name = re.sub(r"\s+в\s+Москве\s*$", "", name)
    return {"name": name, "price": price}


def crawl(max_pages=2000, delay=0.3, verbose=True):
    if verbose:
        print("  Собираю URL из sitemap...")
    urls = collect_sitemap_urls()
    if verbose:
        print(f"  Найдено {len(urls)} московских URL в sitemap")

    products = {}
    skipped = 0
    for i, url in enumerate(urls[:max_pages]):
        html = get(url)
        if not html:
            skipped += 1
            continue
        result = parse_product_page(html)
        if not result:
            skipped += 1
            continue
        slug = url.split("/msk/")[1].rstrip("/")
        products[slug] = result
        if verbose and (i + 1) % 50 == 0:
            print(f"  ...{i+1}/{len(urls)} стр, товаров {len(products)}, пропущено {skipped}")
        time.sleep(delay)

    return products


if __name__ == "__main__":
    print("CMD: обход каталога через sitemap...")
    products = crawl()
    print(f"Готово: {len(products)} уникальных анализов.")
    json.dump(products, open("parser/raw_cmd.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("Сохранено -> parser/raw_cmd.json")
    for slug, p in list(products.items())[:15]:
        print(f"  {p['price']:>6} ₽  {p['name'][:60]}")
