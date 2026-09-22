/* Hamyon — WebApp (do'kon) mantig'i */
(function () {
  const { api, t, esc, money, fmtDate, toast, showModal, errMsg, applyTheme, copyText } = window.H;
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

  const S = {
    user: null,
    pub: null,
    tab: "home",
    providers: [],
    products: [],
    providerFilter: "",
    productsLoadedAt: 0,
    balance: null,
    themePref: "auto",
  };

  const $ = (id) => document.getElementById(id);

  /* ------------------------------------------------ init */
  async function boot() {
    if (tg) { tg.ready(); tg.expand(); tg.disableVerticalSwipes && tg.disableVerticalSwipes(); }
    try {
      const initData = tg ? tg.initData || "" : "";
      if (!initData) return showBrowserHint();
      const r = await api.post("/api/auth", { initData });
      S.user = r.user;
      S.pub = r.public;
      S.themePref = S.user.theme || "auto";
      pickLang();
      applyTheme(S.themePref);
      $("app").classList.remove("hidden");
      $("boot").classList.add("hidden");
      afterAuth();
    } catch (e) {
      if (e.code === "USER_BLOCKED") {
        showBlocked();
      } else {
        showBrowserHint(e.code === "UNAUTHORIZED" ? "" : errMsg(e));
      }
    }
  }

  function pickLang() {
    const saved = localStorage.getItem("hy_lang");
    let lang = saved || "";
    if (!lang && S.user && ["uz", "ru", "en"].includes(S.user.lang)) lang = S.user.lang;
    if (!lang && tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
      const lc = (tg.initDataUnsafe.user.language_code || "").slice(0, 2);
      if (["uz", "ru", "en"].includes(lc)) lang = lc;
    }
    if (!lang) lang = (S.pub && S.pub.defaultLang) || "uz";
    window.H.setLang(lang);
  }

  function afterAuth() {
    if (S.pub && S.pub.appName) {
      $("brandName").textContent = S.pub.appName;
      document.title = S.pub.appName;
    }
    document.querySelectorAll("#tabbar .tab").forEach((b) => {
      b.addEventListener("click", () => switchTab(b.dataset.tab));
    });
    $("themeBtn").addEventListener("click", toggleTheme);
    updateThemeBtn();
    if (S.pub && S.pub.maintenance) {
      showModal(maintenanceHtml(), { center: true, sticky: true });
    }
    switchTab("home");
  }

  function bootLang() {
    try {
      const lc = tg && tg.initDataUnsafe && tg.initDataUnsafe.user
        ? (tg.initDataUnsafe.user.language_code || "").slice(0, 2) : "";
      if (["uz", "ru", "en"].includes(lc)) window.H.setLang(lc);
      else window.H.setLang(localStorage.getItem("hy_lang") || "uz");
    } catch (e) { /* */ }
  }

  function showBrowserHint(extra) {
    bootLang();
    $("boot").innerHTML =
      '<img src="/img/logo.png" alt="">' +
      '<div class="soft" style="max-width:340px;padding:22px;text-align:center;margin:0 18px">' +
      '<div style="font-weight:700;margin-bottom:8px">' + esc(extra || t("err.browser")) + "</div>" +
      '<div class="small muted">Hamyon</div></div>';
  }

  function showBlocked() {
    bootLang();
    $("boot").innerHTML =
      '<img src="/img/logo.png" alt="">' +
      '<div class="soft" style="max-width:340px;padding:22px;text-align:center;margin:0 18px">' +
      '<div style="font-weight:700">' + esc(t("err.blocked")) + "</div></div>";
  }

  function maintenanceHtml() {
    return '<div class="modal-title">' + esc(t("mt.title")) + "</div>" +
      '<p class="muted">' + esc(t("home.maintenance")) + "</p>";
  }

  /* ------------------------------------------------ tema */
  function toggleTheme() {
    const cur = document.body.getAttribute("data-theme");
    S.themePref = cur === "dark" ? "light" : "dark";
    applyTheme(S.themePref);
    updateThemeBtn();
    api.post("/api/prefs", { theme: S.themePref }).catch(() => {});
  }

  function updateThemeBtn() {
    const dark = document.body.getAttribute("data-theme") === "dark";
    document.querySelector("#themeBtn .sun-ic").classList.toggle("hidden", dark);
    document.querySelector("#themeBtn .moon-ic").classList.toggle("hidden", !dark);
  }

  /* ------------------------------------------------ tablар */
  function switchTab(name) {
    S.tab = name;
    document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
    $("page-" + name).classList.add("active");
    document.querySelectorAll("#tabbar .tab").forEach((b) =>
      b.classList.toggle("active", b.dataset.tab === name)
    );
    if (name === "home") renderHome();
    if (name === "catalog") renderCatalog();
    if (name === "wallet") renderWallet();
    if (name === "orders") renderOrders();
    if (name === "profile") renderProfile();
  }

  const skeletonRows = (n) =>
    Array.from({ length: n }).map(() => '<div class="skeleton" style="height:76px;margin-bottom:12px"></div>').join("");

  /* ------------------------------------------------ Bosh sahifa */
  async function renderHome() {
    const name = esc(S.user.firstName || S.user.username || "");
    $("page-home").innerHTML =
      '<div class="hero-card soft">' +
      '<img src="' + esc((S.pub && S.pub.startPhoto) || "/img/hero.png") + '" alt="">' +
      '<div class="hero-overlay"><h2>' + t("home.hello", { name }) + "</h2>" +
      "<p>" + esc(t("home.sub")) + "</p></div></div>" +
      (S.pub && !S.pub.apiConfigured && S.user.role === "admin"
        ? '<div class="soft-flat card small" style="color:var(--warn)">' + esc(t("home.setupBanner")) + "</div>"
        : "") +
      '<div class="card soft balance-card">' +
      '<div class="balance-label">' + esc(t("home.balance")) + "</div>" +
      '<div class="balance-value" id="homeBalance">… <small>USD</small></div>' +
      '<div style="display:flex;gap:10px;margin-top:12px">' +
      '<button class="btn btn-primary btn-sm" style="flex:1" onclick="window.__go(\'catalog\')">' + esc(t("home.quickCatalog")) + "</button>" +
      '<button class="btn btn-sm" style="flex:1" onclick="window.__go(\'wallet\')">' + esc(t("home.quickWallet")) + "</button>" +
      "</div></div>" +
      '<div class="section-title">' + esc(t("home.featured")) + "</div>" +
      '<div id="featured">' + skeletonRows(3) + "</div>";

    window.__go = switchTab;

    loadBalance().then((b) => {
      const el = $("homeBalance");
      if (el && b) el.innerHTML = esc(money(b.balance)) + " <small>" + esc(b.currency || "USD") + "</small>";
    });

    try {
      const products = await loadProducts();
      const box = $("featured");
      if (!box) return;
      box.innerHTML = products.slice(0, 4).map(productRowHtml).join("") ||
        '<div class="empty-state">' + esc(t("cat.empty")) + "</div>";
      bindProductRows(box);
    } catch (e) {
      const box = $("featured");
      if (box) box.innerHTML = '<div class="empty-state">' + esc(errMsg(e)) + "</div>";
    }
  }

  async function loadBalance() {
    try {
      S.balance = await api.get("/api/balance");
      return S.balance;
    } catch (e) {
      return null;
    }
  }

  /* ------------------------------------------------ Katalog */
  async function loadProducts(force) {
    if (!force && S.products.length && Date.now() - S.productsLoadedAt < 60000) return S.products;
    const r = await api.get("/api/products");
    S.products = r.data || [];
    S.productsLoadedAt = Date.now();
    return S.products;
  }

  function providerEmoji(p) {
    const em = p.emoji || {};
    return em.normal || "";
  }

  async function renderCatalog() {
    $("page-catalog").innerHTML =
      '<div class="section-title">' + esc(t("cat.providers")) + "</div>" +
      '<div class="chips" id="providerChips"><div class="skeleton" style="height:38px;width:130px;flex:0 0 auto"></div></div>' +
      '<div class="section-title">' + esc(t("cat.products")) + "</div>" +
      '<div id="productList">' + skeletonRows(4) + "</div>";

    try {
      const prov = await api.get("/api/providers");
      S.providers = prov.data || [];
    } catch (e) { S.providers = []; }

    const chips = $("providerChips");
    if (chips) {
      chips.innerHTML =
        '<button class="chip' + (S.providerFilter ? "" : " active") + '" data-p="">' + esc(t("c.all")) + "</button>" +
        S.providers.map((p) =>
          '<button class="chip' + (S.providerFilter === p.key ? " active" : "") + '" data-p="' + esc(p.key) + '">' +
          (providerEmoji(p) ? esc(providerEmoji(p)) + " " : "") + esc(p.name) + "</button>"
        ).join("");
      chips.querySelectorAll(".chip").forEach((c) =>
        c.addEventListener("click", () => {
          S.providerFilter = c.dataset.p;
          renderCatalog();
        })
      );
    }

    try {
      const products = await loadProducts();
      const list = $("productList");
      if (!list) return;
      const filtered = S.providerFilter
        ? products.filter((p) => (p.provider || {}).key === S.providerFilter)
        : products;
      list.innerHTML = filtered.map(productRowHtml).join("") ||
        '<div class="empty-state"><svg><use href="#i-box"/></svg>' + esc(t("cat.empty")) + "</div>";
      bindProductRows(list);
    } catch (e) {
      const list = $("productList");
      if (list) list.innerHTML = '<div class="empty-state">' + esc(errMsg(e)) + "</div>";
    }
  }

  function productRowHtml(p) {
    const stock = p.stock || {};
    const prov = p.provider || {};
    const emoji = ((p.emoji || {}).normal) || ((prov.emoji || {}).normal) || "";
    const out = stock.inStock === false;
    return (
      '<div class="product-row soft-flat" data-ref="' + esc(p.slug || p.id) + '">' +
      '<div class="product-icon">' + (emoji ? esc(emoji) : '<svg style="width:26px;height:26px;color:var(--accent)"><use href="#i-box"/></svg>') + "</div>" +
      '<div class="product-info"><div class="product-name">' + esc(p.name || p.slug) + "</div>" +
      '<div class="product-meta">' +
      (out
        ? '<span class="badge err">' + esc(t("cat.out")) + "</span>"
        : '<span class="badge ok">' + esc(t("cat.inStock")) + "</span>") +
      (p.durationDays ? '<span>' + esc(t("cat.duration")) + ": " + p.durationDays + " " + esc(t("cat.days")) + "</span>" : "") +
      "</div></div>" +
      '<div class="product-price">$' + esc(money(p.yourPrice)) + "</div></div>"
    );
  }

  function bindProductRows(box) {
    box.querySelectorAll(".product-row").forEach((r) =>
      r.addEventListener("click", () => openProduct(r.dataset.ref))
    );
  }

  /* ------------------------------------------------ Mahsulot oynasi */
  async function openProduct(ref) {
    const m = showModal('<div class="modal-handle"></div><div class="skeleton" style="height:120px"></div>', {});
    let p;
    try {
      const r = await api.get("/api/products/" + encodeURIComponent(ref));
      p = r.product;
    } catch (e) {
      m.close();
      toast(errMsg(e), "err");
      return;
    }
    const stock = p.stock || {};
    const maxQty = Math.max(1, Math.min(stock.maxQuantity || stock.count || 50, (S.pub && S.pub.quantityMax) || 50));
    const sensitive = (p.flags || {}).sensitiveDelivery || p.deliveryType === "READY_ACCOUNT";
    let qty = 1;

    const unitPrice = () => tierPrice(p, qty);
    const totalHtml = () => '<div class="kv"><span class="k">' + esc(t("cat.total")) + '</span><span class="v" id="prdTotal">$' + money(unitPrice() * qty) + "</span></div>";

    m.el.querySelector(".modal-card").innerHTML =
      '<div class="modal-handle"></div>' +
      '<div class="modal-title"><span>' + esc(p.name || "") + "</span>" +
      '<button class="modal-close" id="prdClose">&times;</button></div>' +
      (stock.inStock === false ? '<div class="badge err" style="margin-bottom:10px">' + esc(t("cat.out")) + "</div>" : "") +
      (p.description ? '<div class="soft-inset" style="padding:13px;font-size:13.5px;margin-bottom:12px">' + esc(p.description) + "</div>" : "") +
      '<div class="soft-flat" style="padding:6px 14px;margin-bottom:12px">' +
      '<div class="kv"><span class="k">' + esc(t("cat.unit")) + '</span><span class="v">$' + esc(money(p.yourPrice)) + "</span></div>" +
      (stock.count != null ? '<div class="kv"><span class="k">' + esc(t("cat.stock")) + '</span><span class="v">' + esc(stock.count) + "</span></div>" : "") +
      (p.durationDays ? '<div class="kv"><span class="k">' + esc(t("cat.duration")) + '</span><span class="v">' + p.durationDays + " " + esc(t("cat.days")) + "</span></div>" : "") +
      ((p.warranty || {}).enabled ? '<div class="kv"><span class="k">' + esc(t("cat.warranty")) + '</span><span class="v">' + p.warranty.days + " " + esc(t("cat.days")) + "</span></div>" : "") +
      '<div class="kv"><span class="k">' + esc(t("ord.type")) + '</span><span class="v">' + esc(t("typ." + p.deliveryType) || p.deliveryType) + "</span></div>" +
      "</div>" +
      (bulkHtml(p) || "") +
      (sensitive ? '<div class="small" style="color:var(--warn);margin-bottom:12px">' + esc(t("cat.sensitive")) + "</div>" : "") +
      (stock.inStock !== false
        ? '<div class="soft-flat" style="padding:14px;margin-bottom:14px">' +
          '<div class="field"><label>' + esc(t("cat.qty")) + "</label>" +
          '<div class="stepper"><button id="qMinus">−</button><div class="val" id="qVal">1</div><button id="qPlus">+</button>' +
          '<div style="flex:1"></div><span class="small muted">' + esc(t("cat.unit")) + ': <b id="prdUnit">$' + money(unitPrice()) + "</b></span></div></div>" +
          '<div class="soft-flat" style="padding:4px 14px;margin-bottom:14px">' + totalHtml() + "</div>" +
          '<button class="btn btn-primary btn-block" id="buyBtn">' + esc(t("cat.order")) + "</button>"
        : "") +
      (p.instructions ? '<div class="small muted" style="margin-top:12px"><b>' + esc(t("cat.instructions")) + ":</b> " + esc(p.instructions) + "</div>" : "");

    m.el.querySelector("#prdClose").addEventListener("click", m.close);
    if (stock.inStock === false) return;

    const qEl = m.el.querySelector("#qVal");
    const unitEl = m.el.querySelector("#prdUnit");
    const upd = () => {
      qEl.textContent = qty;
      unitEl.textContent = "$" + money(unitPrice());
      m.el.querySelector("#prdTotal").textContent = "$" + money(unitPrice() * qty);
    };
    m.el.querySelector("#qMinus").addEventListener("click", () => { qty = Math.max(1, qty - 1); upd(); });
    m.el.querySelector("#qPlus").addEventListener("click", () => { qty = Math.min(maxQty, qty + 1); upd(); });
    m.el.querySelector("#buyBtn").addEventListener("click", () => placeOrder(p, qty, m));
  }

  function tierPrice(p, qty) {
    const bd = p.bulkDiscount || {};
    if (bd.enabled && Array.isArray(bd.tiers)) {
      let best = null;
      for (const tr of bd.tiers) {
        const min = tr.minQuantity || 1;
        const max = tr.maxQuantity == null ? Infinity : tr.maxQuantity;
        if (qty >= min && qty <= max) {
          const pr = Number(tr.unitPrice);
          if (best === null || pr < best) best = pr;
        }
      }
      if (best !== null) return best;
    }
    const base = Number(p.yourPrice != null ? p.yourPrice : (p.pricing || {}).yourUnitPrice);
    return isFinite(base) ? base : 0;
  }

  function bulkHtml(p) {
    const bd = p.bulkDiscount || {};
    if (!bd.enabled || !Array.isArray(bd.tiers) || !bd.tiers.length) return "";
    return '<div class="soft-inset" style="padding:12px 14px;margin-bottom:12px">' +
      '<div class="small" style="font-weight:700;margin-bottom:7px">' + esc(t("cat.bulk")) + "</div>" +
      bd.tiers.map((tr) =>
        '<div class="kv" style="padding:5px 0"><span class="k">' + tr.minQuantity + "+" + esc(t("cat.perUnit")) + "</span>" +
        '<span class="v">$' + money(tr.unitPrice) + "</span></div>"
      ).join("") + "</div>";
  }

  /* ------------------------------------------------ Buyurtma berish */
  async function placeOrder(product, qty, productModal) {
    const btn = productModal.el.querySelector("#buyBtn");
    btn.disabled = true;
    btn.textContent = t("cat.placing");
    try {
      const r = await api.post("/api/orders", { productSlug: product.slug, quantity: qty });
      productModal.close();
      showOrderResult(r);
    } catch (e) {
      btn.disabled = false;
      btn.textContent = t("cat.order");
      toast(errMsg(e), "err");
    }
  }

  function deliveryBlockHtml(d, type) {
    if (!d) return "";
    let body = "";
    if (d.link) {
      body = '<div class="delivery-box soft-inset">' + esc(d.link) + "</div>" +
        '<div style="display:flex;gap:8px">' +
        '<button class="btn btn-sm" data-copy="' + esc(d.link) + '">' + esc(t("c.copy")) + "</button>" +
        '<a class="btn btn-primary btn-sm" href="' + esc(d.link) + '" target="_blank" rel="noopener">' + esc(t("ord.open")) + "</a></div>";
    } else if (d.code) {
      body = '<div class="delivery-box soft-inset" style="font-size:16px;font-weight:800;letter-spacing:1px">' + esc(d.code) + "</div>" +
        '<button class="btn btn-sm" data-copy="' + esc(d.code) + '">' + esc(t("c.copy")) + "</button>";
    } else if (d.content) {
      body = '<div class="delivery-box soft-inset" id="accContent" data-real="' + esc(d.content) + '">' +
        "•".repeat(14) + "</div>" +
        '<div style="display:flex;gap:8px">' +
        '<button class="btn btn-sm" id="accToggle">' + esc(t("ord.show")) + "</button>" +
        '<button class="btn btn-sm" data-copy="' + esc(d.content) + '">' + esc(t("c.copy")) + "</button></div>";
    }
    const instr = d.instructions ? '<div class="small muted" style="margin-top:10px">' + esc(d.instructions) + "</div>" : "";
    return body + instr;
  }

  function bindDeliveryActions(root) {
    root.querySelectorAll("[data-copy]").forEach((b) =>
      b.addEventListener("click", () => copyText(b.getAttribute("data-copy")))
    );
    const tog = root.querySelector("#accToggle");
    const content = root.querySelector("#accContent");
    if (tog && content) {
      const real = content.getAttribute("data-real") || "";
      let masked = true;
      tog.addEventListener("click", () => {
        masked = !masked;
        content.textContent = masked ? "•".repeat(14) : real;
        tog.textContent = masked ? t("ord.show") : t("ord.hide");
      });
    }
  }

  function showOrderResult(r) {
    const isBulk = Array.isArray(r.lines) && r.lines.length > 0;
    let deliveryHtml = "";
    if (isBulk) {
      deliveryHtml = '<div class="small" style="font-weight:700;margin-bottom:8px">' + esc(t("ord.lines")) + " (" + r.lines.length + ")</div>" +
        r.lines.map((l) => {
          const val = l.code || l.link || l.content || "";
          return '<div class="soft-inset" style="padding:11px;margin-bottom:8px">' +
            '<div class="small muted">' + esc(l.orderCode || "") + "</div>" +
            '<div class="delivery-box" style="margin:6px 0 8px">' + esc(val) + "</div>" +
            '<button class="btn btn-sm" data-copy="' + esc(val) + '">' + esc(t("c.copy")) + "</button></div>";
        }).join("");
    } else {
      deliveryHtml = deliveryBlockHtml(r.delivery, r.deliveryType);
    }

    const m = showModal(
      '<div class="modal-handle"></div>' +
      '<div class="modal-title"><span>' + esc(t("ord.success")) + '</span><button class="modal-close" id="resClose">&times;</button></div>' +
      '<div class="soft-flat" style="padding:6px 14px;margin-bottom:12px">' +
      '<div class="kv"><span class="k">' + esc(t("ord.code")) + '</span><span class="v">' + esc(r.orderCode || "") + "</span></div>" +
      '<div class="kv"><span class="k">' + esc(t("ord.type")) + '</span><span class="v">' + esc(t("typ." + r.deliveryType) || r.deliveryType || "—") + "</span></div>" +
      '<div class="kv"><span class="k">' + esc(t("ord.qty")) + '</span><span class="v">' + esc(r.quantity || 1) + "</span></div>" +
      '<div class="kv"><span class="k">' + esc(t("ord.total")) + '</span><span class="v">$' + esc(money(r.totalCharged)) + "</span></div>" +
      (r.balanceAfter != null ? '<div class="kv"><span class="k">' + esc(t("ord.balanceAfter")) + '</span><span class="v">$' + esc(money(r.balanceAfter)) + "</span></div>" : "") +
      "</div>" +
      '<div class="section-title" style="margin-top:6px">' + esc(t("ord.delivery")) + "</div>" +
      deliveryHtml,
      {}
    );
    m.el.querySelector("#resClose").addEventListener("click", m.close);
    bindDeliveryActions(m.el);
  }

  /* ------------------------------------------------ Hamyon */
  async function renderWallet() {
    $("page-wallet").innerHTML =
      '<div class="card soft balance-card">' +
      '<div class="balance-label">' + esc(t("wal.title")) + "</div>" +
      '<div class="balance-value" id="walBalance">… <small>USD</small></div></div>' +
      '<div class="section-title">' + esc(t("wal.topup")) + "</div>" +
      '<div class="card soft-flat" id="depositCard"></div>' +
      '<div class="section-title">' + esc(t("wal.stats")) + "</div>" +
      '<div id="usageBox"><div class="skeleton" style="height:120px"></div></div>';

    loadBalance().then((b) => {
      const el = $("walBalance");
      if (el) el.innerHTML = b ? esc(money(b.balance)) + " <small>" + esc(b.currency || "USD") + "</small>" : "—";
    });

    const dep = (S.pub && S.pub.deposit) || {};
    const depEl = $("depositCard");
    const depImg = '<img src="/img/wallet.png" style="width:100%;border-radius:16px;margin-bottom:12px" alt="">';
    if (dep.address) {
      depEl.innerHTML = depImg +
        (dep.network ? '<div class="kv"><span class="k">' + esc(t("wal.network")) + '</span><span class="v">' + esc(dep.network) + "</span></div>" : "") +
        '<div class="kv"><span class="k">' + esc(t("wal.address")) + '</span><span class="v small" style="max-width:190px">' + esc(dep.address) + "</span></div>" +
        (dep.note ? '<div class="kv"><span class="k">' + esc(t("wal.note")) + '</span><span class="v small">' + esc(dep.note) + "</span></div>" : "") +
        '<button class="btn btn-primary btn-sm" style="margin-top:10px" data-copy="' + esc(dep.address) + '">' + esc(t("c.copy")) + "</button>";
      depEl.querySelectorAll("[data-copy]").forEach((b) =>
        b.addEventListener("click", () => copyText(b.getAttribute("data-copy")))
      );
    } else {
      depEl.innerHTML = depImg + '<div class="small muted">' + esc(t("wal.topupNote")) + "</div>";
    }

    try {
      const u = await api.get("/api/usage");
      const box = $("usageBox");
      if (!box) return;
      box.innerHTML = '<div class="stat-grid">' +
        statCell(money(u.apiOrdersTotal), t("wal.ordersTotal")) +
        statCell("$" + money(u.apiSpendTotal), t("wal.spendTotal")) +
        statCell(money(u.apiOrders24h), t("wal.orders24")) +
        statCell("$" + money(u.apiSpend24h), t("wal.spend24")) +
        statCell(money(u.requestCountToday), t("wal.reqToday")) +
        statCell(money(u.errorCountToday), t("wal.errToday")) +
        "</div>";
    } catch (e) {
      const box = $("usageBox");
      if (box) box.innerHTML = '<div class="empty-state">' + esc(errMsg(e)) + "</div>";
    }
  }

  const statCell = (v, k) =>
    '<div class="stat-cell soft-flat"><div class="v">' + esc(v) + '</div><div class="k">' + esc(k) + "</div></div>";

  /* ------------------------------------------------ Buyurtmalar */
  async function renderOrders() {
    $("page-orders").innerHTML =
      '<div class="section-title">' + esc(t("ord.title")) + "</div>" +
      '<div id="ordersList">' + skeletonRows(3) + "</div>";
    try {
      const r = await api.get("/api/orders?limit=50");
      const box = $("ordersList");
      if (!box) return;
      const rows = r.data || [];
      box.innerHTML = rows.length
        ? rows.map(orderRowHtml).join("")
        : '<div class="empty-state"><svg><use href="#i-receipt"/></svg>' + esc(t("ord.empty")) + "</div>";
      box.querySelectorAll(".order-row").forEach((el) =>
        el.addEventListener("click", () => openOrderDetail(el.dataset.code))
      );
    } catch (e) {
      const box = $("ordersList");
      if (box) box.innerHTML = '<div class="empty-state">' + esc(errMsg(e)) + "</div>";
    }
  }

  function orderRowHtml(o) {
    return '<div class="order-row soft-flat" data-code="' + esc(o.orderCode) + '">' +
      '<div class="top"><span class="code">' + esc(o.product.name || o.product.slug || o.orderCode) + "</span>" +
      '<span class="badge ok">' + esc(t("st." + (o.status || "")) || o.status || "") + "</span></div>" +
      '<div class="sub"><span>' + esc(o.orderCode) + "</span><span>$" + esc(money(o.totalCharged)) + "</span>" +
      "<span>" + esc(fmtDate(o.createdAt)) + "</span></div></div>";
  }

  async function openOrderDetail(code) {
    const m = showModal('<div class="modal-handle"></div><div class="skeleton" style="height:100px"></div>', {});
    try {
      const r = await api.get("/api/orders/" + encodeURIComponent(code));
      const isBulk = Array.isArray(r.lines) && r.lines.length;
      m.el.querySelector(".modal-card").innerHTML =
        '<div class="modal-handle"></div>' +
        '<div class="modal-title"><span>' + esc(r.orderCode || code) + '</span><button class="modal-close" id="odClose">&times;</button></div>' +
        '<div class="soft-flat" style="padding:6px 14px;margin-bottom:12px">' +
        '<div class="kv"><span class="k">' + esc(t("ord.status")) + '</span><span class="v">' + esc(t("st." + (r.status || "")) || r.status || "—") + "</span></div>" +
        '<div class="kv"><span class="k">' + esc(t("ord.type")) + '</span><span class="v">' + esc(t("typ." + r.deliveryType) || r.deliveryType || "—") + "</span></div>" +
        '<div class="kv"><span class="k">' + esc(t("ord.qty")) + '</span><span class="v">' + esc(r.quantity) + "</span></div>" +
        '<div class="kv"><span class="k">' + esc(t("ord.unit")) + '</span><span class="v">$' + esc(money(r.unitPrice)) + "</span></div>" +
        '<div class="kv"><span class="k">' + esc(t("ord.total")) + '</span><span class="v">$' + esc(money(r.totalCharged)) + "</span></div>" +
        '<div class="kv"><span class="k">' + esc(t("ord.date")) + '</span><span class="v">' + esc(fmtDate(r.createdAt)) + "</span></div>" +
        "</div>" +
        '<div class="section-title" style="margin-top:4px">' + esc(t("ord.delivery")) + "</div>" +
        (isBulk
          ? r.lines.map((l) => {
              const val = l.code || l.link || l.content || "";
              return '<div class="soft-inset" style="padding:11px;margin-bottom:8px"><div class="small muted">' + esc(l.orderCode || "") +
                '</div><div class="delivery-box" style="margin:6px 0 8px">' + esc(val) + "</div>" +
                '<button class="btn btn-sm" data-copy="' + esc(val) + '">' + esc(t("c.copy")) + "</button></div>";
            }).join("")
          : deliveryBlockHtml(r.delivery, r.deliveryType) || '<div class="small muted">—</div>');
      m.el.querySelector("#odClose").addEventListener("click", m.close);
      bindDeliveryActions(m.el);
    } catch (e) {
      m.close();
      toast(errMsg(e), "err");
    }
  }

  /* ------------------------------------------------ Profil */
  function renderProfile() {
    const u = S.user;
    const lang = window.H.currentLang();
    const theme = S.themePref || "auto";
    $("page-profile").innerHTML =
      '<div class="card soft" style="display:flex;align-items:center;gap:14px">' +
      '<div class="product-icon" style="width:58px;height:58px;border-radius:50%"><svg style="width:30px;height:30px;color:var(--accent)"><use href="#i-user"/></svg></div>' +
      '<div><div style="font-weight:800;font-size:16px">' + esc(u.firstName || "") + " " + esc(u.lastName || "") + "</div>" +
      '<div class="small muted">' + (u.username ? "@" + esc(u.username) : esc(t("c.notSet"))) + "</div>" +
      '<div style="margin-top:6px"><span class="badge">' + esc(u.role === "admin" ? t("prof.roleAdmin") : t("prof.roleUser")) + "</span></div></div></div>" +
      '<div class="card soft-flat">' +
      '<div class="field"><label>' + esc(t("prof.lang")) + "</label>" +
      '<div class="segmented" id="langSeg">' +
      seg("uz", "O'zbekcha", lang) + seg("ru", "Русский", lang) + seg("en", "English", lang) +
      "</div></div>" +
      '<div class="field" style="margin-bottom:4px"><label>' + esc(t("prof.theme")) + "</label>" +
      '<div class="segmented" id="themeSeg">' +
      seg("light", t("prof.light"), theme) + seg("dark", t("prof.dark"), theme) + seg("auto", t("prof.auto"), theme) +
      "</div></div></div>" +
      '<div class="card soft-flat">' +
      '<div class="kv"><span class="k">' + esc(t("prof.since")) + '</span><span class="v">' + esc(fmtDate(u.createdAt)) + "</span></div>" +
      "</div>" +
      ((S.pub && S.pub.supportUrl)
        ? '<a class="btn btn-block" style="margin-bottom:12px" href="' + esc(S.pub.supportUrl) + '" target="_blank" rel="noopener">' + esc(t("prof.support")) + "</a>"
        : "") +
      (u.role === "admin" ? '<a class="btn btn-primary btn-block" href="/admin">' + esc(t("prof.admin")) + "</a>" : "");

    $("langSeg").querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => {
        window.H.setLang(b.dataset.v);
        api.post("/api/prefs", { lang: b.dataset.v }).catch(() => {});
        renderProfile();
        renderStaticBits();
      })
    );
    $("themeSeg").querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => {
        S.themePref = b.dataset.v;
        applyTheme(S.themePref);
        updateThemeBtn();
        api.post("/api/prefs", { theme: S.themePref }).catch(() => {});
        renderProfile();
      })
    );
  }

  const seg = (v, label, cur) =>
    '<button data-v="' + v + '" class="' + (cur === v ? "active" : "") + '">' + esc(label) + "</button>";

  function renderStaticBits() {
    updateThemeBtn();
  }

  boot();
})();
