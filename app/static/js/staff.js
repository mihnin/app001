// Сотрудник: вход, очередь, переходы статусов, отмена с причиной, завершение дня.
import { api, h, money, hm, hms, describeLine, statusBadge, setMsg, setupTabs, setTimezone, syncServerTime, serverNow } from "./common.js";
import { loadIntake, loadSummary, initAdmin } from "./staff-admin.js";

const $ = (id) => document.getElementById(id);
const NEXT_LABEL = { accepted: "Начать готовить", preparing: "Готов", ready: "Выдан" };
const ACTIVE = new Set(["accepted", "preparing", "ready"]);
let orders = [];

async function boot() {
  try {
    const { data: point } = await api("/api/point");
    setTimezone(point.timezone);
    syncServerTime(point.now);
  } catch { /* часовой пояс по умолчанию */ }
  const { data } = await api("/api/staff/me");
  data.staff ? showApp() : showLogin();
}

function showLogin() {
  $("login-form").hidden = false;
  $("app").hidden = true;
  $("staff-tabs").hidden = true;
  $("password").focus();
}

function showApp() {
  $("login-form").hidden = true;
  $("app").hidden = false;
  $("staff-tabs").hidden = false;
  refreshQueue();
}

async function login(ev) {
  ev.preventDefault();
  try {
    await api("/api/staff/login", { method: "POST", body: { password: $("password").value } });
    $("password").value = "";
    setMsg($("login-msg"), "");
    showApp();
  } catch (e) {
    setMsg($("login-msg"), e.message, "bad");
  }
}

async function logout() {
  await api("/api/staff/logout", { method: "POST" }).catch(() => {});
  showLogin();
}

// Любой 403 в панели означает, что сессия закончилась.
export function handleError(e, target = $("staff-msg")) {
  if (e.status === 403) { showLogin(); return; }
  setMsg(target, e.message, e.kind === "validation" ? "bad" : "warn");
}

// ---------- Очередь ----------
export async function refreshQueue() {
  const stamp = $("queue-updated");
  try {
    const { data } = await api("/api/staff/queue");
    orders = data;
    stamp.textContent = `обновлено в ${hms()}`;
    stamp.className = "muted";
  } catch (e) {
    stamp.textContent = `Не обновлено: ${e.message}`;
    stamp.className = "stale";
    if (e.status === 403) { showLogin(); return; }
  }
  renderQueue();
}

function renderQueue() {
  const showAll = $("show-all").checked;
  const visible = orders.filter((o) => showAll || ACTIVE.has(o.status));
  const list = $("queue-list");
  if (!visible.length) {
    list.replaceChildren(h("p", { class: "muted" }, showAll ? "Сегодня заказов нет." : "Активных заказов нет."));
    return;
  }
  const groups = new Map();
  for (const o of visible) {
    const key = `${hm(o.slot.start)}–${hm(o.slot.end)}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(o);
  }
  list.replaceChildren(...[...groups].map(([slot, items]) => h("div", { class: "slot-group" },
    h("h3", {}, `Интервал ${slot}`),
    h("div", { class: "grid" }, items.map(queueCard)))));
}

function queueCard(o) {
  const msg = h("div", { class: "msg", role: "alert" });
  const reason = h("input", { type: "text", maxlength: "200", placeholder: "Причина отмены (обязательно)",
    "aria-label": `Причина отмены заказа ${o.number}` });
  const cancelBox = h("div", { class: "row", hidden: true }, reason,
    h("button", { class: "btn danger small", type: "button", onclick: () => cancel(o, reason.value, msg) },
      "Подтвердить отмену"));
  const actions = ACTIVE.has(o.status) ? h("div", { class: "row" },
    h("button", { class: "btn small", type: "button", onclick: () => advance(o, msg) }, NEXT_LABEL[o.status]),
    h("button", { class: "btn danger small", type: "button",
      onclick: () => { cancelBox.hidden = !cancelBox.hidden; if (!cancelBox.hidden) reason.focus(); } },
      "Отменить…")) : null;
  const overdue = ACTIVE.has(o.status) && new Date(o.slot.end) < serverNow();
  return h("article", { class: "card" },
    h("div", { class: "row between" }, h("h3", {}, `№${o.number}`), statusBadge(o)),
    h("p", { class: "muted" }, `Принят в ${hm(o.accepted_at)}` +
      (o.ready_at ? ` · готов в ${hm(o.ready_at)}` : "")),
    overdue ? h("p", { class: "stale" }, "Интервал уже закончился") : null,
    h("ul", { class: "plain" }, o.lines.map((l) => h("li", {}, describeLine(l)))),
    o.wish ? h("div", {}, h("b", {}, "Пожелание гостя:"), h("div", { class: "wish" }, o.wish)) : null,
    h("p", {}, `Сумма: ${money(o.total)}`),
    o.cancel_reason ? h("p", { class: "msg bad" }, `Отменён (${o.cancelled_by === "guest" ? "гостем" : "сотрудником"}): ${o.cancel_reason}`) : null,
    actions, cancelBox, msg);
}

async function advance(o, msg) {
  try {
    await api(`/api/staff/orders/${o.id}/advance`, { method: "POST", body: { expected_status: o.status } });
    await refreshQueue();
  } catch (e) {
    handleError(e, msg);
    if (e.code === "stale") await refreshQueue().then(() => setMsg($("staff-msg"), e.message, "warn"));
  }
}

async function cancel(o, reason, msg) {
  try {
    await api(`/api/staff/orders/${o.id}/cancel`, { method: "POST", body: { expected_status: o.status, reason } });
    await refreshQueue();
  } catch (e) {
    handleError(e, msg);
    if (e.code === "stale") await refreshQueue().then(() => setMsg($("staff-msg"), e.message, "warn"));
  }
}

async function closeDay(ev) {
  const btn = ev.target;
  if (btn.dataset.armed !== "1") {
    btn.dataset.armed = "1";
    btn.textContent = "Подтвердите: завершить день";
    return;
  }
  btn.dataset.armed = "";
  btn.textContent = "Завершить день";
  try {
    const { data } = await api("/api/staff/close-day", { method: "POST" });
    setMsg($("staff-msg"), `День завершён: отменено ${data.cancelled}, не получено ${data.not_received}.`, "ok");
    await refreshQueue();
  } catch (e) {
    handleError(e);
  }
}

function init() {
  setupTabs((id) => {
    if (id === "queue") refreshQueue();
    if (id === "intake") loadIntake();
    if (id === "summary") loadSummary();
  });
  initAdmin(handleError);
  $("login-form").addEventListener("submit", login);
  $("logout").addEventListener("click", logout);
  $("queue-refresh").addEventListener("click", refreshQueue);
  $("show-all").addEventListener("change", renderQueue);
  $("close-day").addEventListener("click", closeDay);
  boot().catch((e) => setMsg($("login-msg"), `Не удалось связаться с сервером: ${e.message}`, "bad"));
}

init();
