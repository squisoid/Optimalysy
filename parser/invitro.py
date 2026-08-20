# -*- coding: utf-8 -*-
"""
Скрейпер каталога Инвитро (Москва) через JSON API.
Эндпоинт: /golk/tests/api/v1/tests?cityID=...&limit=N&offset=M
Отдаёт title, price, code, category_name, keywords.
"""
import re, json, sys, io, time
import requests

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "https://www.invitro.ru"
API = "/golk/tests/api/v1/tests"
CITY_ID = "f1c3c4f0-3426-4cda-8449-e5d326e02f97"  # Москва
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ru-RU,ru;q=0.9"}

session = requests.Session()
session.headers.update(UA)


def fetch_page(offset, limit=100):
    url = f"{BASE}{API}?cityID={CITY_ID}&limit={limit}&offset={offset}"
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                return r.json()
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 * (attempt + 1))
    return None


def crawl(verbose=True):
    offset = 0
    limit = 100
    products = {}
    total = None

    while True:
        data = fetch_page(offset, limit)
        if not data:
            if verbose:
                print(f"  ! ошибка на offset={offset}")
            break

        if total is None:
            total = data.get("total", 0)
            if verbose:
                print(f"  Всего анализов в API: {total}")

        for cat in data.get("data", []):
            for prod in cat.get("products", []):
                code = prod.get("code", "")
                if not code:
                    continue
                slug = f"/analizes/for-doctors/{code}/"
                products[slug] = {
                    "name": prod.get("title", ""),
                    "price": prod.get("price", 0),
                    "code": code,
                    "category": cat.get("category_name", ""),
                    "src": "api"
                }

        items_in_page = sum(len(c.get("products", [])) for c in data.get("data", []))
        offset += limit
        if verbose and offset % 500 == 0:
            print(f"  ...offset {offset}, собрано {len(products)}")

        if items_in_page == 0 or (total and offset >= total):
            break
        time.sleep(0.2)

    return products


if __name__ == "__main__":
    print("Инвитро: загрузка каталога через API...")
    products = crawl()
    print(f"Готово: {len(products)} уникальных анализов.")
    json.dump(products, open("parser/raw_invitro.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("Сохранено -> parser/raw_invitro.json")
    for slug, p in list(products.items())[:15]:
        print(f"  {p['price']:>6} ₽  [{p['code']:>6}]  {p['name'][:60]}")
