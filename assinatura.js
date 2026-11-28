/* GR Data — plano do usuário no app (carregado ANTES do app.js).
 *
 * 1. Manda o login (token do Supabase) junto nas chamadas às funções do GR Data,
 *    para o servidor saber o plano de quem pede (limites de IA, consultas, Pro…).
 * 2. Quando o servidor responde "fora do plano" (402) ou "limite do dia" (429),
 *    mostra o convite para assinar.
 * 3. window.grPlano: usado pelo app.js no comparativo e no export CSV.
 * 4. Aviso de mensalidade em aberto / em atraso, com link para assinar.html.
 *
 * Fica fora do app.js de propósito (o app é um bundle compilado), como o botão de suporte.
 */
(function () {
  var REF = "lrtacwxvsrqbcmgbvyrl";
  var FN = "https://" + REF + ".supabase.co/functions/v1/";
  var SESSAO = "sb-" + REF + "-auth-token";
  var CACHE = "grdata.plano";
  var NIVEL = { cidadao: 0, plus: 1, pro: 2 };
  var NOME = { cidadao: "Cidadão", plus: "Plus", pro: "Pro" };

  function ler(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function gravar(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* sem storage */ } }

  function token() {
    try {
      var v = JSON.parse(ler(SESSAO) || "null");
      if (!v) return null;
      var s = v.currentSession || v;
      if (!s.access_token) return null;
      if (s.expires_at && s.expires_at * 1000 < Date.now()) return null;
      return s.access_token;
    } catch (e) { return null; }
  }

  var plano = ler(CACHE) || "cidadao";
  if (!(plano in NIVEL)) plano = "cidadao";

  // ---------- convite para assinar ----------
  var aberto = null;
  function fecharModal() { if (aberto) { aberto.remove(); aberto = null; } }
  function modal(msg, up) {
    if (aberto) return;
    var alvo = (up && up.plano) || "plus";
    var precisaLogin = up && up.logado === false;
    var el = document.createElement("div");
    el.id = "gr-plano-modal";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-modal", "true");
    el.innerHTML =
      '<div class="gpm-box">' +
      '<div class="gpm-tag">Plano ' + (NOME[alvo] || "Plus") + "</div>" +
      '<p class="gpm-msg"></p>' +
      '<div class="gpm-acoes">' +
      '<a class="gpm-cta" href="assinar.html?plano=' + alvo + '">' +
      (precisaLogin ? "Entrar ou assinar" : "Assinar o " + (NOME[alvo] || "Plus")) + "</a>" +
      '<button type="button" class="gpm-sec">Agora não</button>' +
      "</div></div>";
    el.querySelector(".gpm-msg").textContent = msg || "Este recurso faz parte de um plano pago.";
    el.addEventListener("click", function (e) { if (e.target === el) fecharModal(); });
    el.querySelector(".gpm-sec").addEventListener("click", fecharModal);
    document.addEventListener("keydown", function esc(e) {
      if (e.key === "Escape") { fecharModal(); document.removeEventListener("keydown", esc); }
    });
    document.body.appendChild(el);
    aberto = el;
    el.querySelector(".gpm-cta").focus();
  }

  // ---------- login nas chamadas às funções ----------
  var origFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    if (url.indexOf(FN) !== 0) return origFetch(input, init);
    var t = token();
    if (t) {
      init = Object.assign({}, init || {});
      var h = new Headers(init.headers || (typeof input !== "string" && input.headers) || {});
      if (!h.has("Authorization")) h.set("Authorization", "Bearer " + t);
      init.headers = h;
    }
    return origFetch(input, init).then(function (res) {
      if ((res.status === 402 || res.status === 429) && url.indexOf("grdata-assinatura") < 0) {
        res.clone().json().then(function (j) {
          if (j && j.error) modal(j.error, j.upgrade || null);
        }).catch(function () {});
      }
      return res;
    });
  };

  // ---------- aviso de mensalidade ----------
  function aviso(texto) {
    var el = document.getElementById("gr-plano-aviso");
    if (!texto) { if (el) el.remove(); return; }
    if (!el) {
      el = document.createElement("a");
      el.id = "gr-plano-aviso";
      el.href = "assinar.html";
      document.body.appendChild(el);
    }
    el.textContent = texto;
  }

  function dataBR(iso) {
    try { return new Date(iso).toLocaleDateString("pt-BR"); } catch (e) { return ""; }
  }

  var ultimoToken = undefined;
  function atualizar() {
    var t = token();
    if (t === ultimoToken) return;
    ultimoToken = t;
    if (!t) { plano = "cidadao"; gravar(CACHE, plano); aviso(null); return; }
    origFetch(FN + "grdata-assinatura?acao=minha", { headers: { Authorization: "Bearer " + t } })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || !j.logado) return;
        plano = j.plano in NIVEL ? j.plano : "cidadao";
        gravar(CACHE, plano);
        var a = j.assinatura;
        if (j.aberto) {
          aviso((j.aberto.method === "pix" ? "Pix" : "Boleto") + " da sua assinatura em aberto · pagar agora →");
        } else if (a && a.status === "atrasada") {
          aviso("Sua assinatura " + (NOME[a.plano] || "") + " está em atraso desde " + dataBR(a.vence_em) + " · regularizar →");
        } else {
          aviso(null);
        }
      })
      .catch(function () { /* mantém o último plano conhecido */ });
  }

  window.grPlano = {
    plano: function () { return plano; },
    tem: function (p) { return NIVEL[plano] >= (NIVEL[p] || 0); },
    /** Comparativo: só no Pro. */
    comparar: function () {
      if (NIVEL[plano] >= NIVEL.pro) return true;
      modal("O comparativo de candidatos (até 5 lado a lado) faz parte do plano Pro.", { plano: "pro", logado: !!token() });
      return false;
    },
    /** Export CSV: Plus 1 por dia, Pro ilimitado — conferido no servidor. */
    exportar: function () {
      return window.fetch(FN + "grdata-assinatura?acao=uso", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      }).then(function (r) {
        if (r.ok) return true;
        return r.json().then(function (j) { modal(j.error, j.upgrade || { plano: "plus", logado: !!token() }); return false; });
      }).catch(function () { return true; });
    },
    atualizar: function () { ultimoToken = undefined; atualizar(); },
  };

  // estilos (Griso DS)
  var css = document.createElement("style");
  css.textContent =
    "#gr-plano-modal{position:fixed;inset:0;z-index:10000;background:rgba(8,8,8,.55);display:flex;align-items:center;justify-content:center;padding:16px}" +
    "#gr-plano-modal .gpm-box{background:#fff;border-radius:18px;max-width:420px;width:100%;padding:28px 24px;text-align:center;font-family:Inter,system-ui,sans-serif;color:#080808}" +
    "#gr-plano-modal .gpm-tag{display:inline-block;background:#FFC200;color:#080808;font:600 12px/1 Inter,sans-serif;padding:6px 10px;border-radius:999px;margin-bottom:14px}" +
    "#gr-plano-modal .gpm-msg{font-size:17px;line-height:1.47;letter-spacing:-.374px;margin:0 0 22px}" +
    "#gr-plano-modal .gpm-acoes{display:flex;flex-direction:column;gap:10px}" +
    "#gr-plano-modal .gpm-cta{background:#FF4C00;color:#080808;text-decoration:none;font-weight:600;padding:11px 22px;border-radius:999px}" +
    "#gr-plano-modal .gpm-cta:focus-visible,#gr-plano-modal .gpm-sec:focus-visible{outline:2px solid #FF6428;outline-offset:2px}" +
    "#gr-plano-modal .gpm-sec{background:none;border:0;color:#454545;font:400 14px Inter,sans-serif;cursor:pointer;padding:8px}" +
    "#gr-plano-aviso{position:fixed;left:16px;bottom:20px;z-index:9997;max-width:calc(100% - 120px);background:#080808;color:#fff;text-decoration:none;font:600 13px/1.3 Inter,system-ui,sans-serif;padding:11px 16px;border-radius:999px;box-shadow:0 6px 20px -6px rgba(0,0,0,.35)}";
  document.head.appendChild(css);

  function iniciar() { atualizar(); setInterval(atualizar, 5000); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
