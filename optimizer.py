"""
Optimalysy — ядро подбора оптимального набора лабораторий под корзину анализов.

Точная оптимизация: пространство крошечное (<=6 лаб x <=12 аналитов + комплексы),
поэтому считаем без эвристик — DP по битовым маскам покрытия (weighted set cover).

Целевая функция:
    minimize  Sum(цены выбранных позиций/комплексов) + Sum(забор * число задействованных лаб)

Комплексы моделируются как обычные "наборы" в задаче покрытия => если комплекс дешевле
штучного набора, DP выберет его сам (эффект alpha: лишнее достаётся "в довесок").
"""

from __future__ import annotations
from dataclasses import dataclass, field
from itertools import combinations
import json


# ------------------------------- Модель данных -------------------------------

@dataclass
class Analyte:
    id: str
    name: str
    fraction: str = ""          # free / total / "" (для Т3/Т4/тестостерона)
    synonyms: list[str] = field(default_factory=list)
    note: str = ""              # напр. "⚠️ уточните: бывают варианты"


@dataclass
class Offering:
    analyte: str                # id аналита
    lab: str
    present: bool               # покрывает / не покрывает — тоже данные
    price: float | None = None
    code: str = ""              # код на бланке (внутренний код лабы)


@dataclass
class Complex:
    lab: str
    name: str
    price: float
    contains: list[str]         # id аналитов, входящих в комплекс
    note: str = ""


@dataclass
class DataSet:
    analytes: list[Analyte]
    labs: list[str]
    fees: dict[str, float]                 # lab -> цена забора биоматериала
    offerings: list[Offering]
    complexes: list[Complex]

    # --- индексы для удобства ---
    def price(self, analyte: str, lab: str) -> float | None:
        for o in self.offerings:
            if o.analyte == analyte and o.lab == lab and o.present:
                return o.price
        return None

    def complexes_of(self, lab: str) -> list[Complex]:
        return [c for c in self.complexes if c.lab == lab]

    @staticmethod
    def load(path: str) -> "DataSet":
        raw = json.load(open(path, encoding="utf-8"))
        return DataSet(
            analytes=[Analyte(**a) for a in raw["analytes"]],
            labs=raw["labs"],
            fees=raw["fees"],
            offerings=[Offering(**o) for o in raw["offerings"]],
            complexes=[Complex(**c) for c in raw["complexes"]],
        )


# ------------------------------- Ядро покрытия -------------------------------

def _mask(items: list[str], index: dict[str, int]) -> int:
    m = 0
    for it in items:
        if it in index:
            m |= 1 << index[it]
    return m


@dataclass
class Bundle:
    """Единица покупки: штучный анализ или комплекс."""
    cost: float
    covers: int          # битовая маска покрываемых ТРЕБУЕМЫХ аналитов
    label: str
    kind: str            # "single" | "complex"
    lab: str


def _bundles_for_lab(ds: DataSet, lab: str, required: list[str],
                     index: dict[str, int]) -> list[Bundle]:
    req_set = set(required)
    bundles: list[Bundle] = []

    # штучные позиции
    for a in required:
        p = ds.price(a, lab)
        if p is not None:
            bundles.append(Bundle(p, _mask([a], index),
                                  _name(ds, a), "single", lab))

    # комплексы — покрывают пересечение своего состава с требуемым
    for c in ds.complexes_of(lab):
        covered = [a for a in c.contains if a in req_set]
        if covered:
            bundles.append(Bundle(c.price, _mask(covered, index),
                                  c.name, "complex", lab))
    return bundles


def _name(ds: DataSet, aid: str) -> str:
    for a in ds.analytes:
        if a.id == aid:
            return a.name
    return aid


def _dp_cover(bundles: list[Bundle], full: int):
    """
    Точный weighted set cover через DP по маскам.
    Возвращает (стоимость, [выбранные Bundle]) для покрытия маски full,
    либо (inf, None) если полное покрытие невозможно данными bundles.
    Также возвращает лучшую достижимую маску (для частичного покрытия).
    """
    INF = float("inf")
    best = {0: (0.0, [])}                       # mask -> (cost, chosen)
    # обрабатываем маски по возрастанию стоимости (Дейкстра по подмножествам)
    import heapq
    pq = [(0.0, 0, [])]
    seen_full = None
    while pq:
        cost, mask, chosen = heapq.heappop(pq)
        if mask in best and best[mask][0] < cost - 1e-9:
            continue
        if mask == full:
            return cost, chosen, full
        for b in bundles:
            nm = mask | b.covers
            if nm == mask:
                continue
            nc = cost + b.cost
            if nm not in best or nc < best[nm][0] - 1e-9:
                best[nm] = (nc, chosen + [b])
                heapq.heappush(pq, (nc, nm, chosen + [b]))
    # полное покрытие недостижимо — вернём лучшую по покрытию (макс бит), затем по цене
    reachable = max(best.keys(), key=lambda m: (bin(m).count("1"), -best[m][0]))
    return best[reachable][0], best[reachable][1], reachable


# ------------------------------- Результаты -------------------------------

@dataclass
class Plan:
    labs_used: list[str]
    items_cost: float
    fees_cost: float
    total: float
    chosen: list[Bundle]
    covered_mask: int
    uncovered: list[str]         # id аналитов, которые не удалось покрыть


def solve_single_lab(ds: DataSet, required: list[str]) -> dict[str, Plan]:
    """Для каждой лабы — лучший план покрытия корзины в ОДНОЙ лабе (+частичное)."""
    index = {a: i for i, a in enumerate(required)}
    full = (1 << len(required)) - 1
    out: dict[str, Plan] = {}
    for lab in ds.labs:
        bundles = _bundles_for_lab(ds, lab, required, index)
        if not bundles:
            out[lab] = Plan([lab], 0, ds.fees.get(lab, 0), ds.fees.get(lab, 0),
                            [], 0, list(required))
            continue
        cost, chosen, cov = _dp_cover(bundles, full)
        fee = ds.fees.get(lab, 0)
        uncovered = [required[i] for i in range(len(required))
                     if not (cov >> i) & 1]
        out[lab] = Plan([lab], cost, fee, cost + fee, chosen, cov, uncovered)
    return out


def solve_mix(ds: DataSet, required: list[str]) -> Plan:
    """Глобальный минимум с возможной разбивкой по лабам (забор за каждую задействованную)."""
    index = {a: i for i, a in enumerate(required)}
    full = (1 << len(required)) - 1
    best: Plan | None = None
    labs = ds.labs
    # перебор подмножеств лаб; для каждого — покрытие из bundles этих лаб + сумма заборов
    for r in range(1, len(labs) + 1):
        for subset in combinations(labs, r):
            bundles = []
            for lab in subset:
                bundles += _bundles_for_lab(ds, lab, required, index)
            if not bundles:
                continue
            cost, chosen, cov = _dp_cover(bundles, full)
            if cov != full:
                continue  # это подмножество не покрывает всё — не кандидат на полный микс
            used = sorted({b.lab for b in chosen})
            fee = sum(ds.fees.get(l, 0) for l in used)
            total = cost + fee
            if best is None or total < best.total - 1e-9:
                uncovered = []
                best = Plan(used, cost, fee, total, chosen, cov, uncovered)
    if best is None:
        # полное покрытие невозможно вообще ни при каком миксе
        bundles = []
        for lab in labs:
            bundles += _bundles_for_lab(ds, lab, required, index)
        cost, chosen, cov = _dp_cover(bundles, full)
        used = sorted({b.lab for b in chosen})
        fee = sum(ds.fees.get(l, 0) for l in used)
        uncovered = [required[i] for i in range(len(required)) if not (cov >> i) & 1]
        best = Plan(used, cost, fee, cost + fee, chosen, cov, uncovered)
    return best


# ------------------------------- Бонусы (beta) -------------------------------

@dataclass
class Upgrade:
    complex_name: str
    lab: str
    baseline: float
    upgraded_total: float
    surcharge: float
    bonus_analytes: list[tuple[str, float | None]]   # (имя, штучная цена)
    trigger: str                                      # "<=10%" | ">=2x"


def find_upgrades_P(ds: DataSet, required: list[str],
                    winner_lab: str, baseline_single: float) -> list[Upgrade]:
    """
    beta, гранулярность P: один комплекс покрывает ВСЮ корзину + лишнее.
    Только в лабе-победителе. Порог: переплата <=10% ИЛИ бонус-анализ >= 2x переплаты.
    baseline_single — стоимость позиций лабы-победителя БЕЗ забора (забор одинаков).
    """
    req_set = set(required)
    ups: list[Upgrade] = []
    for c in ds.complexes_of(winner_lab):
        if not req_set.issubset(set(c.contains)):
            continue  # должен покрывать всё требуемое целиком
        surcharge = c.price - baseline_single
        if surcharge <= 0:
            continue  # это уже alpha (комплекс дешевле) — не бонус, оптимизатор возьмёт сам
        extras = [a for a in c.contains if a not in req_set]
        if not extras:
            continue
        extra_named = [(_name(ds, a), ds.price(a, winner_lab)) for a in extras]
        # триггеры
        pct_ok = surcharge <= 0.10 * baseline_single
        max_extra_price = max([p for _, p in extra_named if p is not None], default=0)
        ratio_ok = max_extra_price >= 2 * surcharge
        if pct_ok or ratio_ok:
            ups.append(Upgrade(
                complex_name=c.name, lab=winner_lab,
                baseline=baseline_single, upgraded_total=c.price,
                surcharge=surcharge, bonus_analytes=extra_named,
                trigger="<=10%" if pct_ok else ">=2x",
            ))
    ups.sort(key=lambda u: (u.surcharge, -len(u.bonus_analytes)))
    return ups
