// Общие утилиты: запросы к API, форматирование, безопасное построение DOM (только textContent).

export class ApiError extends Error {
  constructor(status, body) {
    const err = (body && body.error) || {};
    super(err.message || `Ошибка ${status}`);
    this.status = status;
    this.kind = err.kind || (status === 0 ? "network" : "error");
    this.code = err.code || this.kind;
    this.details = err.details || {};
  }
}

export async function api(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, { error: { kind: "network", message: "Нет связи с сервером" } });
  }
  let data = null;
  try { data = await res.json(); } catch { data = null; }
  if (!res.ok) throw new ApiError(res.status, data);
  return { status: res.status, data };
}

// h("div", {class: "x", onclick: fn}, "текст", child)
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, String(v));
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function money(kop) {
  const rub = kop / 100;
  const opts = Number.isInteger(rub) ? {} : { minimumFractionDigits: 2, maximumFractionDigits: 2 };
  return `${rub.toLocaleString("ru-RU", opts)} ₽`;
}

let TZ = "Europe/Moscow";
export function setTimezone(tz) { TZ = tz; }

export function hm(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("ru-RU", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
}

export function hms(date = new Date()) {
  return date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function statusBadge(order) {
  return h("span", { class: `status st-${order.status}` }, order.status_label);
}

export function describeLine(line) {
  const addons = (line.addons || []).map((a) => a.name || a).join(", ");
  return `${line.drink_name || line.drink_id} · ${line.size}${addons ? " · " + addons : ""} × ${line.qty}`;
}

export function setMsg(el, text, kind = "info") {
  el.className = `msg ${kind}`;
  el.textContent = text || "";
}

export function uuid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  return [...b].map((x) => x.toString(16).padStart(2, "0")).join("").replace(
    /^(.{8})(.{4})(.{4})(.{4})(.{12})$/, "$1-$2-$3-$4-$5");
}

export const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* хранилище недоступно */ }
  },
};

export function setupTabs(onChange) {
  const tabs = [...document.querySelectorAll(".tab[data-tab]")];
  const show = (id) => {
    for (const t of tabs) {
      const on = t.dataset.tab === id;
      t.setAttribute("aria-selected", String(on));
      document.getElementById(t.dataset.tab).hidden = !on;
    }
    if (onChange) onChange(id);
  };
  tabs.forEach((t) => t.addEventListener("click", () => show(t.dataset.tab)));
  return show;
}

// Серверное время: интерфейс не опирается на часы устройства.
let serverOffsetMs = 0;
export function syncServerTime(serverIso) {
  if (serverIso) serverOffsetMs = new Date(serverIso).getTime() - Date.now();
}
export function serverNow() { return new Date(Date.now() + serverOffsetMs); }
