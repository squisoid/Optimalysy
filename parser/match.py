# -*- coding: utf-8 -*-
"""
Матчер: соединяет сырые каталоги лабораторий в канонические аналиты.
Все лабы отдают кириллические названия -> join по нормализованному имени
через rapidfuzz, с защитными токенами (свободный/общий/прямой/венозная...),
чтобы не склеить разные фракции.

Поддерживает произвольное число лаб. Первая лаба — «опорная» (anchor),
остальные матчатся к ней; затем оставшиеся немэтченные анализы матчатся
друг к другу.

Вывод: data_full.json + validation_queue.json.
"""
import re, json, sys, io, os
from rapidfuzz import fuzz, process

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

GUARDS = ["свободн", "общ", "прям", "непрям", "суммарн",
          "венозн", "капилляр", "мужчин", "женщин",
          "моч", "слюн", "волос", "в кале", "соскоб", "мокрот", "ногт",
          "igm", "igg", "iga",
          "токсоплазм", "микоплазм", "хламид",
          "лпнп", "лпонп", "лпвп",
          "16/18", "31/33", "6/11",
          "гепатит а", "гепатит в", "гепатит с", "гепатит d", "гепатит е",
          "аполипопротеин а", "аполипопротеин в", "аполипопротеин b",
          "1 антител", "3 антител",
          "щитовидн", "предстательн",
          "без лейкоцит", "фемофлор"]

COMPLEX_MARK = ["комплекс", "профиль", "скрининг", "чек-ап", "чек ап", "check",
                "обследование", "панель", "программа", "диагностика ",
                "оценка ", "показател", "фракц"]

LABS = [
    {"key": "gemotest", "name": "Гемотест",  "file": "parser/raw_gemotest.json", "fee": 330},
    {"key": "kdl",      "name": "KDL",        "file": "parser/raw_kdl.json",      "fee": 199},
    {"key": "invitro",  "name": "Инвитро",    "file": "parser/raw_invitro.json",   "fee": 310},
    {"key": "helix",    "name": "Хеликс",     "file": "parser/raw_helix.json",     "fee": 285},
    {"key": "labquest", "name": "LabQuest",   "file": "parser/raw_labquest.json",  "fee": 395},
    {"key": "cmd",      "name": "CMD",        "file": "parser/raw_cmd.json",       "fee": 285},
]


def normalize(name):
    s = name.lower().replace("ё", "е")
    s = s.replace("igа", "iga").replace("igм", "igm").replace("igг", "igg")
    ig_markers = re.findall(r"\big[gamGAM]\b", s, re.IGNORECASE)
    s = re.sub(r"\([^()]*[a-zA-Z]{3,}[^()]*\)", "", s)
    for m in ig_markers:
        if m.lower() not in s:
            s = s + " " + m.lower()
    s = re.sub(r"\((венозн|капилляр)[^)]*\)", "", s)
    s = re.sub(r"\(в крови\)|\(в сыворотке\)|\(в плазме\)|\(в моче\)", "", s)
    s = re.sub(r"\(ифа\)|\(иха\)", "", s)
    s = re.sub(r",?\s*вэжх[-\s]*мс/?мс\b", "", s)
    s = re.sub(r",?\s*вэжх\b", "", s)
    s = re.sub(r",?\s*%\s*активности\b", "", s)
    s = re.sub(r",?\s*активность\s*%", "", s)
    s = re.sub(r"\b(cito|срочно|срочный)\b", "", s)
    s = re.sub(r"\s+в\s+(москве|санкт-петербурге|спб)\s*(и\s+мо)?\s*$", "", s)
    s = s.replace("д-димер", "d-димер")
    s = re.sub(r"\bпростатспецифическ", "простатическ специфическ", s)
    s = re.sub(r"anti-h\.?\s*pylori|helicobacter\s*pylori|h\.?\s*pylori", "хеликобактер пилори", s)
    s = re.sub(r"хеликобактеру(?=\s|$|[,;)])", "хеликобактер", s)
    s = re.sub(r"хеликобактера(?=\s|$|[,;)])", "хеликобактер", s)
    s = s.replace("хеликобактер пилори пилори", "хеликобактер пилори")
    if "хеликобактер" in s and "хеликобактер пилори" not in s:
        s = s.replace("хеликобактер", "хеликобактер пилори")
    s = re.sub(r"антитела к хеликобактер пилори", "хеликобактер пилори антитела", s)
    s = re.sub(r"антитела класса\s+", "", s)
    s = re.sub(r"количественн\w+\s+определение\s+антител\s+класса", "антитела", s)
    s = re.sub(r"качественн\w+\s+определение\s+", "", s)
    s = re.sub(r"определение антиген\w*\s+", "антиген ", s)
    s = re.sub(r"выявление антиген\w*\s+", "антиген ", s)
    s = re.sub(r"исследование антиген\w*\s+", "антиген ", s)
    s = re.sub(r"антигенный тест", "антиген", s)
    s = re.sub(r"антигенов(?=\s|$)", "антиген", s)
    s = re.sub(r"антиген\s+хеликобактер пилори", "хеликобактер пилори антиген", s)
    if "хеликобактер пилори антиген" in s and "в кале" not in s:
        s = s.replace("хеликобактер пилори антиген", "хеликобактер пилори антиген в кале")
    s = re.sub(r"определение днк", "днк", s)
    s = re.sub(r"13[сc]\s*[—–\-]?\s*уреазный дыхательный тест.*", "13с уреазный дыхательный тест", s)
    s = re.sub(r"[«»\"',.;:()\[\]]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def guard_set(norm):
    return frozenset(g for g in GUARDS if g in norm)


def guards_compatible(gs1, gs2):
    return gs1 == gs2


def is_complex(name):
    n = name.lower()
    n = re.sub(r"\([^()]*[a-zA-Z]{3,}[^()]*\)", "", n)
    if sum(n.count(c) for c in [",", "+", ";"]) >= 2:
        return True
    return any(m in n for m in COMPLEX_MARK)


def load(path):
    if not os.path.exists(path):
        return []
    raw = json.load(open(path, encoding="utf-8"))
    items = []
    for slug, p in raw.items():
        items.append({"slug": slug, "name": p["name"], "price": p["price"],
                      "norm": normalize(p["name"]), "complex": is_complex(p["name"])})
    return items


SYNONYMS = [
    ["25-oh витамин d", "витамин d 25-гидрокси", "витамин d 25-oh",
     "25-он витамин d", "витамин d суммарный", "витамин d витамин солнца",
     "витамин д 25-oh витамин d", "25 гидроксикальциферол"],
    ["тиреотропный гормон", "ттг", "тиротропин"],
    ["тироксин свободный", "т4 свободный"],
    ["трийодтиронин свободный", "т3 свободный"],
    ["простатический специфический антиген общий",
     "простатспецифический антиген общий", "пса общий",
     "простат-специфический антиген общий"],
    ["аланинаминотрансфераза", "аланин-аминотрансфераза"],
    ["аспартатаминотрансфераза", "аспартат-аминотрансфераза"],
    ["d-димер", "д-димер", "дедимер"],
    ["тестостерон", "тестостерон общий"],
]

_syn_map = {}
for group in SYNONYMS:
    canon = group[0]
    for syn in group[1:]:
        _syn_map[syn] = canon
_syn_map = dict(sorted(_syn_map.items(), key=lambda x: -len(x[0])))


def apply_synonyms(norm):
    for syn, canon in _syn_map.items():
        if syn in norm:
            replaced = norm.replace(syn, canon)
            if replaced != norm:
                return re.sub(r"\s+", " ", replaced).strip()
    return norm


def best_individual_per_norm(items):
    by = {}
    for it in items:
        if it["complex"]:
            continue
        k = apply_synonyms(it["norm"])
        if k not in by or it["price"] < by[k]["price"]:
            by[k] = it
    return by


def match_multi(lab_data, threshold=90):
    """
    lab_data: list of (lab_key, items)
    Returns: canon list of dicts {name, <lab_key>_price, <lab_key>_slug, ...}
             low_conf list
    """
    lab_indices = {}
    for key, items in lab_data:
        lab_indices[key] = best_individual_per_norm(items)

    all_keys = [k for k, _ in lab_data]
    if not all_keys:
        return [], []

    anchor_key = all_keys[0]
    anchor = lab_indices[anchor_key]
    other_keys = all_keys[1:]

    other_norms = {}
    for k in other_keys:
        other_norms[k] = list(lab_indices[k].keys())

    canon = []
    used = {k: set() for k in other_keys}
    low_conf = []

    def empty_entry(name):
        entry = {"name": name}
        for k in all_keys:
            entry[f"{k}_price"] = None
            entry[f"{k}_slug"] = None
        return entry

    for anorm, ait in anchor.items():
        entry = empty_entry(ait["name"])
        entry[f"{anchor_key}_price"] = ait["price"]
        entry[f"{anchor_key}_slug"] = ait["slug"]

        for k in other_keys:
            norms = other_norms[k]
            if not norms:
                continue
            candidates = process.extract(anorm, norms, scorer=fuzz.token_set_ratio, limit=5)
            for knorm, score, _ in candidates:
                if score < threshold:
                    break
                if guards_compatible(guard_set(anorm), guard_set(knorm)):
                    pair = lab_indices[k][knorm]
                    entry[f"{k}_price"] = pair["price"]
                    entry[f"{k}_slug"] = pair["slug"]
                    used[k].add(knorm)
                    if score < 96:
                        low_conf.append({
                            "anchor": ait["name"], "lab": k,
                            "matched": pair["name"], "score": score
                        })
                    break
        canon.append(entry)

    remaining = {}
    for k in other_keys:
        for knorm, kit in lab_indices[k].items():
            if knorm not in used[k]:
                if knorm not in remaining:
                    remaining[knorm] = empty_entry(kit["name"])
                remaining[knorm][f"{k}_price"] = kit["price"]
                remaining[knorm][f"{k}_slug"] = kit["slug"]

    rem_norms = list(remaining.keys())
    merged_rem = set()
    for i, n1 in enumerate(rem_norms):
        if n1 in merged_rem:
            continue
        for j in range(i + 1, len(rem_norms)):
            n2 = rem_norms[j]
            if n2 in merged_rem:
                continue
            score = fuzz.token_set_ratio(n1, n2)
            if score >= threshold and guards_compatible(guard_set(n1), guard_set(n2)):
                for k in all_keys:
                    if remaining[n1][f"{k}_price"] is None and remaining[n2][f"{k}_price"] is not None:
                        remaining[n1][f"{k}_price"] = remaining[n2][f"{k}_price"]
                        remaining[n1][f"{k}_slug"] = remaining[n2][f"{k}_slug"]
                merged_rem.add(n2)
                if score < 96:
                    low_conf.append({
                        "anchor": remaining[n1]["name"], "lab": "cross",
                        "matched": remaining[n2]["name"], "score": score
                    })

    for knorm in rem_norms:
        if knorm not in merged_rem:
            canon.append(remaining[knorm])

    return canon, low_conf


def to_dataset(canon, labs_info):
    analytes, offerings = [], []
    lab_names = [l["name"] for l in labs_info]
    fees = {l["name"]: l["fee"] for l in labs_info}

    for i, c in enumerate(canon):
        aid = f"a{i:04d}"
        analytes.append({"id": aid, "name": c["name"], "fraction": "", "synonyms": [], "note": ""})
        for l in labs_info:
            price = c.get(f"{l['key']}_price")
            if price is not None:
                offerings.append({"analyte": aid, "lab": l["name"], "present": True,
                                  "price": price, "code": ""})
    return {
        "_meta": {"city": "Москва", "source": "автопарсер (Фаза 1)",
                  "labs": lab_names,
                  "note": "Индивидуальные анализы. Составы комплексов и акции — следующий шаг."},
        "analytes": analytes, "labs": lab_names,
        "fees": fees,
        "offerings": offerings, "complexes": []
    }


if __name__ == "__main__":
    lab_data = []
    available = []
    for l in LABS:
        items = load(l["file"])
        if items:
            lab_data.append((l["key"], items))
            available.append(l)
            print(f"  {l['name']:12} {len(items):>5} позиций")
        else:
            print(f"  {l['name']:12}   --- файл не найден")

    canon, low_conf = match_multi(lab_data)

    print(f"\nКанонических аналитов: {len(canon)}")
    for l in available:
        k = l["key"]
        has = sum(1 for c in canon if c.get(f"{k}_price") is not None)
        print(f"  {l['name']:12}: {has:>5} покрыто")

    multi = sum(1 for c in canon if sum(1 for l in available if c.get(f"{l['key']}_price") is not None) >= 2)
    print(f"  в ≥2 лабах:  {multi:>5}")
    print(f"  низкая уверенность: {len(low_conf)}")

    json.dump(to_dataset(canon, available), open("data_full.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump({"low_confidence_joins": low_conf[:200]},
              open("parser/validation_queue.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nПримеры сопоставленных:")
    for c in canon[:15]:
        parts = []
        for l in available:
            k = l["key"]
            p = c.get(f"{k}_price")
            tag = l["name"][:3]
            parts.append(f"{tag} {p:>5}" if p else f"{tag}     -")
        print(f"  {c['name'][:40]:40} {'  '.join(parts)}")

    raw_data = {}
    for l in available:
        raw_data[l["key"]] = json.load(open(l["file"], encoding="utf-8"))

    import csv
    ref_rows = []
    for c in canon:
        n_labs = sum(1 for l in available if c.get(f"{l['key']}_price") is not None)
        if n_labs < 2:
            continue
        row = {"canonical": c["name"], "n_labs": n_labs}
        for l in available:
            k = l["key"]
            slug = c.get(f"{k}_slug")
            price = c.get(f"{k}_price")
            if slug and slug in raw_data[k]:
                row[f"{l['name']}_name"] = raw_data[k][slug]["name"]
                row[f"{l['name']}_price"] = price
            else:
                row[f"{l['name']}_name"] = ""
                row[f"{l['name']}_price"] = ""
        ref_rows.append(row)

    ref_rows.sort(key=lambda x: -x["n_labs"])

    lab_names = [l["name"] for l in available]
    fields = ["canonical", "n_labs"]
    for ln in lab_names:
        fields.extend([f"{ln}_name", f"{ln}_price"])

    with open("parser/reference_table.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        w.writerows(ref_rows)

    ref_json = []
    for r in ref_rows:
        entry = {"canonical": r["canonical"], "n_labs": r["n_labs"], "labs": {}}
        for ln in lab_names:
            if r.get(f"{ln}_name"):
                entry["labs"][ln] = {"name": r[f"{ln}_name"], "price": r[f"{ln}_price"]}
        ref_json.append(entry)
    json.dump(ref_json, open("parser/reference_table.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\nСправочник: {len(ref_rows)} записей -> parser/reference_table.csv, .json")
