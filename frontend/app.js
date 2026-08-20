// Optimalysy — frontend application
const API = "";

// ── State ──
let allAnalytes = [];
let lastSearchResults = [];
let selected = new Map(); // id -> analyte object
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
    const res = await fetch(`${API}/api/analytes`);
    allAnalytes = await res.json();
  } catch (e) {
    console.error("Failed to load analytes:", e);
  }
  bindEvents();
}

// ── Events ──
function bindEvents() {
  $input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    $clear.classList.toggle("visible", $input.value.length > 0);
    debounceTimer = setTimeout(() => searchAnalytes($input.value), 120);
  });

  $input.addEventListener("focus", () => {
    if ($input.value.trim()) searchAnalytes($input.value);
  });

  $input.addEventListener("keydown", e => {
    const items = $dropdown.querySelectorAll(".dd-item:not(.selected)");
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

  $clear.addEventListener("click", () => {
    $input.value = "";
    $clear.classList.remove("visible");
    closeDropdown();
    $input.focus();
  });

  $calcBtn.addEventListener("click", runOptimization);

  $dropdown.addEventListener("click", e => {
    const item = e.target.closest(".dd-item:not(.selected)");
    if (item) selectAnalyte(item.dataset.id);
  });

  $clearAll.addEventListener("click", () => {
    selected.clear();
    renderChips();
    $results.innerHTML = "";
    $input.focus();
  });

  document.addEventListener("click", e => {
    if (!e.target.closest(".search-section")) closeDropdown();
  });

  document.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && selected.size > 0) {
      e.preventDefault();
      runOptimization();
    }
  });
}

// ── Search & Dropdown ──
async function searchAnalytes(query) {
  const q = query.trim();
  if (!q) { closeDropdown(); return; }

  try {
    const res = await fetch(`${API}/api/analytes?q=${encodeURIComponent(q)}`);
    const items = await res.json();
    lastSearchResults = items;
    renderDropdown(items, q);
  } catch (e) {
    console.error("Search error:", e);
  }
}

function renderDropdown(items, query) {
  if (!items.length) {
    $dropdown.innerHTML = `<div class="dd-empty">Ничего не найдено по «${esc(query)}»</div>`;
    $dropdown.classList.add("open");
    ddIndex = -1;
    return;
  }

  const qLow = query.toLowerCase();
  $dropdown.innerHTML = items.map(a => {
    const isSel = selected.has(a.id);
    const name = highlightMatch(a.name, qLow);
    const prices = Object.values(a.prices);
    const priceMin = prices.length ? Math.min(...prices) : null;
    const priceMax = prices.length ? Math.max(...prices) : null;
    const priceStr = priceMin != null
      ? (priceMin === priceMax ? rub(priceMin) : `${rub(priceMin)}–${rub(priceMax)}`)
      : "";

    return `<div class="dd-item${isSel ? " selected" : ""}" data-id="${esc(a.id)}">
      <span class="name">${name}</span>
      <span class="labs-count">${a.lab_count} лаб.</span>
      <span class="price-range">${priceStr}</span>
    </div>`;
  }).join("");

  $dropdown.classList.add("open");
  ddIndex = -1;
}

function highlightMatch(name, query) {
  const idx = name.toLowerCase().indexOf(query);
  if (idx === -1) return esc(name);
  const before = name.slice(0, idx);
  const match  = name.slice(idx, idx + query.length);
  const after  = name.slice(idx + query.length);
  return esc(before) + `<em>${esc(match)}</em>` + esc(after);
}

function updateDDActive(items) {
  items.forEach((el, i) => el.classList.toggle("active", i === ddIndex));
  if (items[ddIndex]) items[ddIndex].scrollIntoView({ block: "nearest" });
}

function closeDropdown() {
  $dropdown.classList.remove("open");
  ddIndex = -1;
}

// ── Selection ──
function selectAnalyte(id) {
  const analyte = allAnalytes.find(a => a.id === id)
    || lastSearchResults.find(a => a.id === id);
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
  const count = selected.size;
  $selArea.style.display = count > 0 ? "block" : "none";
  $calcBtn.disabled = count === 0;
  $selCount.textContent = `Выбрано: ${count}`;

  $chips.innerHTML = "";
  for (const [id, a] of selected) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.innerHTML = `${a.note && a.note.startsWith("⚠") ? '<span class="warn-icon">⚠️</span>' : ""}` +
      `${esc(a.name)}` +
      `<button class="chip-remove" title="Убрать">&times;</button>`;
    chip.querySelector(".chip-remove").addEventListener("click", () => removeAnalyte(id));
    $chips.appendChild(chip);
  }
}

// ── Optimization ──
async function runOptimization() {
  if (selected.size === 0) return;

  closeDropdown();
  $calcBtn.disabled = true;
  $results.innerHTML = `<div class="loading results-enter">
    <div class="spinner"></div>
    <span class="loading-text">Считаем оптимальный план...</span>
  </div>`;

  try {
    const res = await fetch(`${API}/api/optimize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analyte_ids: [...selected.keys()] }),
    });
    const data = await res.json();
    if (data.error) {
      $results.innerHTML = `<div class="card results-enter"><p style="color:var(--danger)">Ошибка: ${esc(data.error)}</p></div>`;
      return;
    }
    renderResults(data);
  } catch (e) {
    $results.innerHTML = `<div class="card results-enter"><p style="color:var(--danger)">Не удалось подключиться к серверу</p></div>`;
    console.error("Optimization error:", e);
  } finally {
    $calcBtn.disabled = false;
  }
}

// ── Render results ──
function renderResults(data) {
  const { winner, winner_lab, ranking, mix, delta, upgrades, required } = data;

  let html = "";

  // 1. Winner banner
  const coverageText = winner.uncovered.length === 0
    ? "полное покрытие вашего заказа"
    : `покрыто ${required.length - winner.uncovered.length} из ${required.length}`;

  html += `<div class="winner-banner results-enter">
    <div class="winner-info">
      <div class="winner-label">Лучший вариант</div>
      <div class="winner-lab">${esc(winner_lab)}</div>
      <div class="winner-detail">${coverageText}</div>
    </div>
    <div class="winner-price-block">
      <div class="winner-price">${rub(winner.total)}</div>
      <div class="winner-price-sub">с учётом забора крови</div>
    </div>
  </div>`;

  // 2. Lab ranking table
  html += `<section class="card results-enter">
    <div class="card-title">Сравнение лабораторий · в одной лаборатории</div>
    <div class="table-wrap">
    <table class="ranking-table">
      <thead><tr>
        <th>Лаборатория</th>
        <th class="num">Анализы</th>
        <th class="num">Забор</th>
        <th class="num">Итого</th>
        <th class="num">Покрытие</th>
      </tr></thead>
      <tbody>`;

  ranking.forEach((r, i) => {
    const isLeader = i === 0;
    const pillClass = r.full_coverage ? "pill-full"
      : r.uncovered_count < required.length ? "pill-partial" : "pill-none";
    const pillText = r.full_coverage ? "полное"
      : r.uncovered_count >= required.length ? "—" : `нет ${r.uncovered_count}`;

    html += `<tr class="${isLeader ? "leader" : ""}">
      <td><div class="lab-name-cell"><span class="lab-rank">${i + 1}</span> ${esc(r.lab)}</div></td>
      <td class="num">${rub(r.items_cost)}</td>
      <td class="num">${rub(r.fee)}</td>
      <td class="num">${rub(r.total)}</td>
      <td class="num"><span class="pill ${pillClass}">${pillText}</span></td>
    </tr>`;
  });

  html += `</tbody></table></div></section>`;

  // 3. Winner detail plan
  html += `<section class="card results-enter">
    <div class="card-title">Детали лучшего плана · ${esc(winner_lab)}</div>
    ${renderPlan(winner)}
  </section>`;

  // 4. Mix comparison
  html += `<section class="card results-enter">
    <div class="card-title">Разбивка по лабораториям</div>`;

  if (mix && delta > 1) {
    html += renderPlan(mix);
    html += `<div class="callout" style="margin-top:16px">
      Одна лаборатория (${esc(winner_lab)}) = <b>${rub(winner.total)}</b>.
      Разбивка = <b>${rub(mix.total)}</b> — экономия <b>${rub(delta)}</b>,
      но это ${mix.labs_used.length} визита вместо одного.
    </div>`;
  } else {
    html += `<div class="callout">Разбивка по лабораториям не даёт экономии.
      Лучший вариант — <b>${esc(winner_lab)}</b> за <b>${rub(winner.total)}</b>.</div>`;
  }
  html += `</section>`;

  // 5. Upgrades
  html += `<section class="card results-enter">
    <div class="card-title">🎁 Апгрейды за копейки</div>`;
  if (!upgrades.length) {
    html += `<p style="color:var(--muted);font-size:14px">Подходящих комплексов-апгрейдов
      в лаборатории-победителе нет. Выгодные комплексы уже учтены в плане выше.</p>`;
  } else {
    for (const u of upgrades) {
      html += `<div class="upgrade-item">
        <div class="ug-head">«${esc(u.complex_name)}»</div>
        <div class="ug-price">Доплата ${rub(u.surcharge)} <span style="color:var(--faint)">[${esc(u.trigger)}]</span></div>
        <div class="ug-extras">`;
      for (const b of u.bonus_analytes) {
        html += `<div>+ ${esc(b.name)}${b.price ? ` <span style="color:var(--faint)">(обычно ${rub(b.price)})</span>` : ""}</div>`;
      }
      html += `</div></div>`;
    }
  }
  html += `</section>`;

  $results.innerHTML = html;
  $results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderPlan(plan) {
  let html = `<div class="plan-section">`;

  const singles = plan.chosen.filter(b => b.kind === "single");
  const complexes = plan.chosen.filter(b => b.kind === "complex");

  for (const b of singles) {
    html += `<div class="plan-item">
      <div>
        <div class="item-name">${esc(b.label)}</div>
        <div class="item-lab">${esc(b.lab)}</div>
      </div>
      <div class="item-price">${rub(b.cost)}</div>
    </div>`;
  }

  for (const b of complexes) {
    const covers = (b.contains || []).map(c => esc(c.name)).join(", ");
    const extras = (b.extras || []).map(e => esc(e.name)).join(", ");
    html += `<div class="plan-complex">
      <div class="cx-head">
        <span>[${esc(b.lab)}] Комплекс «${esc(b.label)}»</span>
        <span>${rub(b.cost)}</span>
      </div>
      ${covers ? `<div class="cx-covers">Покрывает: ${covers}</div>` : ""}
      ${extras ? `<div class="cx-bonus">🎁 Бонусом: ${extras}</div>` : ""}
    </div>`;
  }

  html += `</div>`;

  // Uncovered
  if (plan.uncovered && plan.uncovered.length) {
    html += `<div class="uncovered-row" style="margin-top:12px">
      <span class="label">⚠️ Не покрыто</span>
      <span class="names">${plan.uncovered.map(u => esc(u.name)).join(", ")}</span>
    </div>`;
  }

  // Totals
  html += `<div class="plan-totals">
    <div class="total-row">
      <span class="total-label">Позиции</span>
      <span>${rub(plan.items_cost)}</span>
    </div>
    <div class="total-row">
      <span class="total-label">Забор крови (${plan.labs_used.map(esc).join(", ")})</span>
      <span>${rub(plan.fees_cost)}</span>
    </div>
    <div class="total-row grand">
      <span class="total-label">Итого</span>
      <span>${rub(plan.total)}</span>
    </div>
  </div>`;

  return html;
}

// ── Start ──
init();
