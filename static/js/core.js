/* Hamyon — umumiy yordamchilar: fetch, tarjima, toast, modal, format */
(function () {
  const state = {
    lang: localStorage.getItem("hy_lang") || "",
    dict: {},
  };

  function currentLang() {
    return state.lang || "uz";
  }

  function setLang(lang) {
    if (!window.I18N || !window.I18N[lang]) lang = "uz";
    state.lang = lang;
    state.dict = window.I18N[lang] || {};
    localStorage.setItem("hy_lang", lang);
    document.documentElement.lang = lang;
    applyI18n(document);
  }

  function t(key, params) {
    let s = state.dict[key];
    if (s === undefined && window.I18N) s = (window.I18N.en || {})[key];
    if (s === undefined) s = key;
    if (params) {
      Object.keys(params).forEach((k) => {
        s = s.split("{" + k + "}").join(params[k]);
      });
    }
    return s;
  }

  function applyI18n(root) {
    (root || document).querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = t(el.getAttribute("data-i18n"));
    });
    (root || document).querySelectorAll("[data-i18n-ph]").forEach((el) => {
      el.setAttribute("placeholder", t(el.getAttribute("data-i18n-ph")));
    });
  }

  /* ---------------- fetch ---------------- */
  async function req(method, url, body, isForm) {
    const opts = { method, credentials: "same-origin" };
    if (body !== undefined && body !== null) {
      if (isForm) {
        opts.body = body;
      } else {
        opts.headers = { "Content-Type": "application/json" };
        opts.body = JSON.stringify(body);
      }
    }
    let resp;
    try {
      resp = await fetch(url, opts);
    } catch (e) {
      throw { code: "NETWORK", message: t("err.network"), status: 0 };
    }
    let data = null;
    try { data = await resp.json(); } catch (e) { /* bo'sh */ }
    if (!resp.ok || (data && data.ok === false)) {
      const err = (data && data.error) || {};
      throw {
        code: err.code || ("HTTP_" + resp.status),
        message: err.message || t("err.unknown"),
        status: resp.status,
        required: err.required,
        balance: err.balance,
      };
    }
    return data || {};
  }

  const api = {
    get: (url) => req("GET", url),
    post: (url, body) => req("POST", url, body),
    del: (url) => req("DELETE", url),
    form: (url, formData) => req("POST", url, formData, true),
  };

  /* ---------------- toast ---------------- */
  function toast(msg, type) {
    const wrap = document.getElementById("toasts");
    if (!wrap) return;
    const el = document.createElement("div");
    el.className = "toast " + (type || "");
    el.textContent = msg;
    wrap.appendChild(el);
    setTimeout(() => {
      el.style.transition = "opacity .4s, transform .4s";
      el.style.opacity = "0";
      el.style.transform = "translateY(-8px)";
      setTimeout(() => el.remove(), 420);
    }, 2600);
  }

  /* ---------------- modal ---------------- */
  function showModal(innerHtml, opts) {
    opts = opts || {};
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML =
      '<div class="modal-card' + (opts.center ? " center" : "") + '">' +
      (opts.center ? "" : '<div class="modal-handle"></div>') +
      innerHtml +
      "</div>";
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop && !opts.sticky) close();
    });
    function close() { backdrop.remove(); if (opts.onClose) opts.onClose(); }
    document.body.appendChild(backdrop);
    return { el: backdrop, close };
  }

  /* ---------------- format ---------------- */
  function esc(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .split("&").join("&amp;").split("<").join("&lt;").split(">").join("&gt;")
      .split('"').join("&quot;").split("'").join("&#39;");
  }

  function money(v) {
    const n = Number(v);
    if (!isFinite(n)) return v == null ? "—" : String(v);
    return n.toFixed(2);
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    const p = (x) => String(x).padStart(2, "0");
    return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast(t("c.copied"), "ok");
    } catch (e) {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); toast(t("c.copied"), "ok"); } catch (e2) { /* */ }
      ta.remove();
    }
  }

  function errMsg(e) {
    if (!e) return t("err.unknown");
    switch (e.code) {
      case "NETWORK": return t("err.network");
      case "API_NOT_CONFIGURED": return t("err.apiNotConfigured");
      case "MAINTENANCE": return t("err.maintenance");
      case "RATE_LIMIT_EXCEEDED": return t("err.rate");
      case "OUT_OF_STOCK": return t("err.oos");
      case "USER_BLOCKED": return t("err.blocked");
      case "UNAUTHORIZED":
      case "NO_INIT_DATA":
      case "BAD_INIT_DATA":
      case "BAD_SIGNATURE":
      case "INIT_DATA_EXPIRED": return t("err.unauthorized");
      case "INSUFFICIENT_BALANCE":
        return t("cat.insufficient", {
          required: money(e.required), balance: money(e.balance),
        });
      default: return e.message || t("err.unknown");
    }
  }

  /* ---------------- mavzu ---------------- */
  function applyTheme(theme) {
    let mode = theme;
    if (!mode || mode === "auto") {
      const tg = window.Telegram && window.Telegram.WebApp;
      const scheme = tg && tg.colorScheme ? tg.colorScheme
        : (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      mode = scheme;
    }
    document.body.setAttribute("data-theme", mode === "dark" ? "dark" : "light");
  }

  window.H = {
    state, currentLang, setLang, t, applyI18n,
    api, toast, showModal, esc, money, fmtDate, copyText, errMsg, applyTheme,
  };
})();
