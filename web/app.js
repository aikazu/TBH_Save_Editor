"use strict";
const $ = (s, r = document) => r.querySelector(s);
const el = (t, c, h) => {
  const e = document.createElement(t);
  if (c) e.className = c;
  if (h != null) e.innerHTML = h;
  return e;
};

// ---------------------------------------------------------------- UI state
const STATE = { heroes: [], hero: null, item: null, dirtyCount: 0, loaded: false };

// ---------------------------------------------------------------- helpers
async function api(method, path, body) {
  const r = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || "HTTP " + r.status);
  return data;
}

function toast(msg, kind = "") {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show " + kind;
  setTimeout(() => (t.className = "toast"), 2800);
}

function iconEl(url, fallback) {
  if (url) {
    const i = el("img");
    i.src = url;
    i.alt = "";
    return i;
  }
  return el("div", "ico", fallback || "?");
}

// middle-truncate a long path for the status strip
function truncMiddle(s, max = 48) {
  if (!s || s.length <= max) return s || "";
  const head = Math.ceil((max - 1) / 2);
  const tail = Math.floor((max - 1) / 2);
  return s.slice(0, head) + "…" + s.slice(s.length - tail);
}

// grade badge class: COMMON -> r-COMMON (CSS rarity color ladder)
function gradeClass(grade) {
  return grade ? "grade r-" + grade.toUpperCase() : "grade";
}

// run an async action with a button "loading" state (also blocks double-clicks)
async function withBusy(btn, fn) {
  if (!btn || btn.disabled) return;
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Working…";
  try {
    return await fn();
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

// ----------------------------------------------------- dirty-state tracking
function setDirty(delta) {
  STATE.dirtyCount = Math.max(0, STATE.dirtyCount + delta);
  renderDirty();
}
function clearDirty() {
  STATE.dirtyCount = 0;
  renderDirty();
}
function renderDirty() {
  const pill = $("#dirtyPill");
  const txt = $("#dirtyText");
  if (STATE.dirtyCount > 0) {
    pill.className = "pill dirty";
    txt.textContent = "Unsaved · " + STATE.dirtyCount;
  } else {
    pill.className = "pill clean";
    txt.textContent = STATE.loaded ? "Saved" : "Ready";
  }
}

// ----------------------------------------------------------- load / save
async function boot() {
  const st = await api("GET", "/api/state");
  $("#savePath").value = st.path || "";
  $("#backendBadge").textContent = "AES: " + (st.aesBackend || "—");
  $("#statusPath").textContent = st.path ? truncMiddle(st.path) : "No save loaded";
  $("#statusPath").title = st.path || "";
  renderDirty();
}

async function doLoad() {
  await withBusy($("#btnLoad"), async () => {
    try {
      const data = await api("POST", "/api/load", {
        path: $("#savePath").value.trim(),
      });
      applyHeroes(data);
      $("#btnSave").disabled = false;
      STATE.loaded = true;
      clearDirty();
      toast(`Loaded · ${data.heroes.length} heroes`, "ok");
    } catch (e) {
      toast("Failed to load: " + e.message, "err");
    }
  });
}

async function doSave() {
  if (STATE.dirtyCount === 0) {
    toast("Nothing unsaved to write.", "");
    return;
  }
  if (!confirm("Write changes to the save file? A .bak backup is created first.")) return;
  await withBusy($("#btnSave"), async () => {
    try {
      const r = await api("POST", "/api/save", {});
      const fix = r.fixed ? ` · ${r.fixed} counter(s) repaired` : "";
      toast("Saved to game" + fix + " · backup created", "ok");
      clearDirty();
    } catch (e) {
      toast("Failed to save: " + e.message, "err");
    }
  });
}

function applyHeroes(data) {
  STATE.heroes = data.heroes;
  STATE.hero = null;
  STATE.item = null;
  renderHeroes();
  $("#itemGrid").innerHTML = "";
  $("#itemEmpty").style.display = "block";
  $("#itemEmpty").innerHTML = "<strong>Pick a hero</strong>Their equipped items will appear here.";
  $("#enchBody").innerHTML = "";
  $("#enchEmpty").style.display = "block";
  $("#enchTitle").textContent = "Enchantments";
  $("#heroEmpty").style.display = STATE.heroes.length ? "none" : "block";
}

// ----------------------------------------------------------------- heroes
function renderHeroes() {
  const list = $("#heroList");
  list.innerHTML = "";
  STATE.heroes.forEach((h, idx) => {
    const d = el("div", "hero" + (STATE.hero === idx ? " sel" : ""));
    d.append(
      el("span", "nm", h.name || "Hero " + h.heroKey),
      el("span", "lv", "Lv " + h.level)
    );
    d.onclick = () => selectHero(idx);
    list.append(d);
  });
}

function selectHero(idx) {
  STATE.hero = idx;
  STATE.item = null;
  renderHeroes();
  renderItems();
  $("#enchBody").innerHTML = "";
  $("#enchEmpty").style.display = "block";
  $("#enchTitle").textContent = "Enchantments";
}

// ------------------------------------------------------------------ items
function renderItems() {
  const grid = $("#itemGrid");
  grid.innerHTML = "";
  const h = STATE.heroes[STATE.hero];
  $("#itemEmpty").style.display = h.items.length ? "none" : "block";
  h.items.forEach((it) => {
    const c = el("div", "card" + (STATE.item && STATE.item.uniqueId === it.uniqueId ? " sel" : ""));
    c.append(iconEl(it.icon, it.group || "?"));
    c.append(el("div", "nm", it.name));
    if (it.grade) c.append(el("div", gradeClass(it.grade), it.grade));
    else c.append(el("div", "grp", it.group || ""));
    c.onclick = () => selectItem(it);
    grid.append(c);
  });
}

function selectItem(it) {
  STATE.item = it;
  renderItems();
  renderEnchants();
}

// ------------------------------------------------------------- enchantments
function renderEnchants() {
  const it = STATE.item;
  const body = $("#enchBody");
  $("#enchEmpty").style.display = "none";
  $("#enchTitle").textContent =
    it.name + (it.grade ? "  ·  " + it.grade : "") + (it.group ? "  ·  " + it.group : "");
  body.innerHTML = "";
  it.enchants.forEach((e) => body.append(slotCard(e)));
}

function slotCard(e) {
  const s = el("div", "slot" + (e.allowed ? "" : " locked"));
  s.dataset.type = e.type;
  const head = el("div", "head");
  head.append(el("span", "tag " + e.type, e.label));
  const cur = el("div", "cur");
  if (!e.allowed) {
    cur.innerHTML = `<i>Unavailable — this item's grade has no such slot.</i>`;
  } else if (e.filled) {
    const unit = e.isPercent ? "%" : "";
    cur.innerHTML =
      `<b>${e.materialName}</b> — <span class="stat">${e.stat}</span> ` +
      `<span class="tier">T${e.tier}</span> · <span class="v">${e.value}${unit}</span>`;
    if (e.errors && e.errors.length) cur.append(el("div", "err", "⚠ " + e.errors.join("; ")));
  } else {
    cur.innerHTML = `<i>Empty</i>`;
  }
  head.append(cur);
  s.append(head);

  if (e.allowed) {
    const actions = el("div", "actions");
    const edit = el("button", "", e.filled ? "Edit" : "Add");
    edit.onclick = () => openEditor(s, e);
    actions.append(edit);
    if (e.filled) {
      const clr = el("button", "linkbtn", "Clear");
      clr.onclick = () => setEnchant({ uniqueId: STATE.item.uniqueId, slot: e.slot, clear: true });
      actions.append(clr);
    }
    s.append(actions);
  }
  return s;
}

// inline editor for one slot — stat-first (material auto-resolved server-side)
async function openEditor(slotEl, e) {
  slotEl.querySelectorAll(".editor").forEach((x) => x.remove());
  const box = el("div", "editor");

  const onKey = (ev) => {
    if (ev.key === "Escape") {
      close();
    }
  };
  const close = () => {
    document.removeEventListener("keydown", onKey);
    box.remove();
  };
  document.addEventListener("keydown", onKey);

  // fetch the stat-first options once: every stat, every tier (union across materials)
  let options = [];
  try {
    const data = await api("GET", `/api/stat_first?item=${STATE.item.itemKey}&slot=${e.slot}`);
    options = data.options;
  } catch (err) {
    box.append(el("div", "err", "Failed to load options: " + err.message));
    slotEl.append(box);
    return;
  }

  // 1) Stat
  const rowStat = el("div", "row", `<label>Stat</label>`);
  const selStat = el("select");
  selStat.append(new Option("— choose —", ""));
  options.forEach((o, i) => selStat.append(new Option(o.statName, i)));
  rowStat.append(selStat);
  // 2) Tier (union of all tiers across materials for the chosen stat)
  const rowTier = el("div", "row", `<label>Tier</label>`);
  const selTier = el("select");
  rowTier.append(selTier);
  // 3) Value (defaults to MAX; material is carried silently from the chosen tier)
  // In Custom Edit mode the slider + Max button are hidden and the number field
  // is unbounded (no min/max/step) so any value can be forced into the slot.
  const isCustom = $("#cbCustom").checked;
  const rowVal = el("div", "row");
  rowVal.append(el("label", null, "Value"));
  const valWrap = el("div", "valbox" + (isCustom ? " custom" : ""));
  const rng = el("input");
  rng.type = "range";
  const num = el("input", "num");
  num.type = "number";
  const maxBtn = el("button", "", "Max");
  if (isCustom) {
    valWrap.append(num);
  } else {
    valWrap.append(rng, num, maxBtn);
  }
  rowVal.append(valWrap);
  const hint = el("div", "hint");
  box.append(rowStat, rowTier, rowVal, hint);

  if (!options.length) {
    selStat.disabled = true;
    hint.textContent = "This slot grants no stats for this gear type.";
  }

  // pre-select the slot's current stat/tier when editing a filled slot
  if (e.filled) {
    const k = options.findIndex((o) => o.statModKey === e.statModKey);
    if (k >= 0) selStat.value = String(k);
  }

  function onStat() {
    selTier.innerHTML = "";
    const o = options[selStat.value];
    if (!o) {
      hint.textContent = "";
      return;
    }
    o.tiers.forEach((t) => selTier.append(new Option("Tier " + t.tier, t.tier)));
    // Editing a filled slot: keep its current tier when still valid.
    // Picking a new stat: auto-select the HIGHEST tier (bottom of the list).
    const keepTier = e.filled && String(e.tier) !== "" &&
      o.tiers.some((t) => String(t.tier) === String(e.tier));
    selTier.value = keepTier ? String(e.tier) : String(o.tiers[o.tiers.length - 1].tier);
    onTier();
  }
  function onTier() {
    const o = options[selStat.value];
    if (!o) return;
    const t = o.tiers.find((x) => String(x.tier) === String(selTier.value)) || o.tiers[o.tiers.length - 1];
    if (isCustom) {
      // No bounds: leave the field free. Seed with the slot's current value when
      // editing, otherwise the tier MAX as a sensible starting point.
      num.min = num.max = num.step = "";
      const v = e.filled ? e.value : t.max;
      num.value = v;
      const unit = o.isPercent ? "%" : "";
      hint.textContent = `⚠ Custom mode — no validation. ${o.statName} · T${t.tier} · nominal range ${t.min}${unit}–${t.max}${unit}`;
    } else {
      rng.min = num.min = t.min;
      rng.max = num.max = t.max;
      rng.step = num.step = t.interval || 1;
      // Editing a filled slot: keep its value when inside range; otherwise default to MAX.
      const v = e.filled && e.value >= t.min && e.value <= t.max ? e.value : t.max;
      rng.value = num.value = v;
      const unit = o.isPercent ? "%" : "";
      hint.textContent = `${o.statName} · T${t.tier} · range ${t.min}${unit}–${t.max}${unit} (step ${t.interval})`;
    }
  }
  selStat.onchange = onStat;
  selTier.onchange = onTier;
  if (!isCustom) {
    rng.oninput = () => (num.value = rng.value);
    num.oninput = () => (rng.value = num.value);
    maxBtn.onclick = () => {
      num.value = rng.value = rng.max;
    };
  }

  const apply = el("button", "primary", "Apply");
  apply.onclick = () => {
    const o = options[selStat.value];
    if (!o) return toast("Choose a stat first.", "err");
    const t = o.tiers.find((x) => String(x.tier) === String(selTier.value)) || o.tiers[o.tiers.length - 1];
    setEnchant(
      {
        uniqueId: STATE.item.uniqueId,
        slot: e.slot,
        materialKey: t.materialKey,
        statModKey: t.statModKey,
        tier: +selTier.value,
        value: +num.value,
        force: isCustom,
      },
      close
    );
  };
  const cancel = el("button", "linkbtn", "Cancel");
  cancel.onclick = close;
  const act = el("div", "actions");
  act.append(apply, cancel);
  box.append(act);

  slotEl.append(box);
  if (e.filled) onStat();
}

async function setEnchant(payload, onDone) {
  const wasClear = !!payload.clear;
  try {
    const item = await api("POST", "/api/set_enchant", payload);
    const h = STATE.heroes[STATE.hero];
    const idx = h.items.findIndex((x) => x.uniqueId === item.uniqueId);
    if (idx >= 0) h.items[idx] = item;
    STATE.item = item;
    renderItems();
    renderEnchants();
    setDirty(1);
    toast(wasClear ? "Slot cleared" : "Enchantment applied", "ok");
    if (onDone) onDone();
  } catch (e) {
    toast("Error: " + e.message, "err");
  }
}

// --------------------------------------------------------------- bindings
$("#btnLoad").onclick = doLoad;
$("#btnSave").onclick = doSave;
$("#savePath").addEventListener("keydown", (e) => {
  if (e.key === "Enter") doLoad();
});
// Custom Edit mode toggle: warn the user before bypassing game-table validation.
$("#cbCustom").onchange = function () {
  if (this.checked) {
    const ok = confirm(
      "⚠️ Custom Edit Mode\n\n" +
      "This DISABLES game-table validation. Any value you enter will be " +
      "written directly to the save (still using display scale).\n\n" +
      "Slots edited while this mode is active may produce enchantments that " +
      "are NOT legit according to the game — risk of rejection or ban is yours.\n\n" +
      "Continue?"
    );
    if (!ok) {
      this.checked = false;
      this.closest(".custom-toggle").classList.remove("on");
      return;
    }
    this.closest(".custom-toggle").classList.add("on");
  } else {
    this.closest(".custom-toggle").classList.remove("on");
  }
};
boot();
