// Гость: меню, корзина, пожелание, интервал, подтверждение и надёжная отправка.
import { api, h, money, hm, describeLine, setMsg, uuid, store, setupTabs, setTimezone, syncServerTime } from "./common.js";
import { refreshOrders, renderFavorites, saveFavorite } from "./guest-orders.js";

const S = {
  point: null,
  menu: { drinks: [], addons: [] },
  cart: store.get("cart", []),
  slot: null,
  pending: null,   // {attempt_id, body} — подтверждаемое содержимое
};

const $ = (id) => document.getElementById(id);
const drinkById = (id) => S.menu.drinks.find((d) => d.id === id);
const addonById = (id) => S.menu.addons.find((a) => a.id === id);

function priceOf(line) {
  const d = drinkById(line.drink_id);
  const size = d && d.sizes.find((s) => s.code === line.size);
  if (!size) return null;
  const add = line.addons.reduce((sum, id) => sum + (addonById(id)?.price ?? 0), 0);
  return (size.price + add) * line.qty;
}
const cartQty = () => S.cart.reduce((n, l) => n + l.qty, 0);
const cartTotal = () => S.cart.reduce((n, l) => n + (priceOf(l) ?? 0), 0);

function saveCart() {
  store.set("cart", S.cart);
  $("cart-count").textContent = String(cartQty());
  invalidateConfirmation();
}

// ---------- Точка и меню ----------
async function loadPoint() {
  const { data } = await api("/api/point");
  S.point = data;
  setTimezone(data.timezone);
  syncServerTime(data.now);
  $("notice").textContent = data.notice;
  const info = $("point-info");
  info.replaceChildren(
    `${data.name}. ${data.address}. Приём заказов ${data.open}–${data.close} (${data.timezone}), только на сегодня. `,
    data.block_reason ? h("span", { class: "block-reason" }, data.block_reason) : "Приём открыт.",
  );
}

async function loadMenu() {
  const { data } = await api("/api/menu");
  S.menu = data;
  renderMenu();
  renderCart();
}

function renderMenu() {
  const grid = $("menu-grid");
  grid.replaceChildren(...S.menu.drinks.map(drinkCard));
}

function drinkCard(d) {
  const name = `size-${d.id}`;
  let qty = 1;
  const qtyOut = h("output", {}, "1");
  const sizeChips = d.sizes.map((s, i) => h("label", { class: "chip" },
    h("input", { type: "radio", name, value: s.code, checked: i === 0 }),
    h("span", {}, `${s.label} — ${money(s.price)}`)));
  const addonChips = d.addon_ids.map(addonById).filter(Boolean).map((a) => h("label", { class: "chip" },
    h("input", { type: "checkbox", value: a.id, disabled: !a.available }),
    h("span", {}, `${a.name} +${money(a.price)}${a.available ? "" : " (нет)"}`)));
  const card = h("article", { class: `card${d.available ? "" : " off"}` },
    h("h3", {}, d.name),
    h("p", { class: "muted" }, d.description),
    d.recommendation ? h("p", { class: "rec" }, d.recommendation) : null,
    h("div", { class: "chips", role: "radiogroup", "aria-label": `Размер: ${d.name}` }, sizeChips),
    addonChips.length ? h("div", { class: "chips", "aria-label": "Добавки" }, addonChips) : null,
    h("div", { class: "row between" },
      h("span", { class: "stepper" },
        h("button", { type: "button", "aria-label": "Меньше", onclick: () => { qty = Math.max(1, qty - 1); qtyOut.textContent = qty; } }, "−"),
        qtyOut,
        h("button", { type: "button", "aria-label": "Больше", onclick: () => { qty = Math.min(4, qty + 1); qtyOut.textContent = qty; } }, "+")),
      h("button", {
        class: "btn", type: "button", disabled: !d.available,
        onclick: () => {
          const size = card.querySelector(`input[name="${name}"]:checked`).value;
          const addons = [...card.querySelectorAll('input[type="checkbox"]:checked')].map((x) => x.value);
          addToCart({ drink_id: d.id, size, addons, qty });
        },
      }, d.available ? "В корзину" : "Нет в наличии")),
  );
  return card;
}

function addToCart(line) {
  const max = S.point?.rules.max_drinks ?? 4;
  if (cartQty() + line.qty > max) {
    setMsg($("global-msg"), `В заказе может быть не больше ${max} напитков.`, "warn");
    return;
  }
  const same = S.cart.find((l) => l.drink_id === line.drink_id && l.size === line.size &&
    [...l.addons].sort().join() === [...line.addons].sort().join());
  if (same) same.qty += line.qty; else S.cart.push(line);
  saveCart();
  renderCart();
  setMsg($("global-msg"), `${drinkById(line.drink_id).name} добавлен в корзину.`, "ok");
}

// ---------- Корзина ----------
function renderCart() {
  const lines = $("cart-lines");
  if (!S.cart.length) {
    lines.replaceChildren(h("p", { class: "muted" }, "Корзина пуста. Выберите напитки в меню."));
  } else {
    lines.replaceChildren(...S.cart.map((l, i) => {
      const d = drinkById(l.drink_id);
      const p = priceOf(l);
      const title = describeLine({ ...l, drink_name: d?.name, addons: l.addons.map((a) => addonById(a)?.name ?? a) });
      return h("div", { class: "cart-line" },
        h("div", {}, title, p === null ? h("div", { class: "msg bad" }, "Позиция недоступна в текущем меню") : null),
        h("div", { class: "row" },
          h("span", { class: "stepper" },
            h("button", { type: "button", "aria-label": "Меньше", onclick: () => changeQty(i, -1) }, "−"),
            h("output", {}, String(l.qty)),
            h("button", { type: "button", "aria-label": "Больше", onclick: () => changeQty(i, +1) }, "+")),
          h("span", { class: "price" }, p === null ? "—" : money(p)),
          h("button", { class: "btn danger small", type: "button", onclick: () => removeLine(i) }, "Удалить")));
    }));
  }
  const max = S.point?.rules.max_drinks ?? 4;
  $("cart-qty").textContent = `Напитков: ${cartQty()} из ${max}`;
  $("cart-total").textContent = `Итого: ${money(cartTotal())}`;
  $("cart-count").textContent = String(cartQty());
  loadSlots();
}

function changeQty(i, delta) {
  const line = S.cart[i];
  const max = S.point?.rules.max_drinks ?? 4;
  if (delta > 0 && cartQty() >= max) {
    setMsg($("global-msg"), `В заказе может быть не больше ${max} напитков.`, "warn");
    return;
  }
  line.qty += delta;
  if (line.qty <= 0) S.cart.splice(i, 1);
  saveCart();
  renderCart();
}

function removeLine(i) {
  S.cart.splice(i, 1);
  saveCart();
  renderCart();
}

// ---------- Пожелание ----------
function wishText() { return $("wish").value.replace(/\r\n?/g, "\n"); }
function wishLength() { return [...wishText()].length; }

function updateWishCounter() {
  const max = S.point?.rules.wish_max ?? 200;
  const n = wishLength();
  const el = $("wish-counter");
  el.textContent = n > max ? `${n} / ${max} — слишком длинно, сократите текст` : `${n} / ${max}`;
  el.style.color = n > max ? "var(--bad)" : "";
  invalidateConfirmation();
}

// ---------- Интервалы ----------
let slotsSeq = 0;
async function loadSlots() {
  const seq = ++slotsSeq;
  const qty = Math.max(1, cartQty());
  try {
    const { data } = await api(`/api/slots?qty=${qty}`);
    if (seq !== slotsSeq) return;
    renderSlots(data);
  } catch (e) {
    $("slots").replaceChildren(h("p", { class: "msg bad" }, `Не удалось загрузить интервалы: ${e.message}`));
  }
}

function renderSlots(data) {
  const box = $("slots");
  const usable = data.slots.filter((s) => s.available);
  if (S.slot && !usable.some((s) => s.key === S.slot)) S.slot = null;
  if (!usable.length) {
    box.replaceChildren(h("p", { class: "msg warn" }, data.block_reason || "Нет доступных интервалов на сегодня."));
    return;
  }
  const visible = data.slots.filter((s) => s.available || s.reason !== "Время уже недоступно для заказа");
  box.replaceChildren(...visible.map((s) => h("button", {
    class: "slot", type: "button", disabled: !s.available, "aria-pressed": String(S.slot === s.key),
    title: s.reason || "", onclick: () => { S.slot = s.key; invalidateConfirmation(); renderSlots(data); },
  }, `${hm(s.start)}–${hm(s.end)}`, h("small", {}, s.available ? `мест: ${s.remaining}` : s.reason))));
}

// ---------- Подтверждение и отправка ----------
function invalidateConfirmation() {
  if (S.pending && S.pending.state !== "unknown") {
    S.pending = null;
    $("confirm").hidden = true;
  }
}

function localProblems() {
  const r = S.point?.rules ?? { max_drinks: 4, wish_max: 200 };
  if (!S.cart.length) return "Корзина пуста.";
  if (cartQty() > r.max_drinks) return `В заказе может быть не больше ${r.max_drinks} напитков.`;
  if (S.cart.some((l) => priceOf(l) === null)) return "В корзине есть недоступные позиции — удалите их.";
  if (wishLength() > r.wish_max) return `Пожелание длиннее ${r.wish_max} символов.`;
  if (!S.slot) return "Выберите время получения.";
  return null;
}

function openConfirmation() {
  const problem = localProblems();
  if (problem) { setMsg($("global-msg"), problem, "warn"); return; }
  const body = {
    attempt_id: uuid(), items: S.cart.map((l) => ({ ...l })), wish: wishText(),
    slot: S.slot, expected_total: cartTotal(),
  };
  S.pending = { body, state: "ready" };
  const p = S.point;
  $("confirm-body").replaceChildren(
    h("p", {}, h("b", {}, "Где: "), `${p.name}, ${p.address}`),
    h("p", {}, h("b", {}, "Когда: "), `сегодня, интервал ${S.slot} (${p.timezone})`),
    h("ul", { class: "plain" }, S.cart.map((l) => h("li", {},
      describeLine({ ...l, drink_name: drinkById(l.drink_id).name, addons: l.addons.map((a) => addonById(a).name) }),
      " — ", money(priceOf(l))))),
    body.wish ? h("div", {}, h("b", {}, "Пожелание:"), h("div", { class: "wish" }, body.wish)) : h("p", { class: "muted" }, "Без пожелания"),
    h("p", { class: "total" }, `Итого: ${money(body.expected_total)}`),
    h("p", { class: "muted" }, "Оплата не производится: это учебная демонстрация."),
  );
  setMsg($("confirm-msg"), "");
  $("confirm-send").hidden = false;
  $("confirm-send").textContent = "Подтвердить заказ";
  $("confirm-check").hidden = true;
  $("confirm").hidden = false;
  $("confirm").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function sendOrder() {
  if (!S.pending) return;
  const btn = $("confirm-send");
  btn.disabled = true;
  setMsg($("confirm-msg"), "Отправляем заказ…", "info");
  try {
    const { data } = await api("/api/orders", { method: "POST", body: S.pending.body });
    onAccepted(data);
  } catch (e) {
    await onSendError(e);
  } finally {
    btn.disabled = false;
  }
}

async function checkAttempt() {
  if (!S.pending) return;
  setMsg($("confirm-msg"), "Проверяем результат…", "info");
  try {
    const { data } = await api(`/api/attempts/${S.pending.body.attempt_id}`);
    onAccepted(data);
  } catch (e) {
    if (e.status === 404) {
      setMsg($("confirm-msg"), "Заказ по этой попытке не принят. Можно отправить ещё раз — дубля не будет.", "warn");
      $("confirm-send").hidden = false;
      $("confirm-send").textContent = "Отправить ещё раз";
    } else {
      setMsg($("confirm-msg"), `Проверить пока не удалось (${e.message}). Попробуйте позже.`, "bad");
    }
  }
}

function onAccepted(order) {
  S.pending = null;
  S.cart = [];
  S.slot = null;
  $("wish").value = "";
  store.set("cart", S.cart);
  $("confirm").hidden = true;
  renderCart();
  updateWishCounter();
  setMsg($("global-msg"), `Заказ №${order.number} принят. Статус: «${order.status_label}». ` +
    `Получение: ${hm(order.slot.start)}–${hm(order.slot.end)}. Следите за статусом в «Мои заказы».`, "ok");
  refreshOrders();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function onSendError(e) {
  if (e.kind === "network" || e.kind === "unavailable" || e.status >= 500) {
    S.pending.state = "unknown";
    setMsg($("confirm-msg"), "Результат отправки неизвестен. Проверьте результат — повторная проверка или отправка " +
      "этой же попытки не создаст второй заказ.", "warn");
    $("confirm-check").hidden = false;
    $("confirm-send").textContent = "Отправить ещё раз";
    return;
  }
  S.pending = null;
  $("confirm-send").hidden = true;
  if (e.code === "conditions_changed") {
    setMsg($("confirm-msg"), `${e.message} Новая сумма: ${money(e.details.total)}.`, "warn");
  } else {
    setMsg($("confirm-msg"), e.message, e.kind === "validation" ? "bad" : "warn");
  }
  await Promise.allSettled([loadPoint(), loadMenu()]);
}

// ---------- Запуск ----------
function init() {
  setupTabs((id) => {
    if (id === "orders") refreshOrders();
    if (id === "favorites") renderFavorites(applyFavorite);
    if (id === "cart") loadSlots();
  });
  $("wish").addEventListener("input", updateWishCounter);
  $("to-confirm").addEventListener("click", openConfirmation);
  $("confirm-send").addEventListener("click", sendOrder);
  $("confirm-check").addEventListener("click", checkAttempt);
  $("confirm-cancel").addEventListener("click", () => { S.pending = null; $("confirm").hidden = true; });
  $("save-favorite").addEventListener("click", () => {
    if (!S.cart.length) { setMsg($("global-msg"), "Корзина пуста — нечего сохранять.", "warn"); return; }
    saveFavorite(S.cart, S.menu);
    setMsg($("global-msg"), "Корзина сохранена в избранное (только в этом браузере).", "ok");
  });
  Promise.all([loadPoint(), loadMenu()])
    .then(updateWishCounter)
    .catch((e) => setMsg($("global-msg"), `Не удалось загрузить данные: ${e.message}`, "bad"));
}

// Повтор избранного: только проверенные сервером позиции, без скрытых замен.
function applyFavorite(checked) {
  S.cart = checked.lines.filter((l) => !l.problem)
    .map((l) => ({ drink_id: l.drink_id, size: l.size, addons: l.addons.map((a) => a.id ?? a), qty: l.qty }));
  S.slot = null;
  $("wish").value = "";
  saveCart();
  renderCart();
  updateWishCounter();
  const skipped = checked.lines.filter((l) => l.problem).map((l) => l.problem);
  const text = skipped.length
    ? `Корзина собрана по текущему меню, но часть позиций не добавлена: ${skipped.join("; ")}. Выберите замену сами.`
    : `Корзина собрана по текущим ценам: ${money(checked.total)}. Выберите время и подтвердите заказ.`;
  setMsg($("global-msg"), text, skipped.length ? "warn" : "ok");
  document.querySelector('[data-tab="cart"]').click();
}

init();
