// Optimalysy — fully static frontend with client-side optimizer
(function() {
"use strict";

// ── State ──
let DATA = null;       // loaded dataset
let priceIndex = {};   // {lab: {analyte_id: price}}
let selected = new Map();
let lastSearchResults = [];
let ddIndex = -1;
let debounceTimer = null;

// ── DOM ──
const $input    = document.getElementById("searchInput");
const $clear    = document.getElementById("searchClear");
const $dropdown = document.getElementById("dropdown");
const $chips    = document.getElementById("chips");
const $selArea  = document.getElementById("selectedArea");
const $selCount = document.getElementById("selectedCount");
const $calcBtn  = document.getElementById("calcBtn");
const $results  = document.getElementById("results");
const $clearAll = document.getElementById("clearAll");

// ── Helpers ──
const rub = n => Math.round(n).toLocaleString("ru-RU") + " ₽";
const esc = s => s.replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]));

// ── Init ──
async function init() {
  try {
    const res = await fetch("data.json");
    const raw = await res.json();
    DATA = raw;
    buildPriceIndex();
  } catch (e) {
    console.error("Failed to load data:", e);
    $results.innerHTML = '<div class="card"><p style="color:var(--danger)">Не удалось загрузить данные</p></div>';
    return;
  }
  bindEvents();
}

function buildPriceIndex() {
  priceIndex = {};
  for (const lab of DATA.labs) priceIndex[lab] = {};
  for (const o of DATA.offerings) {
    if (o.present && o.price != null) {
      priceIndex[o.lab][o.analyte] = o.price;
    }
  }
}

function getPrice(analyte, lab) {
  return priceIndex[lab] && priceIndex[lab][analyte] != null ? priceIndex[lab][analyte] : null;
}

function analyteName(id) {
  const a = DATA.analytes.find(a => a.id === id);
  return a ? a.name : id;
}

// ── Events ──
function bindEvents() {
  $input.addEventListener("input", function() {
    clearTimeout(debounceTimer);
    $clear.classList.toggle("visible", $input.value.length > 0);
    debounceTimer = setTimeout(function() { searchAnalytes($input.value); }, 120);
  });

  $input.addEventListener("focus", function() {
    if ($input.value.trim()) searchAnalytes($input.value);
  });

  $input.addEventListener("keydown", function(e) {
    var items = $dropdown.querySelectorAll(".dd-item:not(.selected)");
    if (e.key === "ArrowDown") {
      e.preventDefault();
      ddIndex = Math.min(ddIndex + 1, items.length - 1);
      updateDDActive(items);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      ddIndex = Math.max(ddIndex - 1, 0);
      updateDDActive(items);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (ddIndex >= 0 && items[ddIndex]) {
        selectAnalyte(items[ddIndex].dataset.id);
      } else if ((e.ctrlKey || e.metaKey) && selected.size > 0) {
        runOptimization();
      }
    } else if (e.key === "Escape") {
      closeDropdown();
    }
  });

  $clear.addEventListener("click", function() {
    $input.value = "";
    $clear.classList.remove("visible");
    closeDropdown();
    $input.focus();
  });

  $calcBtn.addEventListener("click", runOptimization);

  $clearAll.addEventListener("click", function() {
    selected.clear();
    renderChips();
    $results.innerHTML = "";
    $input.focus();
  });

  document.addEventListener("click", function(e) {
    if (!e.target.closest(".search-section")) closeDropdown();
  });

  document.addEventListener("keydown", function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && selected.size > 0) {
      e.preventDefault();
      runOptimization();
    }
  });
}

// ── Search (client-side) ──
function searchAnalytes(query) {
  var q = query.trim().toLowerCase();
  if (!q) { closeDropdown(); return; }

  var results = [];
  for (var i = 0; i < DATA.analytes.length; i++) {
    var a = DATA.analytes[i];
    var nameLow = a.name.toLowerCase();
    var syns = (a.synonyms || []).join(" ").toLowerCase();
    if (q.length > 0 && nameLow.indexOf(q) === -1 && syns.indexOf(q) === -1) continue;

    var prices = {};
    var labCount = 0;
    for (var j = 0; j < DATA.labs.length; j++) {
      var lab = DATA.labs[j];
      var p = getPrice(a.id, lab);
      if (p != null) { prices[lab] = p; labCount++; }
    }
    if (labCount === 0) continue;

    results.push({
      id: a.id, name: a.name, note: a.note || "",
      fraction: a.fraction || "", synonyms: a.synonyms || [],
      prices: prices, lab_count: labCount
    });
  }

  results.sort(function(a, b) {
    var aStart = a.name.toLowerCase().indexOf(q) === 0 ? 0 : 1;
    var bStart = b.name.toLowerCase().indexOf(q) === 0 ? 0 : 1;
    if (aStart !== bStart) return aStart - bStart;
    if (b.lab_count !== a.lab_count) return b.lab_count - a.lab_count;
    return a.name.localeCompare(b.name);
  });

  lastSearchResults = results.slice(0, 80);
  renderDropdown(lastSearchResults, q);
}

function renderDropdown(items, query) {
  if (!items.length) {
    $dropdown.innerHTML = '<div class="dd-empty">Ничего не найдено по «' + esc(query) + '»</div>';
    $dropdown.classList.add("open");
    ddIndex = -1;
    return;
  }

  var html = "";
  for (var i = 0; i < items.length; i++) {
    var a = items[i];
    var isSel = selected.has(a.id);
    var name = highlightMatch(a.name, query);
    var prices = Object.values(a.prices);
    var priceMin = Math.min.apply(null, prices);
    var priceMax = Math.max.apply(null, prices);
    var priceStr = priceMin === priceMax ? rub(priceMin) : rub(priceMin) + "–" + rub(priceMax);

    html += '<div class="dd-item' + (isSel ? " selected" : "") + '" data-id="' + esc(a.id) + '">'
      + '<span class="name">' + name + '</span>'
      + '<span class="labs-count">' + a.lab_count + ' лаб.</span>'
      + '<span class="price-range">' + priceStr + '</span>'
      + '</div>';
  }

  $dropdown.innerHTML = html;
  $dropdown.classList.add("open");
  ddIndex = -1;

  $dropdown.querySelectorAll(".dd-item:not(.selected)").forEach(function(el) {
    el.addEventListener("click", function() { selectAnalyte(el.dataset.id); });
  });
}

function highlightMatch(name, query) {
  var idx = name.toLowerCase().indexOf(query);
  if (idx === -1) return esc(name);
  return esc(name.slice(0, idx)) + '<em>' + esc(name.slice(idx, idx + query.length)) + '</em>' + esc(name.slice(idx + query.length));
}

function updateDDActive(items) {
  items.forEach(function(el, i) { el.classList.toggle("active", i === ddIndex); });
  if (items[ddIndex]) items[ddIndex].scrollIntoView({ block: "nearest" });
}

function closeDropdown() {
  $dropdown.classList.remove("open");
  ddIndex = -1;
}

// ── Selection ──
function selectAnalyte(id) {
  var analyte = lastSearchResults.find(function(a) { return a.id === id; });
  if (!analyte || selected.has(id)) return;
  selected.set(id, analyte);
  renderChips();
  $input.value = "";
  $clear.classList.remove("visible");
  closeDropdown();
  $input.focus();
}

function removeAnalyte(id) {
  selected.delete(id);
  renderChips();
}

function renderChips() {
  var count = selected.size;
  $selArea.style.display = count > 0 ? "block" : "none";
  $calcBtn.disabled = count === 0;
  $selCount.textContent = "Выбрано: " + count;

  $chips.innerHTML = "";
  selected.forEach(function(a, id) {
    var chip = document.createElement("span");
    chip.className = "chip";
    chip.innerHTML = (a.note && a.note.charAt(0) === "⚠" ? '<span class="warn-icon">⚠️</span>' : "")
      + esc(a.name)
      + '<button class="chip-remove" title="Убрать">&times;</button>';
    chip.querySelector(".chip-remove").addEventListener("click", function() { removeAnalyte(id); });
    $chips.appendChild(chip);
  });
}

// ══════════════════════════════════════════════════════════════
// OPTIMIZER — weighted set cover via DP on bitmasks (client-side)
// ══════════════════════════════════════════════════════════════

function bundlesForLab(lab, required, index) {
  var reqSet = new Set(required);
  var out = [];
  for (var i = 0; i < required.length; i++) {
    var a = required[i];
    var p = getPrice(a, lab);
    if (p != null) out.push({ cost: p, covers: 1 << index[a], label: analyteName(a), kind: "single", lab: lab });
  }
  var complexes = DATA.complexes || [];
  for (var c = 0; c < complexes.length; c++) {
    var cx = complexes[c];
    if (cx.lab !== lab) continue;
    var mask = 0, any = false;
    for (var j = 0; j < cx.contains.length; j++) {
      if (reqSet.has(cx.contains[j])) { mask |= 1 << index[cx.contains[j]]; any = true; }
    }
    if (any) out.push({ cost: cx.price, covers: mask, label: cx.name, kind: "complex", lab: lab,
      _contains: cx.contains });
  }
  return out;
}

function dpCover(bundles, full) {
  var best = new Map();
  best.set(0, { cost: 0, chosen: [] });
  var pq = [[0, 0, []]];

  while (pq.length) {
    var bi = 0;
    for (var i = 1; i < pq.length; i++) if (pq[i][0] < pq[bi][0]) bi = i;
    var item = pq.splice(bi, 1)[0];
    var cost = item[0], mask = item[1], chosen = item[2];

    if (best.has(mask) && best.get(mask).cost < cost - 1e-9) continue;
    if (mask === full) return { cost: cost, chosen: chosen, cov: full };

    for (var b = 0; b < bundles.length; b++) {
      var bundle = bundles[b];
      var nm = mask | bundle.covers;
      if (nm === mask) continue;
      var nc = cost + bundle.cost;
      if (!best.has(nm) || nc < best.get(nm).cost - 1e-9) {
        var ch = chosen.concat([bundle]);
        best.set(nm, { cost: nc, chosen: ch });
        pq.push([nc, nm, ch]);
      }
    }
  }

  var popcount = function(x) { var c = 0; while (x) { c += x & 1; x >>= 1; } return c; };
  var bm = 0;
  best.forEach(function(v, m) {
    if (popcount(m) > popcount(bm) || (popcount(m) === popcount(bm) && v.cost < best.get(bm).cost)) bm = m;
  });
  return { cost: best.get(bm).cost, chosen: best.get(bm).chosen, cov: bm };
}

function solveSingle(required) {
  var index = {};
  required.forEach(function(a, i) { index[a] = i; });
  var full = (1 << required.length) - 1;
  var res = {};

  for (var li = 0; li < DATA.labs.length; li++) {
    var lab = DATA.labs[li];
    var b = bundlesForLab(lab, required, index);
    if (!b.length) {
      res[lab] = { lab: lab, items: 0, fee: DATA.fees[lab] || 0, total: DATA.fees[lab] || 0,
        chosen: [], uncovered: required.map(function(a) { return { id: a, name: analyteName(a) }; }), labs_used: [lab] };
      continue;
    }
    var r = dpCover(b, full);
    var fee = DATA.fees[lab] || 0;
    var uncovered = [];
    for (var i = 0; i < required.length; i++) {
      if (!((r.cov >> i) & 1)) uncovered.push({ id: required[i], name: analyteName(required[i]) });
    }
    res[lab] = { lab: lab, items: r.cost, fee: fee, total: r.cost + fee, chosen: r.chosen, uncovered: uncovered, labs_used: [lab] };
  }
  return res;
}

function solveMix(required) {
  var index = {};
  required.forEach(function(a, i) { index[a] = i; });
  var full = (1 << required.length) - 1;
  var best = null;
  var labs = DATA.labs;
  var L = labs.length;

  for (var s = 1; s < (1 << L); s++) {
    var bundles = [];
    for (var i = 0; i < L; i++) {
      if ((s >> i) & 1) bundles = bundles.concat(bundlesForLab(labs[i], required, index));
    }
    if (!bundles.length) continue;
    var r = dpCover(bundles, full);
    if (r.cov !== full) continue;
    var usedSet = {};
    r.chosen.forEach(function(b) { usedSet[b.lab] = true; });
    var used = Object.keys(usedSet);
    var fee = 0;
    used.forEach(function(l) { fee += DATA.fees[l] || 0; });
    var total = r.cost + fee;
    if (!best || total < best.total - 1e-9) {
      best = { items: r.cost, fee: fee, total: total, chosen: r.chosen, labs_used: used,
        uncovered: [] };
    }
  }
  return best;
}

function findUpgrades(required, winnerLab, baselineItems) {
  var reqSet = new Set(required);
  var ups = [];
  var complexes = DATA.complexes || [];

  for (var c = 0; c < complexes.length; c++) {
    var cx = complexes[c];
    if (cx.lab !== winnerLab) continue;
    var allCovered = true;
    for (var i = 0; i < required.length; i++) {
      if (cx.contains.indexOf(required[i]) === -1) { allCovered = false; break; }
    }
    if (!allCovered) continue;
    var surcharge = cx.price - baselineItems;
    if (surcharge <= 0) continue;
    var extras = cx.contains.filter(function(a) { return !reqSet.has(a); });
    if (!extras.length) continue;
    var named = extras.map(function(a) { return { name: analyteName(a), price: getPrice(a, winnerLab) }; });
    var pctOk = surcharge <= 0.10 * baselineItems;
    var maxE = Math.max.apply(null, named.map(function(n) { return n.price || 0; }).concat([0]));
    var ratioOk = maxE >= 2 * surcharge;
    if (pctOk || ratioOk) {
      ups.push({ complex_name: cx.name, lab: winnerLab, surcharge: surcharge,
        trigger: pctOk ? "≤10%" : "≥2×", bonus_analytes: named });
    }
  }
  ups.sort(function(a, b) { return a.surcharge - b.surcharge; });
  return ups;
}

// ── Run optimization ──
function runOptimization() {
  if (selected.size === 0) return;
  closeDropdown();
  $calcBtn.disabled = true;

  $results.innerHTML = '<div class="loading results-enter"><div class="spinner"></div>'
    + '<span class="loading-text">Считаем оптимальный план...</span></div>';

  setTimeout(function() {
    try {
      var required = Array.from(selected.keys());
      var singles = solveSingle(required);
      var mix = solveMix(required);

      var ranked = Object.keys(singles).map(function(k) { return singles[k]; });
      ranked.sort(function(a, b) { return (a.uncovered.length - b.uncovered.length) || (a.total - b.total); });
      var winner = ranked[0];
      var winnerLab = winner.lab;

      var ups = findUpgrades(required, winnerLab, winner.items);
      var delta = mix ? winner.total - mix.total : 0;

      var data = {
        required: required.map(function(a) { return { id: a, name: analyteName(a) }; }),
        winner: winner,
        winner_lab: winnerLab,
        ranking: ranked.map(function(p, i) {
          return { lab: p.lab, total: p.total, items_cost: p.items, fee: p.fee,
            uncovered_count: p.uncovered.length, full_coverage: p.uncovered.length === 0 };
        }),
        mix: mix,
        delta: delta,
        upgrades: ups
      };
      renderResults(data);
    } catch (e) {
      console.error("Optimization error:", e);
      $results.innerHTML = '<div class="card results-enter"><p style="color:var(--danger)">Ошибка оптимизации: ' + esc(e.message) + '</p></div>';
    } finally {
      $calcBtn.disabled = false;
    }
  }, 50);
}

// ── Render results ──
function renderResults(data) {
  var winner = data.winner, winnerLab = data.winner_lab, ranking = data.ranking;
  var mix = data.mix, delta = data.delta, upgrades = data.upgrades, required = data.required;

  var html = "";

  var coverageText = winner.uncovered.length === 0
    ? "полное покрытие вашего заказа"
    : "покрыто " + (required.length - winner.uncovered.length) + " из " + required.length;

  html += '<div class="winner-banner results-enter">'
    + '<div class="winner-info"><div class="winner-label">Лучший вариант</div>'
    + '<div class="winner-lab">' + esc(winnerLab) + '</div>'
    + '<div class="winner-detail">' + coverageText + '</div></div>'
    + '<div class="winner-price-block"><div class="winner-price">' + rub(winner.total) + '</div>'
    + '<div class="winner-price-sub">с учётом забора крови</div></div></div>';

  html += '<section class="card results-enter"><div class="card-title">Сравнение лабораторий · в одной лаборатории</div>'
    + '<div class="table-wrap"><table class="ranking-table"><thead><tr>'
    + '<th>Лаборатория</th><th class="num">Анализы</th><th class="num">Забор</th>'
    + '<th class="num">Итого</th><th class="num">Покрытие</th></tr></thead><tbody>';

  for (var i = 0; i < ranking.length; i++) {
    var r = ranking[i];
    var isLeader = i === 0;
    var pillClass = r.full_coverage ? "pill-full" : r.uncovered_count < required.length ? "pill-partial" : "pill-none";
    var pillText = r.full_coverage ? "полное" : r.uncovered_count >= required.length ? "—" : "нет " + r.uncovered_count;
    html += '<tr class="' + (isLeader ? "leader" : "") + '">'
      + '<td><div class="lab-name-cell"><span class="lab-rank">' + (i + 1) + '</span> ' + esc(r.lab) + '</div></td>'
      + '<td class="num">' + rub(r.items_cost) + '</td>'
      + '<td class="num">' + rub(r.fee) + '</td>'
      + '<td class="num">' + rub(r.total) + '</td>'
      + '<td class="num"><span class="pill ' + pillClass + '">' + pillText + '</span></td></tr>';
  }
  html += '</tbody></table></div></section>';

  html += '<section class="card results-enter"><div class="card-title">Детали лучшего плана · ' + esc(winnerLab) + '</div>'
    + renderPlan(winner) + '</section>';

  html += '<section class="card results-enter"><div class="card-title">Разбивка по лабораториям</div>';
  if (mix && delta > 1) {
    html += renderPlan(mix);
    html += '<div class="callout" style="margin-top:16px">'
      + 'Одна лаборатория (' + esc(winnerLab) + ') = <b>' + rub(winner.total) + '</b>. '
      + 'Разбивка = <b>' + rub(mix.total) + '</b> — экономия <b>' + rub(delta) + '</b>, '
      + 'но это ' + mix.labs_used.length + ' визита вместо одного.</div>';
  } else {
    html += '<div class="callout">Разбивка по лабораториям не даёт экономии. '
      + 'Лучший вариант — <b>' + esc(winnerLab) + '</b> за <b>' + rub(winner.total) + '</b>.</div>';
  }
  html += '</section>';

  html += '<section class="card results-enter"><div class="card-title">🎁 Апгрейды за копейки</div>';
  if (!upgrades.length) {
    html += '<p style="color:var(--muted);font-size:14px">Подходящих комплексов-апгрейдов '
      + 'в лаборатории-победителе нет. Выгодные комплексы уже учтены в плане выше.</p>';
  } else {
    for (var u = 0; u < upgrades.length; u++) {
      var up = upgrades[u];
      html += '<div class="upgrade-item"><div class="ug-head">«' + esc(up.complex_name) + '»</div>'
        + '<div class="ug-price">Доплата ' + rub(up.surcharge) + ' <span style="color:var(--faint)">[' + esc(up.trigger) + ']</span></div>'
        + '<div class="ug-extras">';
      for (var bi = 0; bi < up.bonus_analytes.length; bi++) {
        var ba = up.bonus_analytes[bi];
        html += '<div>+ ' + esc(ba.name) + (ba.price ? ' <span style="color:var(--faint)">(обычно ' + rub(ba.price) + ')</span>' : '') + '</div>';
      }
      html += '</div></div>';
    }
  }
  html += '</section>';

  $results.innerHTML = html;
  $results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderPlan(plan) {
  var html = '<div class="plan-section">';
  var singles = plan.chosen.filter(function(b) { return b.kind === "single"; });
  var complexes = plan.chosen.filter(function(b) { return b.kind === "complex"; });

  for (var i = 0; i < singles.length; i++) {
    var b = singles[i];
    html += '<div class="plan-item"><div><div class="item-name">' + esc(b.label) + '</div>'
      + '<div class="item-lab">' + esc(b.lab) + '</div></div>'
      + '<div class="item-price">' + rub(b.cost) + '</div></div>';
  }

  for (var i = 0; i < complexes.length; i++) {
    var b = complexes[i];
    var reqSet = new Set(Array.from(selected.keys()));
    var covers = (b._contains || []).filter(function(a) { return reqSet.has(a); }).map(function(a) { return esc(analyteName(a)); }).join(", ");
    var extras = (b._contains || []).filter(function(a) { return !reqSet.has(a); }).map(function(a) { return esc(analyteName(a)); }).join(", ");

    html += '<div class="plan-complex"><div class="cx-head">'
      + '<span>[' + esc(b.lab) + '] Комплекс «' + esc(b.label) + '»</span>'
      + '<span>' + rub(b.cost) + '</span></div>'
      + (covers ? '<div class="cx-covers">Покрывает: ' + covers + '</div>' : '')
      + (extras ? '<div class="cx-bonus">🎁 Бонусом: ' + extras + '</div>' : '')
      + '</div>';
  }

  html += '</div>';

  if (plan.uncovered && plan.uncovered.length) {
    html += '<div class="uncovered-row" style="margin-top:12px">'
      + '<span class="label">⚠️ Не покрыто</span>'
      + '<span class="names">' + plan.uncovered.map(function(u) { return esc(u.name); }).join(", ") + '</span></div>';
  }

  html += '<div class="plan-totals">'
    + '<div class="total-row"><span class="total-label">Позиции</span><span>' + rub(plan.items) + '</span></div>'
    + '<div class="total-row"><span class="total-label">Забор крови (' + plan.labs_used.map(esc).join(", ") + ')</span><span>' + rub(plan.fee) + '</span></div>'
    + '<div class="total-row grand"><span class="total-label">Итого</span><span>' + rub(plan.total) + '</span></div></div>';

  return html;
}

// ── Start ──
init();

})();
