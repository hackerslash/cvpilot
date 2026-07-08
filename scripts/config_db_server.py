#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def validate_db(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["Root value must be a JSON object."]

    if not isinstance(payload.get("schemaVersion"), int):
        errors.append("schemaVersion must be an integer.")
    candidate = payload.get("candidate")
    if not isinstance(candidate, dict):
        errors.append("candidate must be an object.")
    elif not candidate.get("name"):
        errors.append("candidate.name is required.")

    required_arrays = [
        "sectionOrder",
        "summaries",
        "education",
        "experience",
        "projects",
        "skills",
        "awards",
    ]
    for key in required_arrays:
        if not isinstance(payload.get(key), list):
            errors.append(f"{key} must be an array.")

    seen_ids: dict[str, str] = {}
    for section in ["summaries", "education", "experience", "projects", "skills", "awards"]:
        entries = payload.get(section, [])
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"{section}[{index}] must be an object.")
                continue
            entry_id = entry.get("id")
            if not entry_id:
                errors.append(f"{section}[{index}].id is required.")
            elif entry_id in seen_ids:
                errors.append(f"Duplicate id '{entry_id}' in {section}; first seen in {seen_ids[entry_id]}.")
            else:
                seen_ids[entry_id] = section
            bullets = entry.get("bullets")
            if bullets is not None and not isinstance(bullets, list):
                errors.append(f"{section}[{index}].bullets must be an array when present.")

    return errors


def html_page() -> str:
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CVPilot DB Config</title>
  <style>
    :root {
      color-scheme: light;
      --bg: oklch(0.965 0.008 215);
      --surface: oklch(0.994 0.004 215);
      --surface-2: oklch(0.94 0.012 215);
      --ink: oklch(0.19 0.018 225);
      --muted: oklch(0.45 0.022 225);
      --line: oklch(0.84 0.018 220);
      --accent: oklch(0.49 0.11 190);
      --accent-ink: oklch(0.98 0.01 190);
      --danger: oklch(0.53 0.16 28);
      --ok: oklch(0.47 0.13 150);
      --radius: 8px;
      --space-xs: 4px;
      --space-sm: 8px;
      --space-md: 12px;
      --space-lg: 16px;
      --space-xl: 24px;
      --space-2xl: 32px;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-size: 14px;
    }

    button, input, textarea, select {
      font: inherit;
    }

    button {
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--ink);
      border-radius: 6px;
      padding: 7px 10px;
      cursor: pointer;
    }

    button:hover { border-color: color-mix(in oklch, var(--accent), var(--line) 55%); }
    button.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
    button.danger { color: var(--danger); }
    button.ghost { background: transparent; }
    button:disabled { cursor: not-allowed; opacity: .48; }

    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      color: var(--ink);
      padding: 8px 9px;
      outline: none;
    }

    textarea { min-height: 86px; resize: vertical; line-height: 1.45; }
    input:focus, textarea:focus, select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in oklch, var(--accent), transparent 80%); }
    label { display: grid; gap: var(--space-xs); color: var(--muted); font-size: 12px; font-weight: 650; }
    label span { color: var(--muted); }

    .app {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }

    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-lg);
      padding: var(--space-lg) var(--space-xl);
      background: var(--surface);
      border-bottom: 1px solid var(--line);
    }

    .brand {
      display: grid;
      gap: 2px;
    }

    h1 {
      margin: 0;
      font-size: 18px;
      line-height: 1.1;
      letter-spacing: 0;
    }

    .meta {
      color: var(--muted);
      font-size: 12px;
    }

    .toolbar {
      display: flex;
      align-items: center;
      gap: var(--space-sm);
      flex-wrap: wrap;
    }

    .status {
      min-width: 180px;
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }

    .status.ok { color: var(--ok); }
    .status.bad { color: var(--danger); }

    main {
      display: grid;
      grid-template-columns: 210px minmax(240px, 330px) 1fr;
      min-height: 0;
    }

    nav, aside, section.editor {
      min-height: 0;
      overflow: auto;
    }

    nav {
      background: var(--surface-2);
      border-right: 1px solid var(--line);
      padding: var(--space-lg);
      display: grid;
      align-content: start;
      gap: var(--space-xs);
    }

    .nav-button {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      border: 0;
      background: transparent;
      text-align: left;
      padding: 9px 10px;
      color: var(--ink);
    }

    .nav-button.active {
      background: var(--surface);
      box-shadow: inset 0 0 0 1px var(--line);
    }

    .count { color: var(--muted); font-size: 12px; }

    aside {
      background: color-mix(in oklch, var(--surface), var(--surface-2) 42%);
      border-right: 1px solid var(--line);
      padding: var(--space-lg);
      display: grid;
      grid-template-rows: auto 1fr;
      gap: var(--space-md);
    }

    .list-head, .editor-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-sm);
    }

    h2, h3 {
      margin: 0;
      letter-spacing: 0;
    }

    h2 { font-size: 15px; }
    h3 { font-size: 13px; }

    .entry-list {
      display: grid;
      gap: var(--space-sm);
      align-content: start;
    }

    .entry-button {
      width: 100%;
      text-align: left;
      display: grid;
      gap: 4px;
      padding: 10px;
    }

    .entry-button.active {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px color-mix(in oklch, var(--accent), transparent 82%);
    }

    .entry-title {
      font-weight: 700;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .entry-subtitle {
      color: var(--muted);
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .editor {
      padding: var(--space-xl);
      display: grid;
      align-content: start;
      gap: var(--space-xl);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(180px, 1fr));
      gap: var(--space-md);
    }

    .grid .full { grid-column: 1 / -1; }

    .row {
      display: flex;
      align-items: center;
      gap: var(--space-sm);
      flex-wrap: wrap;
    }

    .checks {
      display: flex;
      align-items: center;
      gap: var(--space-sm);
      color: var(--muted);
      font-weight: 650;
    }

    .checks input { width: auto; }

    .section-band {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface);
      padding: var(--space-lg);
      display: grid;
      gap: var(--space-md);
    }

    .bullet {
      display: grid;
      gap: var(--space-md);
      padding: var(--space-md);
      background: color-mix(in oklch, var(--surface-2), var(--surface) 35%);
      border: 1px solid var(--line);
      border-radius: var(--radius);
    }

    .raw {
      min-height: 52vh;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }

    .empty {
      color: var(--muted);
      padding: var(--space-xl);
      border: 1px dashed var(--line);
      border-radius: var(--radius);
      background: color-mix(in oklch, var(--surface), transparent 25%);
    }

    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; }
      nav, aside { border-right: 0; border-bottom: 1px solid var(--line); }
      nav { grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); }
      .grid { grid-template-columns: 1fr; }
      .status { text-align: left; min-width: auto; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="brand">
        <h1>CVPilot DB Config</h1>
        <div class="meta" id="dbMeta">Loading db.json</div>
      </div>
      <div class="toolbar">
        <button id="validateBtn">Validate</button>
        <button id="rawBtn">Raw JSON</button>
        <button class="primary" id="saveBtn">Save</button>
        <div class="status" id="status">Unsaved changes will appear here</div>
      </div>
    </header>
    <main>
      <nav id="nav"></nav>
      <aside>
        <div class="list-head">
          <h2 id="listTitle">Entries</h2>
          <button id="addEntryBtn">Add</button>
        </div>
        <div class="entry-list" id="entryList"></div>
      </aside>
      <section class="editor" id="editor"></section>
    </main>
  </div>

  <script>
    const SECTIONS = [
      { key: "candidate", title: "Candidate", singleton: true },
      { key: "summaries", title: "Summaries", fields: [{ key: "text", label: "Summary", type: "textarea", full: true }] },
      { key: "education", title: "Education", fields: [
        { key: "institution", label: "Institution" },
        { key: "location", label: "Location" },
        { key: "degree", label: "Degree", full: true },
        { key: "dates", label: "Dates" }
      ] },
      { key: "experience", title: "Experience", bullets: true, fields: [
        { key: "organization", label: "Organization" },
        { key: "location", label: "Location" },
        { key: "title", label: "Title" },
        { key: "dates", label: "Dates" },
        { key: "technologies", label: "Technologies", type: "list", full: true }
      ] },
      { key: "projects", title: "Projects", bullets: true, fields: [
        { key: "name", label: "Project name", full: true },
        { key: "link.label", label: "Link label" },
        { key: "link.url", label: "Link URL" },
        { key: "link.kind", label: "Link kind" },
        { key: "role", label: "Stack / Role", full: true },
        { key: "dates", label: "Dates" },
        { key: "technologies", label: "Technologies", type: "list", full: true }
      ] },
      { key: "skills", title: "Skills", fields: [
        { key: "label", label: "Label" },
        { key: "items", label: "Items", type: "list", full: true }
      ] },
      { key: "awards", title: "Awards", fields: [
        { key: "text", label: "Award / achievement", type: "textarea", full: true }
      ] },
      { key: "raw", title: "Raw JSON", singleton: true, raw: true }
    ];

    let db = null;
    let activeSection = "candidate";
    let selectedIndex = 0;
    let rawText = "";
    let dirty = false;

    const $ = (id) => document.getElementById(id);
    const configFor = (key) => SECTIONS.find((section) => section.key === key);

    function clone(value) {
      return JSON.parse(JSON.stringify(value));
    }

    function slug(value) {
      return String(value || "entry").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "entry";
    }

    function getPath(object, path) {
      return path.split(".").reduce((current, key) => current && current[key], object);
    }

    function setPath(object, path, value) {
      const parts = path.split(".");
      let current = object;
      while (parts.length > 1) {
        const key = parts.shift();
        if (!current[key] || typeof current[key] !== "object") current[key] = {};
        current = current[key];
      }
      current[parts[0]] = value;
    }

    function arrayToText(value) {
      return Array.isArray(value) ? value.join("\n") : "";
    }

    function textToArray(value) {
      return value.split(/\n|,/).map((item) => item.trim()).filter(Boolean);
    }

    function setStatus(message, kind = "") {
      $("status").textContent = message;
      $("status").className = `status ${kind}`;
    }

    function markDirty() {
      dirty = true;
      setStatus("Unsaved changes", "bad");
      renderMeta();
    }

    function renderMeta() {
      $("dbMeta").textContent = db
        ? `schemaVersion ${db.schemaVersion || "?"} · updated ${db.updatedAt || "unknown"}${dirty ? " · modified" : ""}`
        : "Loading db.json";
    }

    function renderNav() {
      $("nav").innerHTML = SECTIONS.map((section) => {
        const count = Array.isArray(db?.[section.key]) ? db[section.key].length : "";
        return `<button class="nav-button ${section.key === activeSection ? "active" : ""}" data-section="${section.key}">
          <span>${section.title}</span><span class="count">${count}</span>
        </button>`;
      }).join("");
      $("nav").querySelectorAll("button").forEach((button) => {
        button.addEventListener("click", () => {
          activeSection = button.dataset.section;
          selectedIndex = 0;
          rawText = JSON.stringify(db, null, 2);
          render();
        });
      });
    }

    function titleForEntry(sectionKey, entry) {
      if (!entry) return "Untitled";
      return entry.organization || entry.name || entry.label || entry.institution || entry.text || entry.id || "Untitled";
    }

    function subtitleForEntry(entry) {
      if (!entry) return "";
      return [entry.title || entry.role || entry.degree, entry.dates].filter(Boolean).join(" · ");
    }

    function renderList() {
      const config = configFor(activeSection);
      $("listTitle").textContent = config.title;
      $("addEntryBtn").style.display = config.singleton ? "none" : "";
      const list = $("entryList");
      if (config.singleton) {
        list.innerHTML = `<div class="empty">${config.raw ? "Edit and save the full JSON document." : "Single candidate profile."}</div>`;
        return;
      }
      const entries = db[activeSection] || [];
      if (!entries.length) {
        list.innerHTML = `<div class="empty">No entries yet.</div>`;
        return;
      }
      list.innerHTML = entries.map((entry, index) => `
        <button class="entry-button ${index === selectedIndex ? "active" : ""}" data-index="${index}">
          <span class="entry-title">${escapeHtml(titleForEntry(activeSection, entry))}</span>
          <span class="entry-subtitle">${escapeHtml(subtitleForEntry(entry) || entry.id || "")}</span>
        </button>
      `).join("");
      list.querySelectorAll("button").forEach((button) => {
        button.addEventListener("click", () => {
          selectedIndex = Number(button.dataset.index);
          render();
        });
      });
    }

    function fieldControl(entry, field) {
      const value = getPath(entry, field.key);
      const classes = field.full ? "full" : "";
      if (field.type === "textarea") {
        return `<label class="${classes}"><span>${field.label}</span><textarea data-field="${field.key}">${escapeHtml(value || "")}</textarea></label>`;
      }
      if (field.type === "list") {
        return `<label class="${classes}"><span>${field.label} (comma or newline separated)</span><textarea data-field="${field.key}" data-list="true">${escapeHtml(arrayToText(value))}</textarea></label>`;
      }
      return `<label class="${classes}"><span>${field.label}</span><input data-field="${field.key}" value="${escapeHtml(value || "")}"></label>`;
    }

    function commonFields(entry) {
      return `
        <div class="grid">
          <label><span>ID</span><input data-field="id" value="${escapeHtml(entry.id || "")}"></label>
          <label><span>Priority</span><input data-field="priority" type="number" value="${Number(entry.priority || 0)}"></label>
          <label class="full"><span>Tags (comma or newline separated)</span><textarea data-field="tags" data-list="true">${escapeHtml(arrayToText(entry.tags))}</textarea></label>
          <label class="full"><span>Keywords (comma or newline separated)</span><textarea data-field="keywords" data-list="true">${escapeHtml(arrayToText(entry.keywords))}</textarea></label>
        </div>
      `;
    }

    function renderCandidate() {
      const links = db.candidate.links || [];
      $("editor").innerHTML = `
        <div class="editor-head"><h2>Candidate</h2></div>
        <div class="section-band">
          <div class="grid">
            ${["name", "headline", "location", "phone", "email"].map((field) => `
              <label><span>${field}</span><input data-candidate="${field}" value="${escapeHtml(db.candidate[field] || "")}"></label>
            `).join("")}
          </div>
        </div>
        <div class="section-band">
          <div class="list-head"><h3>Links</h3><button id="addLinkBtn">Add link</button></div>
          <div id="linksEditor">${links.map((link, index) => `
            <div class="bullet" data-link-index="${index}">
              <div class="row">
                <button data-link-up="${index}" ${index === 0 ? "disabled" : ""}>Up</button>
                <button data-link-down="${index}" ${index === links.length - 1 ? "disabled" : ""}>Down</button>
                <button class="danger" data-link-delete="${index}">Delete</button>
              </div>
              <div class="grid">
                ${["id", "label", "url", "kind"].map((field) => `
                  <label><span>${field}</span><input data-link-field="${field}" data-index="${index}" value="${escapeHtml(link[field] || "")}"></label>
                `).join("")}
              </div>
            </div>
          `).join("")}</div>
        </div>
      `;
      bindCandidate();
    }

    function renderRaw() {
      $("editor").innerHTML = `
        <div class="editor-head"><h2>Raw JSON</h2><button id="applyRawBtn">Apply to editor</button></div>
        <textarea class="raw" id="rawText">${escapeHtml(rawText || JSON.stringify(db, null, 2))}</textarea>
      `;
      $("rawText").addEventListener("input", (event) => {
        rawText = event.target.value;
        setStatus("Raw JSON edited, apply before saving", "bad");
      });
      $("applyRawBtn").addEventListener("click", () => {
        try {
          const parsed = JSON.parse($("rawText").value);
          const errors = clientValidate(parsed);
          if (errors.length) {
            setStatus(errors[0], "bad");
            return;
          }
          db = parsed;
          dirty = true;
          setStatus("Raw JSON applied", "ok");
          activeSection = "candidate";
          render();
        } catch (error) {
          setStatus(error.message, "bad");
        }
      });
    }

    function renderEntryEditor() {
      const config = configFor(activeSection);
      const entries = db[activeSection] || [];
      const entry = entries[selectedIndex];
      if (!entry) {
        $("editor").innerHTML = `<div class="empty">Select or add an entry.</div>`;
        return;
      }
      $("editor").innerHTML = `
        <div class="editor-head">
          <h2>${escapeHtml(config.title)}</h2>
          <div class="row">
            <button id="moveEntryUp" ${selectedIndex === 0 ? "disabled" : ""}>Up</button>
            <button id="moveEntryDown" ${selectedIndex === entries.length - 1 ? "disabled" : ""}>Down</button>
            <button id="duplicateEntry">Duplicate</button>
            <button class="danger" id="deleteEntry">Delete</button>
          </div>
        </div>
        <label class="checks"><input type="checkbox" data-field="enabled" ${entry.enabled !== false ? "checked" : ""}> Enabled</label>
        <div class="section-band">${commonFields(entry)}</div>
        <div class="section-band"><div class="grid">${(config.fields || []).map((field) => fieldControl(entry, field)).join("")}</div></div>
        ${config.bullets ? bulletsEditor(entry) : ""}
      `;
      bindEntry(config, entry, entries);
    }

    function bulletsEditor(entry) {
      const bullets = entry.bullets || [];
      return `
        <div class="section-band">
          <div class="list-head"><h3>Bullets</h3><button id="addBulletBtn">Add bullet</button></div>
          ${bullets.length ? bullets.map((bullet, index) => `
            <div class="bullet" data-bullet-index="${index}">
              <div class="row">
                <label class="checks"><input type="checkbox" data-bullet-field="enabled" data-index="${index}" ${bullet.enabled !== false ? "checked" : ""}> Enabled</label>
                <button data-bullet-up="${index}" ${index === 0 ? "disabled" : ""}>Up</button>
                <button data-bullet-down="${index}" ${index === bullets.length - 1 ? "disabled" : ""}>Down</button>
                <button class="danger" data-bullet-delete="${index}">Delete</button>
              </div>
              <div class="grid">
                <label><span>ID</span><input data-bullet-field="id" data-index="${index}" value="${escapeHtml(bullet.id || "")}"></label>
                <label><span>Priority</span><input type="number" data-bullet-field="priority" data-index="${index}" value="${Number(bullet.priority || 0)}"></label>
                <label class="full"><span>Text</span><textarea data-bullet-field="text" data-index="${index}">${escapeHtml(bullet.text || "")}</textarea></label>
                <label class="full"><span>Tags</span><textarea data-bullet-field="tags" data-index="${index}" data-list="true">${escapeHtml(arrayToText(bullet.tags))}</textarea></label>
                <label class="full"><span>Keywords</span><textarea data-bullet-field="keywords" data-index="${index}" data-list="true">${escapeHtml(arrayToText(bullet.keywords))}</textarea></label>
              </div>
            </div>
          `).join("") : `<div class="empty">No bullets for this entry.</div>`}
        </div>
      `;
    }

    function bindCandidate() {
      $("editor").querySelectorAll("[data-candidate]").forEach((input) => {
        input.addEventListener("input", () => {
          db.candidate[input.dataset.candidate] = input.value;
          markDirty();
        });
      });
      $("editor").querySelectorAll("[data-link-field]").forEach((input) => {
        input.addEventListener("input", () => {
          db.candidate.links[Number(input.dataset.index)][input.dataset.linkField] = input.value;
          markDirty();
        });
      });
      $("addLinkBtn").addEventListener("click", () => {
        db.candidate.links ||= [];
        db.candidate.links.push({ id: `link-${Date.now()}`, label: "", url: "", kind: "website" });
        markDirty();
        render();
      });
      bindMoveDelete("link", db.candidate.links, () => render());
    }

    function bindEntry(config, entry, entries) {
      $("editor").querySelectorAll("[data-field]").forEach((input) => {
        input.addEventListener(input.type === "checkbox" ? "change" : "input", () => {
          const value = input.type === "checkbox" ? input.checked : input.dataset.list ? textToArray(input.value) : input.type === "number" ? Number(input.value) : input.value;
          setPath(entry, input.dataset.field, value);
          markDirty();
          if (["id", "organization", "name", "label", "institution", "text"].includes(input.dataset.field)) renderList();
        });
      });
      $("moveEntryUp").addEventListener("click", () => moveItem(entries, selectedIndex, selectedIndex - 1, (next) => { selectedIndex = next; render(); }));
      $("moveEntryDown").addEventListener("click", () => moveItem(entries, selectedIndex, selectedIndex + 1, (next) => { selectedIndex = next; render(); }));
      $("duplicateEntry").addEventListener("click", () => {
        const copy = clone(entry);
        copy.id = `${entry.id || slug(titleForEntry(activeSection, entry))}-copy-${Date.now()}`;
        entries.splice(selectedIndex + 1, 0, copy);
        selectedIndex += 1;
        markDirty();
        render();
      });
      $("deleteEntry").addEventListener("click", () => {
        if (!confirm("Delete this entry?")) return;
        entries.splice(selectedIndex, 1);
        selectedIndex = Math.max(0, selectedIndex - 1);
        markDirty();
        render();
      });
      if (config.bullets) bindBullets(entry);
    }

    function bindBullets(entry) {
      entry.bullets ||= [];
      $("addBulletBtn").addEventListener("click", () => {
        entry.bullets.push({ id: `bullet-${Date.now()}`, enabled: true, priority: 50, tags: [], keywords: [], text: "" });
        markDirty();
        render();
      });
      $("editor").querySelectorAll("[data-bullet-field]").forEach((input) => {
        input.addEventListener(input.type === "checkbox" ? "change" : "input", () => {
          const bullet = entry.bullets[Number(input.dataset.index)];
          const value = input.type === "checkbox" ? input.checked : input.dataset.list ? textToArray(input.value) : input.type === "number" ? Number(input.value) : input.value;
          bullet[input.dataset.bulletField] = value;
          markDirty();
        });
      });
      bindMoveDelete("bullet", entry.bullets, () => render());
    }

    function bindMoveDelete(prefix, array, rerender) {
      $("editor").querySelectorAll(`[data-${prefix}-up]`).forEach((button) => {
        button.addEventListener("click", () => moveItem(array, Number(button.dataset[`${prefix}Up`]), Number(button.dataset[`${prefix}Up`]) - 1, rerender));
      });
      $("editor").querySelectorAll(`[data-${prefix}-down]`).forEach((button) => {
        button.addEventListener("click", () => moveItem(array, Number(button.dataset[`${prefix}Down`]), Number(button.dataset[`${prefix}Down`]) + 1, rerender));
      });
      $("editor").querySelectorAll(`[data-${prefix}-delete]`).forEach((button) => {
        button.addEventListener("click", () => {
          array.splice(Number(button.dataset[`${prefix}Delete`]), 1);
          markDirty();
          rerender();
        });
      });
    }

    function moveItem(array, from, to, done) {
      if (to < 0 || to >= array.length) return;
      const [item] = array.splice(from, 1);
      array.splice(to, 0, item);
      markDirty();
      done(to);
    }

    function newEntry(section) {
      const id = `${section}-${Date.now()}`;
      const base = { id, enabled: true, priority: 50, tags: [], keywords: [] };
      if (["experience", "projects"].includes(section)) base.bullets = [];
      if (section === "skills") base.items = [];
      if (section === "projects") base.link = { label: "", url: "", kind: "website" };
      return base;
    }

    function clientValidate(payload = db) {
      const errors = [];
      if (!payload || typeof payload !== "object") errors.push("Root must be an object.");
      if (!Number.isInteger(payload.schemaVersion)) errors.push("schemaVersion must be an integer.");
      if (!payload.candidate?.name) errors.push("candidate.name is required.");
      ["sectionOrder", "summaries", "education", "experience", "projects", "skills", "awards"].forEach((key) => {
        if (!Array.isArray(payload[key])) errors.push(`${key} must be an array.`);
      });
      const ids = new Map();
      ["summaries", "education", "experience", "projects", "skills", "awards"].forEach((section) => {
        (payload[section] || []).forEach((entry, index) => {
          if (!entry.id) errors.push(`${section}[${index}].id is required.`);
          if (entry.id && ids.has(entry.id)) errors.push(`Duplicate id ${entry.id}.`);
          if (entry.id) ids.set(entry.id, true);
        });
      });
      return errors;
    }

    function render() {
      renderMeta();
      renderNav();
      renderList();
      if (activeSection === "candidate") renderCandidate();
      else if (activeSection === "raw") renderRaw();
      else renderEntryEditor();
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#039;"
      }[char]));
    }

    async function loadDb() {
      const response = await fetch("/api/db");
      db = await response.json();
      rawText = JSON.stringify(db, null, 2);
      dirty = false;
      setStatus("Loaded", "ok");
      render();
    }

    async function saveDb() {
      const errors = clientValidate();
      if (errors.length) {
        setStatus(errors[0], "bad");
        return;
      }
      const response = await fetch("/api/db", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(db)
      });
      const payload = await response.json();
      if (!response.ok) {
        setStatus((payload.errors || [payload.error || "Save failed"])[0], "bad");
        return;
      }
      db = payload.db;
      rawText = JSON.stringify(db, null, 2);
      dirty = false;
      setStatus("Saved", "ok");
      render();
    }

    $("addEntryBtn").addEventListener("click", () => {
      db[activeSection] ||= [];
      db[activeSection].push(newEntry(activeSection));
      selectedIndex = db[activeSection].length - 1;
      markDirty();
      render();
    });
    $("saveBtn").addEventListener("click", saveDb);
    $("validateBtn").addEventListener("click", () => {
      const errors = clientValidate();
      setStatus(errors.length ? errors[0] : "Validation passed", errors.length ? "bad" : "ok");
    });
    $("rawBtn").addEventListener("click", () => {
      activeSection = "raw";
      rawText = JSON.stringify(db, null, 2);
      render();
    });

    window.addEventListener("beforeunload", (event) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    });

    loadDb().catch((error) => setStatus(error.message, "bad"));
  </script>
</body>
</html>
"""


class ConfigDbHandler(BaseHTTPRequestHandler):
    db_path: Path

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}", file=sys.stderr)

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        self._send(status, json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"), "application/json")

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._send(HTTPStatus.OK, html_page().encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path == "/api/db":
            try:
                payload = json.loads(self.db_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
                return
            self._send(HTTPStatus.OK, json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"), "application/json")
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/api/db":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        errors = validate_db(payload)
        if errors:
            self._send_json(HTTPStatus.BAD_REQUEST, {"errors": errors})
            return

        payload["updatedAt"] = date.today().isoformat()
        rendered = json.dumps(payload, indent=2, sort_keys=False) + "\n"
        try:
            self.db_path.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.OK, {"status": "ok", "db": payload})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start a local editor for CVPilot db.json")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind")
    parser.add_argument("--db", default=str(repo_root() / "db.json"), help="Path to db.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"db.json not found: {db_path}")
    ConfigDbHandler.db_path = db_path
    server = ThreadingHTTPServer((args.host, args.port), ConfigDbHandler)
    print(f"CVPilot DB editor running at http://{args.host}:{args.port}")
    print(f"Editing {db_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping CVPilot DB editor")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
