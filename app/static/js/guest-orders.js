// Гость: мои заказы (явное обновление, отмена) и избранные корзины (localStorage).
import { api, h, money, hm, hms, describeLine, statusBadge, setMsg, store } from "./common.js";

const $ = (id) => document.getElementById(id);
let lastOrders = [];

export async function refreshOrders() {
  const stamp = $("orders-updated");
  try {
    const { data } = await api("/api/orders");
    lastOrders = data;
    stamp.textContent = `обновлено в ${hms()}`;
    stamp.className = "muted";
    renderOrders(false);
  } catch (e) {
    stamp.textContent = `Не обновлено: ${e.message}. Показано последнее полученное состояние.`;
    stamp.className = "stale";
    renderOrders(true);
  }
}

function renderOrders(stale) {
  const list = $("orders-list");
  if (!lastOrders.length) {
    list.replaceChildren(h("p", { class: "muted" }, "Заказов пока нет."));
    return;
  }
  list.replaceChildren(...lastOrders.map((o) => orderCard(o, stale)));
}

function orderCard(o, stale) {
  const msg = h("div", { class: "msg", role: "alert" });
  let armed = false;
  const cancelBtn = o.guest_can_cancel ? h("button", {
    class: "btn danger small", type: "button",
    onclick: async (ev) => {
      if (!armed) { armed = true; ev.target.textContent = "Точно отменить?"; return; }
      ev.target.disabled = true;
      try {
        await api(`/api/orders/${o.id}/cancel`, { method: "POST" });
        await refreshOrders();
      } catch (e) {
        setMsg(msg, e.message, "warn");
        ev.target.disabled = false;
      }
    },
  }, "Отменить заказ") : null;
  return h("article", { class: "card" },
    h("div", { class: "row between" }, h("h3", {}, `Заказ №${o.number}`), statusBadge(o)),
    stale ? h("p", { class: "stale" }, "Состояние может быть устаревшим") : null,
    h("p", { class: "muted" }, `Получение: сегодня ${hm(o.slot.start)}–${hm(o.slot.end)} · ${o.point.address}`),
    h("ul", { class: "plain" }, o.lines.map((l) => h("li", {}, describeLine(l), " — ", money(l.line_total)))),
    o.wish ? h("div", { class: "wish" }, o.wish) : null,
    h("p", { class: "total" }, money(o.total)),
    o.cancel_reason ? h("p", { class: "msg bad" }, `Причина отмены: ${o.cancel_reason}`) : null,
    !o.guest_can_cancel && ["preparing", "ready"].includes(o.status)
      ? h("p", { class: "muted" }, "Заказ уже готовится — для отмены обратитесь к сотруднику.") : null,
    cancelBtn, msg);
}

// ---------- Избранное ----------
const FAV_KEY = "favorites";

export function saveFavorite(cart, menu) {
  const names = cart.map((l) => menu.drinks.find((d) => d.id === l.drink_id)?.name ?? l.drink_id);
  const favs = store.get(FAV_KEY, []);
  favs.unshift({
    id: String(Date.now()),
    name: names.join(", ").slice(0, 80),
    items: cart.map((l) => ({ drink_id: l.drink_id, size: l.size, addons: [...l.addons], qty: l.qty })),
    labels: cart.map((l) => describeLine({
      ...l,
      drink_name: menu.drinks.find((d) => d.id === l.drink_id)?.name,
      addons: l.addons.map((a) => menu.addons.find((x) => x.id === a)?.name ?? a),
    })),
    saved_at: new Date().toISOString(),
  });
  store.set(FAV_KEY, favs.slice(0, 20));
}

export function renderFavorites(onRepeat) {
  const list = $("favorites-list");
  const favs = store.get(FAV_KEY, []);
  if (!favs.length) {
    list.replaceChildren(h("p", { class: "muted" }, "Пока пусто. Соберите корзину и нажмите «Сохранить корзину в избранное»."));
    return;
  }
  list.replaceChildren(...favs.map((f) => {
    const msg = h("div", { class: "msg", role: "alert" });
    return h("article", { class: "card" },
      h("h3", {}, f.name),
      h("ul", { class: "plain" }, (f.labels || f.items.map((l) => describeLine(l))).map((t) => h("li", {}, t))),
      h("p", { class: "muted" }, "Цены пересчитаются по текущему меню при повторе."),
      h("p", { class: "muted" }, `Сохранено ${new Date(f.saved_at).toLocaleString("ru-RU")}`),
      h("div", { class: "row" },
        h("button", {
          class: "btn small", type: "button",
          onclick: async () => {
            try {
              const { data } = await api("/api/cart/check", { method: "POST", body: { items: f.items } });
              onRepeat(data);
            } catch (e) { setMsg(msg, e.message, "bad"); }
          },
        }, "Повторить"),
        h("button", {
          class: "btn danger small", type: "button",
          onclick: () => {
            store.set(FAV_KEY, store.get(FAV_KEY, []).filter((x) => x.id !== f.id));
            renderFavorites(onRepeat);
          },
        }, "Удалить")),
      msg);
  }));
}
