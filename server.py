# -*- coding: utf-8 -*-
"""FastAPI-сервер Optimalysy: API оптимизации + раздача фронтенда."""
from __future__ import annotations
import json
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from optimizer import DataSet, solve_single_lab, solve_mix, find_upgrades_P, _name

ROOT = Path(__file__).parent
DS = DataSet.load(str(ROOT / "data_full.json"))

app = FastAPI(title="Optimalysy API")


# ──────────────────── Models ────────────────────

class OptimizeRequest(BaseModel):
    analyte_ids: list[str]


# ──────────────────── API routes ────────────────────

@app.get("/api/analytes")
def list_analytes(q: str = Query("", max_length=120)):
    """Поиск аналитов для автокомплита. Пустой q — все."""
    q_low = q.lower().strip()
    results = []
    for a in DS.analytes:
        name_low = a.name.lower()
        syns = " ".join(s.lower() for s in a.synonyms)
        if q_low and q_low not in name_low and q_low not in syns and q_low not in a.id:
            continue
        prices = {}
        for lab in DS.labs:
            p = DS.price(a.id, lab)
            if p is not None:
                prices[lab] = p
        results.append({
            "id": a.id,
            "name": a.name,
            "note": a.note,
            "fraction": a.fraction,
            "synonyms": a.synonyms,
            "prices": prices,
            "lab_count": len(prices),
        })
    if q_low:
        results.sort(key=lambda r: (
            0 if r["name"].lower().startswith(q_low) else 1,
            -r["lab_count"],
            r["name"],
        ))
    return results[:80]


@app.get("/api/labs")
def list_labs():
    return [{"name": lab, "fee": DS.fees.get(lab, 0)} for lab in DS.labs]


@app.post("/api/optimize")
def optimize(req: OptimizeRequest):
    required = req.analyte_ids
    if not required:
        return {"error": "empty"}

    valid = [a.id for a in DS.analytes]
    required = [r for r in required if r in valid]
    if not required:
        return {"error": "no_valid_analytes"}

    singles = solve_single_lab(DS, required)
    mix = solve_mix(DS, required)

    ranked = sorted(singles.items(),
                    key=lambda kv: (len(kv[1].uncovered), kv[1].total))
    winner_lab, winner = ranked[0]

    ups = find_upgrades_P(DS, required, winner_lab, winner.items_cost)

    def plan_to_dict(plan):
        return {
            "labs_used": plan.labs_used,
            "items_cost": plan.items_cost,
            "fees_cost": plan.fees_cost,
            "total": plan.total,
            "uncovered": [{"id": a, "name": _name(DS, a)} for a in plan.uncovered],
            "chosen": [{
                "label": b.label,
                "kind": b.kind,
                "lab": b.lab,
                "cost": b.cost,
                "contains": _complex_contents(b) if b.kind == "complex" else None,
                "extras": _complex_extras(b, required) if b.kind == "complex" else None,
            } for b in plan.chosen],
        }

    ranking = []
    for lab, plan in ranked:
        ranking.append({
            "lab": lab,
            "total": plan.total,
            "items_cost": plan.items_cost,
            "fee": DS.fees.get(lab, 0),
            "uncovered_count": len(plan.uncovered),
            "full_coverage": len(plan.uncovered) == 0,
        })

    upgrade_list = [{
        "complex_name": u.complex_name,
        "lab": u.lab,
        "surcharge": u.surcharge,
        "trigger": u.trigger,
        "bonus_analytes": [{"name": n, "price": p} for n, p in u.bonus_analytes],
    } for u in ups]

    delta = winner.total - mix.total if mix else 0

    return {
        "required": [{"id": a, "name": _name(DS, a)} for a in required],
        "winner": plan_to_dict(winner),
        "winner_lab": winner_lab,
        "ranking": ranking,
        "mix": plan_to_dict(mix) if mix else None,
        "delta": delta,
        "upgrades": upgrade_list,
        "labs": DS.labs,
    }


def _complex_contents(bundle):
    for c in DS.complexes:
        if c.name == bundle.label and c.lab == bundle.lab:
            return [{"id": a, "name": _name(DS, a)} for a in c.contains]
    return []


def _complex_extras(bundle, required):
    req_set = set(required)
    for c in DS.complexes:
        if c.name == bundle.label and c.lab == bundle.lab:
            return [{"id": a, "name": _name(DS, a)} for a in c.contains if a not in req_set]
    return []


# ──────────────────── Static frontend ────────────────────

@app.get("/")
def index():
    return FileResponse(ROOT / "frontend" / "index.html")


app.mount("/static", StaticFiles(directory=str(ROOT / "frontend")), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
