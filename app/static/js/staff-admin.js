// Сотрудник: пауза, стоп-лист, лимиты интервалов, дневная сводка.
import { api, h, money, hm, setMsg, syncServerTime, serverNow } from "./common.js";

const $ = (id) => document.getElementById(id);
let onError = () => {};

export function initAdmin(errorHandler) {
  onError = errorHandler;
  $("pause").addEventListener("change", async (ev) => {
    try {
      await api("/api/staff/pause", { method: "POST", body: { paused: ev.target.checked } });
      setMsg($("staff-msg"), ev.target.checked ? "Приём новых заказов приостановлен." : "Приём возобновлён.", "ok");
    } catch (e) {
      ev.target.checked = !ev.target.checked;
      onError(e);
    }
  });
  $("summary-refresh").addEventListener("click", loadSummary);
}

export async function loadIntake() {
  try {
    const [{ data: point }, { data: menu }, { data: slots }] = await Promise.all([
      api("/api/point"), api("/api/staff/menu"), api("/api/staff/slots"),
    ]);
    syncServerTime(point.now);
    $("pause").checked = point.paused;
    $("stop-drinks").replaceChildren(...menu.drinks.map((d) => toggle(d, "drinks")));
    $("stop-addons").replaceChildren(...menu.addons.map((a) => toggle(a, "addons")));
    renderLimits(slots);
  } catch (e) {
    onError(e);
  }
}

function toggle(item, kind) {
  const box = h("input", { type: "checkbox", checked: item.available });
  box.addEventListener("change", async () => {
    try {
      await api(`/api/staff/${kind}/${item.id}/availability`, { method: "POST", body: { available: box.checked } });
    } catch (e) {
      box.checked = !box.checked;
      onError(e);
    }
  });
  return h("div", {}, h("label", { class: "switch" }, box, `${item.name} — в наличии`));
}

function renderLimits(data) {
  const now = serverNow();
  const rows = data.slots.filter((s) => new Date(s.end) > now);
  if (!rows.length) {
    $("limits").replaceChildren(h("tr", {}, h("td", { colspan: "5" }, "На сегодня интервалов больше нет.")));
    return;
  }
  $("limits").replaceChildren(...rows.map((s) => {
    const input = h("input", { type: "number", min: "0", step: "1", value: String(s.limit),
      "aria-label": `Лимит интервала ${s.key}` });
    const rest = h("td", {}, String(s.remaining));
    return h("tr", {},
      h("td", {}, `${hm(s.start)}–${hm(s.end)}`),
      h("td", {}, String(s.used)),
      h("td", {}, input),
      rest,
      h("td", {}, h("button", {
        class: "btn small", type: "button",
        onclick: async () => {
          const value = Number(input.value);
          try {
            const { data: res } = await api(`/api/staff/slots/${s.key}/limit`, {
              method: "POST", body: { limit: Number.isInteger(value) ? value : input.value },
            });
            rest.textContent = String(res.remaining);
            setMsg($("staff-msg"), `Лимит ${s.key} = ${res.limit}, остаток ${res.remaining}.`, "ok");
          } catch (e) {
            onError(e);
          }
        },
      }, "Сохранить")));
  }));
}

function fmtDuration(sec) {
  if (sec === null || sec === undefined) return "Нет данных";
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m} мин ${s} с`;
}

export async function loadSummary() {
  const day = $("summary-day").value;
  try {
    const { data } = await api(`/api/staff/summary${day ? `?day=${encodeURIComponent(day)}` : ""}`);
    if (!day) $("summary-day").value = data.day;
    renderSummary(data);
  } catch (e) {
    onError(e);
  }
}

function renderSummary(s) {
  const kpi = (title, value) => h("div", { class: "kpi" }, h("span", { class: "muted" }, title), h("b", {}, value));
  const list = (items) => (items.length ? items.map((n) => `№${n}`).join(", ") : "нет");
  const reasons = Object.entries(s.cancel_reasons);
  $("summary-body").replaceChildren(
    h("div", { class: "kpis" },
      kpi("Уникальных заказов", String(s.total)),
      kpi("Готовность к концу интервала", s.readiness.text),
      kpi("Среднее время до готовности", fmtDuration(s.avg_ready_seconds)),
      kpi("Сумма учебных заказов", money(s.demo_total))),
    h("p", { class: "muted" }, s.note),
    h("h3", { class: "mt" }, "Статусы"),
    h("div", { class: "table-wrap" }, h("table", {},
      h("tbody", {}, Object.entries(s.by_status).map(([k, v]) => h("tr", {}, h("td", {}, k), h("td", {}, String(v))))))),
    h("h3", { class: "mt" }, "Причины отмен"),
    reasons.length
      ? h("ul", { class: "plain" }, reasons.map(([r, n]) => h("li", {}, `${r} — ${n}`)))
      : h("p", { class: "muted" }, "Отмен нет"),
    h("h3", { class: "mt" }, "Требуют внимания"),
    h("p", {}, `Активные с истёкшим интервалом: ${list(s.overdue_active)}`),
    h("p", {}, `Не получены: ${list(s.not_received)}`),
    h("h3", { class: "mt" }, "Время от принятия до первой готовности"),
    s.durations.length
      ? h("ul", { class: "plain" }, s.durations.map((d) => h("li", {}, `№${d.number}: ${fmtDuration(d.seconds)}`)))
      : h("p", { class: "muted" }, "Нет данных"),
  );
}
