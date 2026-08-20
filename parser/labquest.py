# -*- coding: utf-8 -*-
"""
Скрейпер каталога LabQuest (Москва). Цены в SSR.
Стратегия: BFS по категориям /analizy-i-tseny/*, собираем .medicine__item.
Также заходим на товарные страницы без .medicine__item и берём цену из
.analysis-total-price-new.
"""
import re, time, json, sys, io
import requests
from bs4 import BeautifulSoup

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "https://www.labquest.ru"
ROOT = "/analizy-i-tseny/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ru-RU,ru;q=0.9"}

_price_re = re.compile(r"(\d[\d\s\xa0]*)\s*₽")

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


def parse_list_items(html):
    soup = BeautifulSoup(html, "lxml")
    out = []
    for item in soup.select(".medicine__item"):
        link = item.select_one("a[href]")
        price_el = item.select_one(".medicine__price")
        if not link or not price_el:
            continue
        m = _price_re.search(price_el.get_text())
        if not m:
            continue
        name = link.get_text(" ", strip=True)
        slug = link.get("href", "").split("?")[0]
        price = int(re.sub(r"\D", "", m.group(1)))
        if name and slug:
            out.append({"name": name, "slug": slug, "price": price})
    return out


def parse_product_page(html):
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.select_one("h1")
    if not h1:
        return None
    name = h1.get_text(" ", strip=True)
    price_el = soup.select_one(".analysis-total-price-new")
    if not price_el:
        price_el = soup.select_one(".block-sale-price")
    if not price_el:
        return None
    m = _price_re.search(price_el.get_text())
    if not m:
        return None
    price = int(re.sub(r"\D", "", m.group(1)))
    return {"name": name, "price": price}


def category_links(html):
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.select(f'a[href*="{ROOT}"]'):
        href = a.get("href", "").split("?")[0].split("#")[0]
        if href.startswith(ROOT) and href != ROOT:
            links.add(href)
    return links


def crawl(max_pages=600, delay=0.35, verbose=True):
    seen, queue = set(), [ROOT]
    products = {}
    pages_done = 0

    while queue and pages_done < max_pages:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)
        html = get(BASE + path)
        pages_done += 1
        if not html:
            continue

        items = parse_list_items(html)
        if items:
            for c in items:
                slug = c["slug"]
                if slug not in products or c["price"] < products[slug]["price"]:
                    products[slug] = {"name": c["name"], "price": c["price"], "src": path}
        else:
            result = parse_product_page(html)
            if result:
                products[path] = {"name": result["name"], "price": result["price"], "src": path}

        for link in category_links(html):
            if link not in seen:
                queue.append(link)

        if verbose and pages_done % 20 == 0:
            print(f"  ...{pages_done} стр, товаров {len(products)}, очередь {len(queue)}")
        time.sleep(delay)

    return products, pages_done


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    print(f"LabQuest: обход каталога (лимит {limit} стр)...")
    products, pages = crawl(max_pages=limit)
    print(f"Готово: {pages} страниц, {len(products)} уникальных анализов.")
    json.dump(products, open("parser/raw_labquest.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("Сохранено -> parser/raw_labquest.json")
    for slug, p in list(products.items())[:15]:
        print(f"  {p['price']:>6} ₽  {p['name']}")
