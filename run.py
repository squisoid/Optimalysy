# -*- coding: utf-8 -*-
"""Прогон MVP на реальном заказе врача (Москва)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from optimizer import (DataSet, solve_single_lab, solve_mix,
                       find_upgrades_P, _name)

ds = DataSet.load("data.json")

# Заказ врача -> канонические id (дефолты: Т3/Т4 свободные, тестостерон общий)
REQUIRED = ["vit_d", "b6", "b9", "b12", "iron", "ferritin",
            "zinc", "t3", "t4", "tsh", "testosterone", "dht"]

def rub(x): return f"{x:,.0f} ₽".replace(",", " ")

def extras_of(complex_name, lab):
    for c in ds.complexes:
        if c.name == complex_name and c.lab == lab:
            return [a for a in c.contains if a not in set(REQUIRED)]
    return []

def show_plan(plan, title):
    print(f"\n  {title}")
    print(f"  {'-'*56}")
    # группируем выбранное
    for b in plan.chosen:
        if b.kind == "complex":
            covered = [_name(ds, a) for c in ds.complexes
                       if c.name == b.label and c.lab == b.lab
                       for a in c.contains if a in set(REQUIRED)]
            ex = [_name(ds, a) for a in extras_of(b.label, b.lab)]
            print(f"    [{b.lab}] КОМПЛЕКС «{b.label}» — {rub(b.cost)}")
            print(f"        покрывает: {', '.join(covered)}")
            if ex:
                print(f"        🎁 бонусом (в довесок): {', '.join(ex)}")
        else:
            print(f"    [{b.lab}] {b.label} — {rub(b.cost)}")
    print(f"  {'-'*56}")
    print(f"    Позиции:      {rub(plan.items_cost)}")
    labs = ", ".join(plan.labs_used)
    print(f"    Забор:        {rub(plan.fees_cost)}  ({labs})")
    print(f"    ИТОГО:        {rub(plan.total)}")
    if plan.uncovered:
        print(f"    ⚠️ НЕ покрыто: {', '.join(_name(ds, a) for a in plan.uncovered)}")

print("="*60)
print("  OPTIMALYSY — подбор по заказу врача. Город: Москва")
print("="*60)
print(f"\n  Заказ ({len(REQUIRED)} аналитов):")
for a in ds.analytes:
    if a.id in REQUIRED:
        mark = f"   {a.note}" if a.note.startswith("⚠️") else ""
        print(f"    • {a.name}{mark}")

# --- Single-lab по каждой лабе ---
singles = solve_single_lab(ds, REQUIRED)
print("\n" + "="*60)
print("  РЕЖИМ «В ОДНОЙ ЛАБЕ» (прямой рейс)")
print("="*60)
ranked = sorted(singles.items(),
                key=lambda kv: (len(kv[1].uncovered), kv[1].total))
for lab, plan in ranked:
    status = "полное покрытие" if not plan.uncovered else f"НЕ покрыто: {len(plan.uncovered)}"
    print(f"    {lab:10s}  {rub(plan.total):>12s}   ({status})")

winner_lab, winner = ranked[0]
show_plan(winner, f"Детали лучшего single-lab: {winner_lab}")

# --- Микс ---
mix = solve_mix(ds, REQUIRED)
print("\n" + "="*60)
print("  РЕЖИМ «САМЫЙ ДЕШЁВЫЙ» (микс, возможны пересадки)")
print("="*60)
show_plan(mix, f"Оптимальный микс: {', '.join(mix.labs_used)}")

# --- Дельта (Aviasales) ---
print("\n" + "="*60)
delta = winner.total - mix.total
if delta <= 1:
    print(f"  💡 Микс и single-lab совпали: лучший вариант — {winner_lab} за {rub(winner.total)}.")
    print(f"     Разбивка по лабам не даёт экономии (комплекс в одной лабе перебивает).")
else:
    print(f"  💡 Прямой рейс ({winner_lab}) = {rub(winner.total)}")
    print(f"     Самый дешёвый (микс) = {rub(mix.total)}  →  экономия {rub(delta)}")
    print(f"     ...но это {len(mix.labs_used)} визита вместо одного.")

# --- Бонусы beta (P): комплекс чуть дороже базы, но добирает ценное ---
# базовая линия = стоимость позиций (без забора) в лабе-победителе
baseline_items = winner.items_cost
ups = find_upgrades_P(ds, REQUIRED, winner_lab, baseline_items)
print("\n" + "="*60)
print("  🎁 АПГРЕЙДЫ ЗА КОПЕЙКИ (β): за небольшую доплату — ценное сверх заказа")
print("="*60)
if not ups:
    print("    Подходящих β-апгрейдов (один комплекс на всю корзину) в лабе-победителе нет.")
    print("    (Заказ гетерогенный: витамины+гормоны+андрология — единого профиля на всё нет.")
    print("     Зато α сработал: комплекс уже выбран внутри плана выше, лишнее — в довесок.)")
else:
    for u in ups:
        print(f"    «{u.complex_name}» ({u.lab}): доплата {rub(u.surcharge)} [{u.trigger}]")
        for nm, p in u.bonus_analytes:
            print(f"        + {nm}" + (f" (обычно {rub(p)})" if p else ""))

# --- Флаги данных ---
print("\n" + "="*60)
print("  ⚠️ ФЛАГИ ДАННЫХ (влияют на результат)")
print("="*60)
for f in ds.__dict__.get("_meta_flags", []):
    print("    •", f)
import json
for f in json.load(open("data.json", encoding="utf-8"))["_meta"]["flags"]:
    print("    •", f)
