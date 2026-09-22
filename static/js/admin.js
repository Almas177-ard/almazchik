/* Hamyon — Admin panel mantig'i */
(function () {
  const { api, t, esc, money, fmtDate, toast, showModal, errMsg } = window.H;
  const $ = (id) => document.getElementById(id);

  const TITLES = {
    dash: "adm.navDash",
    settings: "adm.navSettings",
    users: "adm.navUsers",
    orders: "adm.navOrders",
    catalog: "adm.navCatalog",
    texts: "adm.navTexts",
    images: "adm.navImages",
  };

  let section = "dash";

  /* ------------------------------------------------ init */
  async function boot() {
    const savedTheme = localStorage.getItem("hy_admin_theme") ||
      (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    window.H.applyTheme(savedTheme);
    updateThemeBtn();

    const savedLang = localStorage.getItem("hy_lang") || "uz";
    window.H.setLang(savedLang);
    $("admLang").value = window.H.currentLang();

    $("admLang").addEventListener("change", () => {
      window.H.setLang($("admLang").value);
      render();
    });
    $("admThemeBtn").addEventListener("click", () => {
      const cur = document.body.getAttribute("data-theme") === "dark" ? "light" : "dark";
      localStorage.setItem("hy_admin_theme", cur);
      window.H.applyTheme(cur);
      updateThemeBtn();
    });
    $("loginBtn").addEventListener("click", doLogin);
    $("loginPass").addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });
    $("admLogout").addEventListener("click", async () => {
      try { await api.post("/admin/api/logout"); } catch (e) {}
      location.reload();
    });
    $("openSiteBtn").addEventListener("click", () => { window.open("/", "_blank"); });

    document.querySelectorAll(".nav-item[data-section]").forEach((b) =>
      b.addEventListener("click", () => {
        section = b.dataset.section;
        document.querySelectorAll(".nav-item[data-section]").forEach((x) =>
          x.classList.toggle("active", x === b)
        );
        render();
      })
    );

    try {
      await api.get("/admin/api/me");
      showPanel();
    } catch (e) {
      $("loginScreen").classList.remove("hidden");
    }
  }

  function updateThemeBtn() {
    const dark = document.body.getAttribute("data-theme") === "dark";
    document.querySelector("#admThemeBtn .sun-ic").classList.toggle("hidden", dark);
    document.querySelector("#admThemeBtn .moon-ic").classList.toggle("hidden", !dark);
  }

  async function doLogin() {
    const btn = $("loginBtn");
    btn.disabled = true;
    try {
      await api.post("/admin/api/login", { password: $("loginPass").value });
      showPanel();
    } catch (e) {
      toast(t("adm.loginErr"), "err");
    }
    btn.disabled = false;
  }

  function showPanel() {
    $("loginScreen").classList.add("hidden");
    $("adminApp").classList.remove("hidden");
    render();
  }

  function render() {
    window.H.applyI18n(document);
    $("admTitle").textContent = t(TITLES[section] || "adm.navDash");
    const c = $("adminContent");
    c.innerHTML = "";
    if (section === "dash") renderDash(c);
    if (section === "settings") renderSettings(c);
    if (section === "users") renderUsers(c);
    if (section === "orders") renderOrders(c);
    if (section === "catalog") renderCatalog(c);
    if (section === "texts") renderTexts(c);
    if (section === "images") renderImages(c);
  }

  /* ------------------------------------------------ Dashboard */
  async function renderDash(c) {
    c.innerHTML = '<div class="skeleton" style="height:150px;margin-bottom:16px"></div>';
    try {
      const d = await api.get("/admin/api/dashboard");
      const st = d.stats || {};
      c.innerHTML =
        '<div class="admin-grid" style="margin-bottom:18px">' +
        card(t("adm.users"), st.usersTotal, "+" + st.users24h) +
        card(t("adm.orders"), st.ordersTotal, "+" + st.orders24h + " / 24h") +
        card(t("adm.spend24"), "$" + money(st.spend24h), "") +
        card(t("adm.balance"), d.balance ? "$" + money(d.balance.balance) : "—", d.balance ? d.balance.currency : "") +
        "</div>" +
        '<div class="panel-card soft">' +
        "<h3>" + esc(t("adm.api")) + "</h3>" +
        '<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">' +
        '<span class="badge ' + (d.apiOnline ? "ok" : "err") + '">' + esc(d.apiOnline ? t("adm.online") : t("adm.offline")) + "</span>" +
        '<button class="btn btn-sm" id="dashSync">' + esc(t("adm.sync")) + "</button>" +
        "</div>" +
        '<hr style="border:none;border-top:1px dashed var(--card-2);margin:16px 0">' +
        "<h3>" + esc(t("adm.maint")) + " — " +
        '<span class="badge ' + (d.maintenance ? "warn" : "ok") + '">' + esc(d.maintenance ? t("adm.on") : t("adm.off")) + "</span></h3>" +
        '<p class="small muted" style="margin-bottom:12px">' + esc(t("adm.maintDesc")) + "</p>" +
        '<label class="switch"><input type="checkbox" id="maintSw" ' + (d.maintenance ? "checked" : "") + ">" +
        '<span class="track"><span class="thumb"></span></span></label>' +
        "</div>";
      c.querySelector("#maintSw").addEventListener("change", async (e) => {
        try {
          await api.post("/admin/api/settings", { maintenance: e.target.checked ? "1" : "0" });
          toast(t("c.saved"), "ok");
        } catch (err) { toast(errMsg(err), "err"); }
        renderDash(c);
      });
      c.querySelector("#dashSync").addEventListener("click", async () => {
        const b = c.querySelector("#dashSync");
        b.disabled = true; b.textContent = t("adm.syncing");
        try {
          await api.post("/admin/api/catalog/sync");
          toast(t("adm.synced"), "ok");
        } catch (err) { toast(errMsg(err), "err"); }
        b.disabled = false; b.textContent = t("adm.sync");
      });
    } catch (e) {
      c.innerHTML = '<div class="panel-card soft">' + esc(errMsg(e)) + "</div>";
    }
  }

  const card = (k, v, sub) =>
    '<div class="panel-card soft" style="margin-bottom:0"><div class="small muted" style="font-weight:700">' + esc(k) +
    '</div><div style="font-size:24px;font-weight:800;margin-top:6px">' + esc(String(v)) +
    '</div>' + (sub ? '<div class="small" style="color:var(--accent);font-weight:700;margin-top:3px">' + esc(sub) + "</div>" : "") + "</div>";

  /* ------------------------------------------------ Sozlamalar */
  async function renderSettings(c) {
    c.innerHTML = '<div class="skeleton" style="height:220px"></div>';
    let s;
    try {
      s = (await api.get("/admin/api/settings")).settings;
    } catch (e) {
      c.innerHTML = '<div class="panel-card soft">' + esc(errMsg(e)) + "</div>";
      return;
    }
    const f = (key, label, type, ph) =>
      '<div class="field"><label>' + esc(label) + '</label><input class="input" type="' + (type || "text") +
      '" id="s_' + key + '" value="' + esc(s[key] || "") + '"' + (ph ? ' placeholder="' + esc(ph) + '"' : "") + "></div>";

    c.innerHTML =
      '<div class="panel-card soft"><h3>' + esc(t("adm.apiSettings")) + "</h3>" +
      f("partner_base_url", t("adm.baseUrl"), "text", "https://hamyon-api.uz/api/partner/v1") +
      f("partner_api_key", t("adm.apiKey"), "text", "sk_live_…") +
      '<button class="btn btn-sm" id="revealKey">' + esc(t("adm.reveal")) + "</button></div>" +
      '<div class="panel-card soft"><h3>' + esc(t("adm.appSettings")) + "</h3>" +
      f("app_name", t("adm.appName")) +
      f("webapp_url", t("adm.webappUrl"), "text", "https://…") +
      f("support_url", t("adm.supportUrl"), "text", "https://t.me/…") +
      '<div class="field"><label>' + esc(t("adm.defaultLang")) + '</label><select class="input" id="s_default_lang">' +
      ["uz", "ru", "en"].map((l) => '<option value="' + l + '"' + (s.default_lang === l ? " selected" : "") + ">" + l + "</option>").join("") +
      "</select></div>" +
      f("cache_ttl", t("adm.cacheTtl"), "number") +
      f("order_quantity_max", t("adm.qtyMax"), "number") +
      "</div>" +
      '<div class="panel-card soft"><h3>' + esc(t("adm.deposit")) + "</h3>" +
      f("deposit_network", t("adm.network"), "text", "TRC20 / ERC20 / BEP20") +
      f("deposit_address", t("adm.addr")) +
      f("deposit_note", t("adm.note")) +
      "</div>" +
      '<button class="btn btn-primary btn-block" id="saveSettings" style="margin-bottom:18px">' + esc(t("c.save")) + "</button>" +
      '<div class="panel-card soft"><h3>' + esc(t("adm.security")) + "</h3>" +
      '<div class="field"><label>' + esc(t("adm.curPass")) + '</label><input class="input" type="password" id="curPass"></div>' +
      '<div class="field"><label>' + esc(t("adm.newPass")) + '</label><input class="input" type="password" id="newPass"></div>' +
      '<button class="btn btn-block" id="changePass">' + esc(t("adm.changePass")) + "</button></div>";

    c.querySelector("#revealKey").addEventListener("click", async () => {
      try {
        const r = await api.get("/admin/api/settings?reveal=1");
        c.querySelector("#s_partner_api_key").value = r.settings.partner_api_key || "";
      } catch (e) { toast(errMsg(e), "err"); }
    });

    c.querySelector("#saveSettings").addEventListener("click", async () => {
      const body = {
        partner_base_url: c.querySelector("#s_partner_base_url").value,
        partner_api_key: c.querySelector("#s_partner_api_key").value,
        app_name: c.querySelector("#s_app_name").value,
        webapp_url: c.querySelector("#s_webapp_url").value,
        support_url: c.querySelector("#s_support_url").value,
        default_lang: c.querySelector("#s_default_lang").value,
        cache_ttl: c.querySelector("#s_cache_ttl").value,
        order_quantity_max: c.querySelector("#s_order_quantity_max").value,
        deposit_network: c.querySelector("#s_deposit_network").value,
        deposit_address: c.querySelector("#s_deposit_address").value,
        deposit_note: c.querySelector("#s_deposit_note").value,
      };
      try {
        await api.post("/admin/api/settings", body);
        toast(t("c.saved"), "ok");
      } catch (e) { toast(errMsg(e), "err"); }
    });

    c.querySelector("#changePass").addEventListener("click", async () => {
      try {
        await api.post("/admin/api/password", {
          current: c.querySelector("#curPass").value,
          next: c.querySelector("#newPass").value,
        });
        toast(t("adm.passChanged"), "ok");
        c.querySelector("#curPass").value = "";
        c.querySelector("#newPass").value = "";
      } catch (e) {
        toast(e.code === "WRONG_PASSWORD" ? t("adm.passWrong") : errMsg(e), "err");
      }
    });
  }

  /* ------------------------------------------------ Foydalanuvchilar */
  async function renderUsers(c) {
    c.innerHTML =
      '<div class="panel-card soft">' +
      '<input class="input" id="userSearch" data-i18n-ph="c.search" style="margin-bottom:14px">' +
      '<div class="table-wrap" id="usersTable"><div class="skeleton" style="height:140px"></div></div></div>';
    const input = c.querySelector("#userSearch");
    let tm = null;
    input.addEventListener("input", () => {
      clearTimeout(tm);
      tm = setTimeout(() => loadUsers(c, input.value), 350);
    });
    loadUsers(c, "");
  }

  async function loadUsers(c, q) {
    const box = c.querySelector("#usersTable");
    try {
      const r = await api.get("/admin/api/users?q=" + encodeURIComponent(q) + "&limit=50");
      const rows = r.data || [];
      box.innerHTML = rows.length
        ? '<table class="tbl"><thead><tr><th>ID</th><th>' + esc(t("adm.name")) + "</th><th>" + esc(t("adm.username")) + "</th><th>" +
          esc(t("adm.langC")) + "</th><th>" + esc(t("adm.roleC")) + "</th><th>" + esc(t("adm.stateC")) + "</th><th></th></tr></thead><tbody>" +
          rows.map((u) =>
            "<tr><td>" + esc(u.tg_id) + "</td><td>" + esc(u.first_name || "") + "</td><td>" + (u.username ? "@" + esc(u.username) : "—") +
            "</td><td>" + esc(u.lang) + "</td><td>" + esc(u.role) + "</td><td>" +
            '<span class="badge ' + (u.blocked ? "err" : "ok") + '">' + esc(u.blocked ? t("adm.blocked") : t("adm.active")) + "</span></td>" +
            '<td style="white-space:nowrap">' +
            '<button class="btn btn-sm" data-act="block" data-id="' + u.tg_id + '" data-blocked="' + u.blocked + '">' +
            esc(u.blocked ? t("adm.unblock") : t("adm.block")) + "</button> " +
            '<button class="btn btn-sm" data-act="role" data-id="' + u.tg_id + '" data-role="' + esc(u.role) + '">' +
            esc(u.role === "admin" ? t("adm.makeUser") : t("adm.makeAdmin")) + "</button></td></tr>"
          ).join("") + "</tbody></table>"
        : '<div class="empty-state">' + esc(t("adm.notFound")) + "</div>";
      box.querySelectorAll("button[data-act]").forEach((b) =>
        b.addEventListener("click", async () => {
          const id = b.dataset.id;
          const body = b.dataset.act === "block"
            ? { blocked: b.dataset.blocked === "0" }
            : { role: b.dataset.role === "admin" ? "user" : "admin" };
          try {
            await api.post("/admin/api/users/" + id, body);
            toast(t("c.saved"), "ok");
            loadUsers(c, c.querySelector("#userSearch").value);
          } catch (e) { toast(errMsg(e), "err"); }
        })
      );
    } catch (e) {
      box.innerHTML = '<div class="empty-state">' + esc(errMsg(e)) + "</div>";
    }
  }

  /* ------------------------------------------------ Buyurtmalar */
  async function renderOrders(c) {
    c.innerHTML =
      '<div class="panel-card soft">' +
      '<input class="input" id="ordSearch" data-i18n-ph="c.search" style="margin-bottom:14px">' +
      '<div class="table-wrap" id="ordersTable"><div class="skeleton" style="height:140px"></div></div></div>';
    const input = c.querySelector("#ordSearch");
    let tm = null;
    input.addEventListener("input", () => {
      clearTimeout(tm);
      tm = setTimeout(() => loadOrders(c, input.value), 350);
    });
    loadOrders(c, "");
  }

  async function loadOrders(c, q) {
    const box = c.querySelector("#ordersTable");
    try {
      const r = await api.get("/admin/api/orders?q=" + encodeURIComponent(q) + "&limit=50");
      const rows = r.data || [];
      box.innerHTML = rows.length
        ? '<table class="tbl"><thead><tr><th>' + esc(t("ord.code")) + "</th><th>" + esc(t("adm.user")) + "</th><th>" +
          esc(t("cat.products")) + "</th><th>" + esc(t("ord.qty")) + "</th><th>" + esc(t("ord.total")) + "</th><th>" +
          esc(t("ord.status")) + "</th><th>" + esc(t("ord.date")) + "</th><th></th></tr></thead><tbody>" +
          rows.map((o) =>
            "<tr><td>" + esc(o.order_code) + "</td><td>" + esc(o.tg_id) + "</td><td>" + esc(o.product_name || o.product_slug || "—") +
            "</td><td>" + esc(o.quantity) + '</td><td>$' + esc(money(o.total_charged)) + "</td><td>" + esc(o.status || "—") +
            "</td><td>" + esc(fmtDate(o.created_at)) + '</td><td><button class="btn btn-sm" data-code="' + esc(o.order_code) + '">' +
            esc(t("adm.view")) + "</button></td></tr>"
          ).join("") + "</tbody></table>"
        : '<div class="empty-state">' + esc(t("adm.notFound")) + "</div>";
      box.querySelectorAll("button[data-code]").forEach((b) =>
        b.addEventListener("click", () => openAdminOrder(b.dataset.code))
      );
    } catch (e) {
      box.innerHTML = '<div class="empty-state">' + esc(errMsg(e)) + "</div>";
    }
  }

  async function openAdminOrder(code) {
    const m = showModal('<div class="modal-handle"></div><div class="skeleton" style="height:90px"></div>', {});
    try {
      const r = await api.get("/admin/api/orders/" + encodeURIComponent(code));
      const o = r.order;
      let deliveryHtml = "";
      const dj = o.delivery_json;
      if (dj) {
        if (dj.delivery) {
          const d = dj.delivery;
          const val = d.link || d.code || d.content || "";
          deliveryHtml = '<div class="delivery-box soft-inset">' + esc(val) + "</div>" +
            (d.instructions ? '<div class="small muted">' + esc(d.instructions) + "</div>" : "");
        }
        if (Array.isArray(dj.lines) && dj.lines.length) {
          deliveryHtml += dj.lines.map((l) =>
            '<div class="soft-inset" style="padding:10px;margin-bottom:8px"><div class="small muted">' + esc(l.orderCode || "") +
            '</div><div class="delivery-box" style="margin:5px 0 0">' + esc(l.code || l.link || l.content || "") + "</div></div>"
          ).join("");
        }
      }
      m.el.querySelector(".modal-card").innerHTML =
        '<div class="modal-handle"></div>' +
        '<div class="modal-title"><span>' + esc(o.order_code) + '</span><button class="modal-close" id="aoClose">&times;</button></div>' +
        '<div class="soft-flat" style="padding:6px 14px;margin-bottom:12px">' +
        '<div class="kv"><span class="k">tg_id</span><span class="v">' + esc(o.tg_id) + "</span></div>" +
        '<div class="kv"><span class="k">' + esc(t("cat.products")) + '</span><span class="v">' + esc(o.product_name || o.product_slug || "—") + "</span></div>" +
        '<div class="kv"><span class="k">' + esc(t("ord.qty")) + '</span><span class="v">' + esc(o.quantity) + "</span></div>" +
        '<div class="kv"><span class="k">' + esc(t("ord.unit")) + '</span><span class="v">$' + esc(money(o.unit_price)) + "</span></div>" +
        '<div class="kv"><span class="k">' + esc(t("ord.total")) + '</span><span class="v">$' + esc(money(o.total_charged)) + "</span></div>" +
        '<div class="kv"><span class="k">' + esc(t("ord.status")) + '</span><span class="v">' + esc(o.status || "—") + "</span></div>" +
        '<div class="kv"><span class="k">' + esc(t("ord.date")) + '</span><span class="v">' + esc(fmtDate(o.created_at)) + "</span></div>" +
        "</div>" +
        "<h3 style='margin:12px 0 8px'>" + esc(t("adm.delivery")) + "</h3>" +
        (deliveryHtml || '<div class="small muted">—</div>');
      m.el.querySelector("#aoClose").addEventListener("click", m.close);
    } catch (e) {
      m.close();
      toast(errMsg(e), "err");
    }
  }

  /* ------------------------------------------------ Katalog */
  async function renderCatalog(c) {
    c.innerHTML =
      '<div class="panel-card soft">' +
      '<div style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap">' +
      '<button class="btn btn-primary btn-sm" id="catSync">' + esc(t("adm.sync")) + "</button>" +
      '<input class="input" id="catSearch" data-i18n-ph="c.search" style="flex:1;min-width:180px"></div>' +
      '<div class="table-wrap" id="catTable"><div class="skeleton" style="height:140px"></div></div></div>';
    c.querySelector("#catSync").addEventListener("click", async () => {
      const b = c.querySelector("#catSync");
      b.disabled = true; b.textContent = t("adm.syncing");
      try {
        await api.post("/admin/api/catalog/sync");
        toast(t("adm.synced"), "ok");
        loadCatalog(c, c.querySelector("#catSearch").value);
      } catch (e) { toast(errMsg(e), "err"); }
      b.disabled = false; b.textContent = t("adm.sync");
    });
    const input = c.querySelector("#catSearch");
    let tm = null;
    input.addEventListener("input", () => {
      clearTimeout(tm);
      tm = setTimeout(() => loadCatalog(c, input.value), 350);
    });
    loadCatalog(c, "");
  }

  async function loadCatalog(c, q) {
    const box = c.querySelector("#catTable");
    try {
      const r = await api.get("/admin/api/catalog/products?q=" + encodeURIComponent(q));
      const rows = r.data || [];
      box.innerHTML = rows.length
        ? '<table class="tbl"><thead><tr><th>' + esc(t("cat.products")) + "</th><th>" + esc(t("adm.provider")) + "</th><th>" +
          esc(t("adm.price")) + "</th><th>" + esc(t("adm.stockC")) + "</th><th>" + esc(t("adm.stateC")) + "</th><th></th></tr></thead><tbody>" +
          rows.map((p) =>
            "<tr><td>" + esc(p.name || p.slug) + '<div class="small muted">' + esc(p.slug) + "</div></td><td>" + esc(p.provider || "—") +
            '</td><td>$' + esc(money(p.yourPrice)) + "</td><td>" + esc(p.stockCount == null ? "—" : p.stockCount) +
            '</td><td>' + (p.blocked ? '<span class="badge warn">' + esc(t("adm.hidden")) + "</span>" : '<span class="badge ok">' + esc(t("cat.inStock")) + "</span>") +
            '</td><td><button class="btn btn-sm" data-slug="' + esc(p.slug) + '" data-blocked="' + (p.blocked ? 1 : 0) + '">' +
            esc(p.blocked ? t("adm.show") : t("adm.hide")) + "</button></td></tr>"
          ).join("") + "</tbody></table>"
        : '<div class="empty-state">' + esc(t("adm.notFound")) + "</div>";
      box.querySelectorAll("button[data-slug]").forEach((b) =>
        b.addEventListener("click", async () => {
          try {
            await api.post("/admin/api/catalog/products/" + encodeURIComponent(b.dataset.slug) + "/toggle", {});
            toast(t("c.saved"), "ok");
            loadCatalog(c, c.querySelector("#catSearch").value);
          } catch (e) { toast(errMsg(e), "err"); }
        })
      );
    } catch (e) {
      box.innerHTML = '<div class="empty-state">' + esc(errMsg(e)) + "</div>";
    }
  }

  /* ------------------------------------------------ Matnlar */
  async function renderTexts(c) {
    const lang = localStorage.getItem("hy_texts_lang") || "uz";
    c.innerHTML =
      '<div class="panel-card soft">' +
      '<div style="display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap">' +
      '<select class="input" id="txtLang" style="width:auto">' +
      ["uz", "ru", "en"].map((l) => '<option value="' + l + '"' + (l === lang ? " selected" : "") + ">" + l + "</option>").join("") +
      "</select><span class='small muted'>" + esc(t("adm.txtHint")) + "</span></div>" +
      '<div id="txtList"><div class="skeleton" style="height:140px"></div></div></div>';
    c.querySelector("#txtLang").addEventListener("change", () => {
      localStorage.setItem("hy_texts_lang", c.querySelector("#txtLang").value);
      loadTexts(c);
    });
    loadTexts(c);
  }

  async function loadTexts(c) {
    const lang = c.querySelector("#txtLang").value;
    const box = c.querySelector("#txtList");
    try {
      const r = await api.get("/admin/api/texts?lang=" + lang);
      box.innerHTML = r.data.map((it) =>
        '<div class="soft-flat" style="padding:14px;margin-bottom:12px">' +
        '<div class="small" style="font-weight:800;margin-bottom:8px">' + esc(it.key) +
        (it.overridden ? ' <span class="badge">' + esc(t("adm.txtVal")) + "</span>" : "") + "</div>" +
        '<textarea class="input" rows="3" id="tx_' + esc(it.key) + '">' + esc(it.value) + "</textarea>" +
        '<div style="display:flex;gap:8px;margin-top:10px">' +
        '<button class="btn btn-primary btn-sm" data-save="' + esc(it.key) + '">' + esc(t("c.save")) + "</button>" +
        '<button class="btn btn-sm" data-reset="' + esc(it.key) + '">' + esc(t("adm.txtReset")) + "</button>" +
        "</div></div>"
      ).join("");
      box.querySelectorAll("[data-save]").forEach((b) =>
        b.addEventListener("click", async () => {
          const key = b.dataset.save;
          try {
            await api.post("/admin/api/texts", {
              key, lang, value: c.querySelector("#tx_" + key).value,
            });
            toast(t("c.saved"), "ok");
            loadTexts(c);
          } catch (e) { toast(errMsg(e), "err"); }
        })
      );
      box.querySelectorAll("[data-reset]").forEach((b) =>
        b.addEventListener("click", async () => {
          const key = b.dataset.reset;
          try {
            await api.post("/admin/api/texts", { key, lang, value: "" });
            toast(t("c.saved"), "ok");
            loadTexts(c);
          } catch (e) { toast(errMsg(e), "err"); }
        })
      );
    } catch (e) {
      box.innerHTML = '<div class="empty-state">' + esc(errMsg(e)) + "</div>";
    }
  }

  /* ------------------------------------------------ Rasmlar */
  async function renderImages(c) {
    c.innerHTML =
      '<div class="panel-card soft">' +
      '<div style="display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap">' +
      '<label class="btn btn-primary btn-sm" style="cursor:pointer">' + esc(t("adm.upload")) +
      '<input type="file" id="imgFile" accept="image/*" style="display:none"></label>' +
      '<span class="small muted" id="imgStatus"></span></div>' +
      '<div id="imgGrid"><div class="skeleton" style="height:140px"></div></div></div>';
    c.querySelector("#imgFile").addEventListener("change", async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const st = c.querySelector("#imgStatus");
      st.textContent = t("adm.uploading");
      const fd = new FormData();
      fd.append("file", file);
      try {
        await api.form("/admin/api/images", fd);
        st.textContent = "";
        toast(t("c.saved"), "ok");
        loadImages(c);
      } catch (err) { toast(errMsg(err), "err"); st.textContent = ""; }
      e.target.value = "";
    });
    loadImages(c);
  }

  async function loadImages(c) {
    const box = c.querySelector("#imgGrid");
    try {
      const r = await api.get("/admin/api/images");
      const rows = r.data || [];
      if (!rows.length) {
        box.innerHTML = '<div class="empty-state">' + esc(t("adm.imgEmpty")) + "</div>" +
          '<div class="small muted" style="margin-top:10px">' + esc(t("adm.current")) + ": <b>/" + esc(r.startPhoto || "img/hero.png") + "</b></div>";
        return;
      }
      box.innerHTML = '<div class="img-grid">' + rows.map((im) =>
        '<div class="img-item soft-flat"><img src="' + esc(im.url) + '" alt="">' +
        '<div class="small" style="margin-bottom:7px;word-break:break-all">' + esc(im.name || "") +
        (im.isStartPhoto ? ' <span class="badge ok">start</span>' : "") + "</div>" +
        '<div class="acts">' +
        (im.isStartPhoto ? "" : '<button class="btn btn-sm" data-use="' + im.id + '">' + esc(t("adm.setStart")) + "</button>") +
        '<button class="btn btn-sm btn-danger" data-del="' + im.id + '">' + esc(t("adm.del")) + "</button>" +
        "</div></div>"
      ).join("") + "</div>" +
      '<div class="small muted" style="margin-top:12px">' + esc(t("adm.current")) + ": <b>/" + esc(r.startPhoto || "img/hero.png") + "</b></div>";
      box.querySelectorAll("[data-use]").forEach((b) =>
        b.addEventListener("click", async () => {
          try {
            await api.post("/admin/api/images/" + b.dataset.use + "/use");
            toast(t("adm.setOk"), "ok");
            loadImages(c);
          } catch (e) { toast(errMsg(e), "err"); }
        })
      );
      box.querySelectorAll("[data-del]").forEach((b) =>
        b.addEventListener("click", async () => {
          try {
            await api.del("/admin/api/images/" + b.dataset.del);
            toast(t("c.saved"), "ok");
            loadImages(c);
          } catch (e) { toast(errMsg(e), "err"); }
        })
      );
    } catch (e) {
      box.innerHTML = '<div class="empty-state">' + esc(errMsg(e)) + "</div>";
    }
  }

  boot();
})();
