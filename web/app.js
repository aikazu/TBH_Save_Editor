"use strict";
const $ = (selector, root = document) => root.querySelector(selector);
const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
};
const STATE = { heroes: [], hero: null, item: null, loaded: false, busy: false, path: "", changes: new Map(), editorToken: 0 };
const format = (value) => Number(value).toLocaleString("en-US", { maximumFractionDigits: 8 });
const titleCase = (value) => value ? value[0] + value.slice(1).toLowerCase() : "Unknown";
const changeKey = (uid, slot) => `${uid}:${slot}`;

async function api(method, path, body) {
  let response;
  try {
    response = await fetch(path, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new Error("The editor server is unavailable. Start server.py and try again.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}
function notice(message, kind = "") {
  const node = $("#notice");
  node.textContent = message;
  node.className = `notice ${kind}`;
  node.hidden = !message;
}
function renderStatus() {
  const count = STATE.changes.size;
  $("#dirtyText").textContent = count ? `${count} unsaved ${count === 1 ? "slot" : "slots"}` : STATE.loaded ? "All changes saved" : "No save loaded";
  $("#dirtyText").className = count ? "dirty" : "";
  $("#btnSave").disabled = !count || STATE.busy;
  $("#btnSave").textContent = count ? `Review & save (${count})` : "Review & save";
}
async function busy(button, label, work) {
  if (STATE.busy) return;
  const previous = button?.textContent;
  STATE.busy = true;
  $("#workbench").inert = true;
  $("#savePath").disabled = true;
  $("#btnLoad").disabled = true;
  if (button) { button.disabled = true; button.textContent = label; }
  renderStatus();
  try { return await work(); }
  finally {
    STATE.busy = false;
    $("#workbench").inert = false;
    $("#savePath").disabled = false;
    $("#btnLoad").disabled = false;
    if (button?.isConnected) { button.disabled = false; button.textContent = previous; }
    renderStatus();
  }
}
function confirmAction({ title, description, accept, cancel = "Cancel", eyebrow = "Confirm action", body }) {
  const dialog = $("#confirmDialog");
  $("#dialogTitle").textContent = title;
  $("#dialogDescription").textContent = description;
  $("#dialogEyebrow").textContent = eyebrow;
  $("#dialogAccept").textContent = accept;
  $("#dialogCancel").textContent = cancel;
  $("#dialogBody").replaceChildren();
  if (body) $("#dialogBody").append(body);
  dialog.returnValue = "";
  return new Promise((resolve) => {
    dialog.onclose = () => resolve(dialog.returnValue === "accept");
    dialog.showModal();
    $("#dialogCancel").focus();
  });
}
$("#dialogAccept").onclick = () => $("#confirmDialog").close("accept");
$("#dialogCancel").onclick = $("#dialogClose").onclick = () => $("#confirmDialog").close("cancel");

function icon(url, className = "item-icon") {
  if (!url) return el("span", "slot-number", "?");
  const image = el("img", className);
  image.src = url;
  image.alt = "";
  image.width = image.height = className === "material-icon" ? 36 : 48;
  return image;
}
function grade(item) { return el("span", `grade grade-${item.grade || "COMMON"}`, titleCase(item.grade)); }
function closeEditor() {
  STATE.editorToken += 1;
  $(".editor")?.remove();
  document.querySelectorAll("[data-edit-slot]").forEach((button) => button.setAttribute("aria-expanded", "false"));
}
function empty(node, heading, text) {
  node.replaceChildren(el("strong", "", heading), el("p", "", text));
  node.hidden = false;
}

async function loadSave() {
  if (STATE.busy) return;
  if (STATE.changes.size && !await confirmAction({ title: "Discard staged changes?", description: "Loading a save replaces the unsaved changes in this workbench. Your file has not been changed.", accept: "Discard & load", cancel: "Keep editing" })) return;
  await busy($("#btnLoad"), "Loading…", async () => {
    notice("Reading and decrypting your save…");
    try {
      const data = await api("POST", "/api/load", { path: $("#savePath").value.trim() });
      closeEditor();
      STATE.heroes = data.heroes;
      STATE.path = data.path;
      STATE.loaded = true;
      STATE.changes.clear();
      STATE.hero = data.heroes.findIndex((hero) => hero.items.length);
      if (STATE.hero < 0) STATE.hero = data.heroes.length ? 0 : null;
      STATE.item = STATE.heroes[STATE.hero]?.items[0] || null;
      $("#itemSearch").value = "";
      $("#savePath").value = data.path;
      $("#statusPath").textContent = data.path;
      $("#versionLabel").textContent = `Tables ${data.dataVersion} · Save ${data.saveVersion}`;
      $("#versionWarning").hidden = data.dataVersion === data.saveVersion;
      $("#versionWarning").textContent = `This save is version ${data.saveVersion}; the editor tables are ${data.dataVersion}. Enchant options may differ.`;
      renderHeroes(); renderItems(); renderEnchants();
      notice(`Loaded ${data.heroes.length} heroes. Select equipment to begin.`, "success");
    } catch (error) { notice(error.message, "error"); }
  });
}
function renderHeroes() {
  const list = $("#heroList");
  list.replaceChildren();
  $("#heroEmpty").hidden = STATE.heroes.length > 0;
  if (STATE.loaded && !STATE.heroes.length) $("#heroEmpty").textContent = "This save has no heroes yet.";
  $("#heroCount").textContent = STATE.loaded ? STATE.heroes.length : "";
  STATE.heroes.forEach((hero, index) => {
    const button = el("button", "hero-button");
    button.type = "button";
    button.setAttribute("aria-pressed", String(STATE.hero === index));
    const copy = el("span");
    copy.append(el("strong", "", hero.name), el("small", "", `Level ${hero.level}`));
    button.append(copy, el("span", "hero-index", `${hero.items.length} gear`));
    button.onclick = () => {
      if (STATE.busy) return;
      closeEditor(); STATE.hero = index; STATE.item = hero.items[0] || null;
      $("#itemSearch").value = "";
      renderHeroes(); renderItems(); renderEnchants();
      $(`#heroList button:nth-child(${index + 1})`)?.focus({ preventScroll: true });
    };
    list.append(button);
  });
}
function renderItems() {
  const list = $("#itemGrid");
  list.replaceChildren();
  const hero = STATE.heroes[STATE.hero];
  $("#heroSummary").hidden = !hero;
  $("#itemTools").hidden = !hero?.items.length;
  $("#itemCount").textContent = hero ? hero.items.length : "";
  if (!hero) return empty($("#itemEmpty"), "Choose your hero", "Their equipped items will appear here.");
  $("#heroSummary").replaceChildren(document.createTextNode(hero.name), el("span", "", `Level ${hero.level} · ${hero.items.length} equipped items`));
  if (!hero.items.length) return empty($("#itemEmpty"), "No equipment yet", `${hero.name} has no equipped items in this save. Choose another hero.`);
  const query = $("#itemSearch").value.trim().toLowerCase();
  const items = hero.items.filter((item) => `${item.name} ${item.grade} ${item.group}`.toLowerCase().includes(query));
  $("#itemEmpty").hidden = items.length > 0;
  if (!items.length) empty($("#itemEmpty"), "No matching equipment", "Try a different name or rarity.");
  items.forEach((item) => {
    const button = el("button", "item-button");
    button.type = "button"; button.dataset.item = item.uniqueId;
    button.setAttribute("aria-pressed", String(STATE.item?.uniqueId === item.uniqueId));
    const copy = el("span", "item-copy");
    copy.append(el("span", "item-name", item.name));
    const meta = el("span", "item-meta"); meta.append(grade(item), el("span", "", titleCase(item.group)));
    copy.append(meta);
    if ([...STATE.changes.values()].some((change) => change.uid === item.uniqueId)) copy.append(el("span", "edited-label", "Edited"));
    button.append(icon(item.icon), copy);
    button.onclick = () => {
      if (STATE.busy) return;
      closeEditor(); STATE.item = item; renderItems(); renderEnchants();
      [...list.children].find((child) => child.dataset.item === item.uniqueId)?.focus({ preventScroll: true });
      if (matchMedia("(max-width: 649px)").matches) $("#enchPane").scrollIntoView({ block: "start", behavior: "instant" });
    };
    list.append(button);
  });
}
function renderEnchants() {
  closeEditor();
  const item = STATE.item;
  $("#enchBody").replaceChildren();
  $("#enchEmpty").hidden = !!item;
  $("#selectedItem").hidden = !item;
  $("#advanced").hidden = !item;
  $("#slotCount").textContent = item ? `${item.enchants.filter((slot) => slot.allowed && slot.filled).length} / ${item.enchants.filter((slot) => slot.allowed).length} filled` : "";
  if (!item) return;
  const detail = el("div");
  detail.append(el("span", "selected-caption", `${STATE.heroes[STATE.hero].name}'s equipment`), el("h3", "", item.name));
  const meta = el("div", "item-meta"); meta.append(grade(item), el("span", "", titleCase(item.group))); detail.append(meta);
  $("#selectedItem").replaceChildren(icon(item.icon), detail);
  ["Decoration", "Engraving", "Inscription"].forEach((label, groupIndex) => {
    const section = el("section", "enchant-group");
    const slots = item.enchants.slice(groupIndex * 2, groupIndex * 2 + 2);
    const head = el("div", "group-heading");
    head.append(el("h3", "", label), el("span", "", `${slots.filter((slot) => slot.allowed).length} available`));
    section.append(head);
    slots.forEach((slot) => section.append(slotRow(slot)));
    $("#enchBody").append(section);
  });
}
function slotRow(slot) {
  const changed = STATE.changes.has(changeKey(STATE.item.uniqueId, slot.slot));
  const row = el("div", `slot${slot.allowed ? "" : " locked"}${changed ? " changed" : ""}`);
  row.dataset.slot = slot.slot;
  const summary = el("div", "slot-summary");
  summary.append(slot.filled ? icon(slot.materialIcon, "material-icon") : el("span", "slot-number", slot.allowed ? String(slot.slot % 2 + 1) : "–"));
  const copy = el("div", "slot-copy");
  copy.append(el("div", "slot-stat", slot.filled ? slot.stat : slot.allowed ? "Empty slot" : "Locked slot"));
  copy.append(el("span", "slot-detail", slot.filled ? `${slot.materialName} · Tier ${slot.tier}` : slot.allowed ? "Choose a stat to add an enchant." : `Unavailable for ${titleCase(STATE.item.grade)} gear.`));
  summary.append(copy);
  if (slot.filled) summary.append(el("span", "slot-value", `${format(slot.value)}${slot.isPercent ? "%" : ""}`));
  row.append(summary);
  if (slot.errors?.length) {
    // Validation messages quote raw save integers, which differ from the scaled value shown above.
    const problem = el("div", "slot-error", "This roll doesn't match the game tables.");
    problem.append(el("span", "", `Raw save value: ${slot.errors.join(". ")}`));
    row.append(problem);
  }
  if (changed) row.append(el("span", "edited-label", "Staged change"));
  if (slot.allowed || slot.filled) {
    const actions = el("div", "slot-actions");
    if (slot.allowed) {
      const edit = el("button", "secondary", slot.filled ? "Edit" : "Add");
      edit.type = "button"; edit.dataset.editSlot = slot.slot;
      edit.setAttribute("aria-label", `${slot.filled ? "Edit" : "Add"} ${slot.label.toLowerCase()} ${slot.slot % 2 + 1}`);
      edit.setAttribute("aria-expanded", "false"); edit.setAttribute("aria-controls", `editor-${slot.slot}`);
      edit.onclick = () => openEditor(row, slot, edit);
      actions.append(edit);
    }
    if (slot.filled) {
      const clear = el("button", "quiet", "Clear");
      clear.type = "button"; clear.setAttribute("aria-label", `Clear ${slot.label.toLowerCase()} ${slot.slot % 2 + 1}`);
      clear.onclick = async () => {
        if (STATE.busy) return;
        if (await confirmAction({ title: `Clear this ${slot.label.toLowerCase()}?`, description: `${STATE.item.name}: ${describeSlot(slot)}. This change will be staged until you save.`, accept: "Clear enchant", cancel: "Keep enchant" })) {
          await setEnchant({ uniqueId: STATE.item.uniqueId, slot: slot.slot, clear: true }, clear);
        }
      };
      actions.append(clear);
    }
    row.append(actions);
  }
  return row;
}

async function openEditor(row, current, trigger) {
  if (STATE.busy) return;
  closeEditor();
  const token = STATE.editorToken;
  const item = STATE.item;
  trigger.setAttribute("aria-expanded", "true");
  const form = el("form", "editor"); form.id = `editor-${current.slot}`; form.method = "post"; form.action = "/api/set_enchant";
  form.append(el("p", "range-hint", "Loading available stats…")); row.append(form);
  let options;
  try {
    options = (await api("GET", `/api/stat_first?item=${item.itemKey}&slot=${current.slot}`)).options;
  } catch (error) {
    if (token === STATE.editorToken) { form.replaceChildren(el("p", "field-error", error.message)); const retry = el("button", "secondary", "Retry"); retry.type = "button"; retry.onclick = () => openEditor(row, current, trigger); form.append(retry); }
    return;
  }
  if (token !== STATE.editorToken || !form.isConnected) return;
  form.replaceChildren();
  const custom = $("#cbCustom").checked;
  const heading = el("div", "editor-heading"); heading.append(el("strong", "", `${current.label} ${current.slot % 2 + 1}`), el("span", `editor-mode${custom ? " custom" : ""}`, custom ? "Custom values" : "Game-table values"));
  const fields = el("div", "form-fields");
  const stat = el("select"); stat.id = "editStat"; stat.name = "stat"; stat.required = true;
  stat.append(new Option("Choose a stat", "")); options.forEach((option, index) => stat.append(new Option(option.statName, String(index))));
  const tier = el("select"); tier.id = "editTier"; tier.name = "tier"; tier.required = true;
  const number = el("input"); number.type = "number"; number.inputMode = "decimal"; number.id = "editValue"; number.name = "value"; number.required = true;
  const range = el("input"); range.type = "range"; range.id = "editRange"; range.setAttribute("aria-label", "Enchantment value slider");
  const max = el("button", "secondary", "Max"); max.type = "button";
  const hint = el("p", "range-hint"); hint.id = "rangeHint";
  const error = el("p", "field-error"); error.id = "editError"; error.setAttribute("role", "alert");
  number.setAttribute("aria-describedby", "rangeHint editError");
  const field = (text, input, className = "") => { const wrap = el("div", className); const label = el("label", "", text); label.htmlFor = input.id; wrap.append(label, input); return wrap; };
  fields.append(field("Stat", stat), field("Tier", tier));
  const valueField = el("div", "field-value"); const valueLabel = el("label", "", "Value"); valueLabel.htmlFor = number.id;
  const valueControls = el("div", "value-controls");
  if (!custom) valueControls.append(range);
  valueControls.append(number);
  if (!custom) valueControls.append(max);
  valueField.append(valueLabel, valueControls); fields.append(valueField);
  const actions = el("div", "editor-actions"); const cancel = el("button", "quiet", "Cancel"); cancel.type = "button";
  const apply = el("button", "primary", "Apply enchant"); apply.type = "submit";
  actions.append(cancel, apply); form.append(heading, fields, hint, error, actions);
  const currentIndex = options.findIndex((option) => option.tiers.some((candidate) => candidate.statModKey === current.statModKey));
  const selection = () => { const option = options[stat.value]; return { option, chosen: option?.tiers.find((candidate) => String(candidate.tier) === tier.value) }; };
  function updateTier(keepCurrent = false) {
    const { option, chosen } = selection();
    const active = !!chosen;
    number.disabled = range.disabled = max.disabled = !active;
    error.textContent = "";
    if (!active) { number.value = ""; hint.textContent = "Choose a stat to see its available tiers and values."; return; }
    const suffix = option.isPercent ? "%" : "";
    valueLabel.textContent = option.isPercent ? "Value (%)" : "Value";
    if (custom) { number.removeAttribute("min"); number.removeAttribute("max"); number.step = "any"; }
    else {
      number.min = range.min = chosen.min; number.max = range.max = chosen.max; number.step = range.step = chosen.interval || "any";
    }
    const value = keepCurrent && current.filled && chosen.statModKey === current.statModKey && chosen.tier === current.tier ? current.value : chosen.max;
    number.value = range.value = value;
    hint.textContent = `${custom ? "Outside-table values allowed. " : ""}Range ${format(chosen.min)}${suffix} to ${format(chosen.max)}${suffix} · step ${format(chosen.interval)}${suffix}`;
  }
  function updateStat(keepCurrent = false) {
    tier.replaceChildren();
    const option = options[stat.value];
    tier.disabled = !option;
    if (option) {
      option.tiers.forEach((candidate) => tier.append(new Option(`Tier ${candidate.tier}`, String(candidate.tier))));
      tier.value = String(keepCurrent && option.tiers.some((candidate) => candidate.tier === current.tier) ? current.tier : option.tiers.at(-1).tier);
    }
    updateTier(keepCurrent);
  }
  stat.onchange = () => updateStat(); tier.onchange = () => updateTier();
  number.oninput = () => { error.textContent = ""; if (number.value !== "") range.value = number.value; };
  range.oninput = () => { number.value = range.value; error.textContent = ""; };
  max.onclick = () => { number.value = range.value = selection().chosen.max; error.textContent = ""; };
  cancel.onclick = () => { closeEditor(); trigger.focus(); };
  form.addEventListener("keydown", (event) => { if (event.key === "Escape") { event.preventDefault(); closeEditor(); trigger.focus(); } });
  form.onsubmit = async (event) => {
    event.preventDefault(); if (STATE.busy || !form.reportValidity()) return;
    const { chosen } = selection(); if (!chosen) return;
    const preserveMaterial = current.filled && current.identityValid && chosen.statModKey === current.statModKey && chosen.tier === current.tier;
    await setEnchant({ uniqueId: item.uniqueId, slot: current.slot, materialKey: preserveMaterial ? current.materialKey : chosen.materialKey, statModKey: chosen.statModKey, tier: chosen.tier, value: number.value, force: custom }, apply, error);
  };
  if (current.filled && currentIndex >= 0) stat.value = String(currentIndex);
  updateStat(true);
  if (!options.length) { stat.disabled = true; apply.disabled = true; hint.textContent = "No enchant options are available for this item."; }
  stat.focus({ preventScroll: true });
}
async function setEnchant(payload, button, errorNode) {
  const original = STATE.item.enchants[payload.slot];
  const heroName = STATE.heroes[STATE.hero].name;
  let applied = false;
  await busy(button, "Applying…", async () => {
    try {
      const item = await api("POST", "/api/set_enchant", payload);
      applied = true;
      const updated = item.enchants[payload.slot];
      if (JSON.stringify(original) === JSON.stringify(updated)) {
        closeEditor(); notice("This enchant is unchanged."); return;
      }
      const key = changeKey(item.uniqueId, payload.slot);
      STATE.changes.set(key, { uid: item.uniqueId, hero: heroName, itemName: item.name, label: `${updated.label} ${payload.slot % 2 + 1}`, before: STATE.changes.get(key)?.before || original, after: updated, custom: !!payload.force });
      STATE.heroes.forEach((hero) => { hero.items = hero.items.map((entry) => entry.uniqueId === item.uniqueId ? item : entry); });
      STATE.item = item; renderItems(); renderEnchants();
      notice(payload.clear ? "Enchantment cleared. Review and save when ready." : "Enchantment staged. Review and save when ready.", "success");
    } catch (error) {
      if (errorNode) errorNode.textContent = error.message;
      notice(error.message, "error");
    }
  });
  if (applied) $(`[data-edit-slot="${payload.slot}"]`)?.focus({ preventScroll: true });
  else if (errorNode) $("#editValue")?.focus({ preventScroll: true });
}
function describeSlot(slot) { return slot.filled ? `${slot.stat} · T${slot.tier} · ${format(slot.value)}${slot.isPercent ? "%" : ""} · ${slot.materialName}` : "Empty slot"; }
async function reviewSave() {
  if (STATE.busy || !STATE.changes.size) return;
  const body = el("div");
  STATE.changes.forEach((change) => {
    const entry = el("div", "review-entry");
    entry.append(el("h3", "", change.itemName), el("p", "", `${change.hero} · ${change.label}${change.custom ? " · Custom value" : ""}`));
    const values = el("div", "review-values");
    const before = el("div"); before.append(el("span", "", "Before"), document.createTextNode(describeSlot(change.before)));
    const after = el("div", "review-after"); after.append(el("span", "", "After"), document.createTextNode(describeSlot(change.after)));
    values.append(before, after); entry.append(values);
    if (JSON.stringify(change.before) === JSON.stringify(change.after)) entry.append(el("p", "muted", "The roll is restored; its applied-enchant counter still records these edits."));
    if (change.after.errors?.length) entry.append(el("p", "field-error", change.after.errors.join(". ")));
    body.append(entry);
  });
  const risk = el("div", "review-risk");
  const custom = [...STATE.changes.values()].some((change) => change.custom);
  risk.append(el("strong", "", "Checked on your device only"), el("span", "", `${custom ? "Some values are outside the game's tables and are more likely to be rejected." : "These values match the game's tables."} The game also validates some items on its servers. It may reject edited items or flag your account.`));
  const path = el("div", "review-path"); path.append(el("strong", "", "Write to"), document.createTextNode(STATE.path)); body.append(risk, path);
  if (!await confirmAction({ title: "Review your changes", eyebrow: `${STATE.changes.size} staged ${STATE.changes.size === 1 ? "slot" : "slots"}`, description: "Close the game before saving. Your current file is first copied to a new dated .bak file next to it. The oldest backup and the two newest are kept.", accept: "Save with backup", cancel: "Keep editing", body })) return;
  await busy($("#btnSave"), "Saving…", async () => {
    notice("Writing your save and creating a backup…");
    try {
      const result = await api("POST", "/api/save", {});
      STATE.changes.clear(); renderItems(); renderEnchants();
      notice(`Saved. Your previous file is backed up at ${result.backup}${result.fixed ? ` · ${result.fixed} enchant counters repaired.` : ""}`, "success");
    } catch (error) { notice(error.message, "error"); }
  });
}
$("#loadForm").onsubmit = (event) => { event.preventDefault(); loadSave(); };
$("#btnSave").onclick = reviewSave;
$("#itemSearch").oninput = renderItems;
$("#cbCustom").onchange = async (event) => {
  const checkbox = event.target;
  if (checkbox.checked) checkbox.checked = await confirmAction({ title: "Allow custom values?", description: "Custom values skip range validation. The game may reject these rolls. Your save is only written after review and confirmation.", accept: "Enable custom values", cancel: "Use game-table values", eyebrow: "Advanced editing" });
  renderEnchants();
};
window.addEventListener("beforeunload", (event) => { if (STATE.changes.size) { event.preventDefault(); event.returnValue = ""; } });
async function boot() {
  try {
    const state = await api("GET", "/api/state");
    $("#savePath").value = state.path || "";
    $("#versionLabel").textContent = `Game tables ${state.dataVersion}`;
  } catch (error) { notice(error.message, "error"); }
  renderStatus();
}
boot();
