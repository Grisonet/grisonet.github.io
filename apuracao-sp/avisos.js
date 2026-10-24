/* Avisos da apuração no navegador (Web Push) — botões [data-avisos] abrem o painel de escolha.
   Funciona no Chrome, Edge, Firefox e Safari do Mac; no iPhone, só com o site adicionado à Tela de Início. */
(() => {
  const PUSH = "https://grdata-push-production.up.railway.app";
  const LS = "apuracao:avisos";
  const GOVS = [["AC", "Acre"], ["AM", "Amazonas"], ["DF", "Distrito Federal"], ["ES", "Espírito Santo"], ["RN", "Rio Grande do Norte"], ["TO", "Tocantins"]];
  const FREQ = [[1, "Só nos momentos decisivos", "começo, projeção apontando o vencedor, resultado oficial"], [2, "De hora em hora", "mais os momentos decisivos"],
    [3, "A cada 30 minutos", "mais os momentos decisivos"], [4, "A cada 15 minutos", "mais os momentos decisivos"], [5, "Em tempo real", "a cada novo lote do TSE, no máximo um aviso a cada 5 min"]];
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const instalado = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const suporta = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  const ler = () => { try { return JSON.parse(localStorage.getItem(LS) || "null"); } catch { return null; } };
  const gravar = (v) => { try { v ? localStorage.setItem(LS, JSON.stringify(v)) : localStorage.removeItem(LS); } catch {} };

  // manifesto e ícone: necessários para o iPhone instalar o site e receber avisos
  for (const [rel, href] of [["manifest", "manifest.webmanifest"], ["apple-touch-icon", "icone-192.png"]]) {
    if (!document.querySelector(`link[rel="${rel}"]`)) { const l = document.createElement("link"); l.rel = rel; l.href = href; document.head.appendChild(l); }
  }

  const css = document.createElement("style");
  css.textContent = `
  .ntf-bg{position:fixed;inset:0;background:rgba(8,8,8,.55);z-index:100;display:flex;align-items:flex-end;justify-content:center;padding:16px}
  @media(min-width:640px){.ntf-bg{align-items:center}}
  .ntf{background:#fff;color:#0b0b0b;border-radius:20px;max-width:460px;width:100%;max-height:calc(100vh - 32px);overflow:auto;padding:22px 20px 18px;font:15px/1.45 Inter,system-ui,sans-serif;box-shadow:0 20px 60px rgba(0,0,0,.35)}
  .ntf h2{font:800 21px/1.15 "Inter Tight",Inter,system-ui,sans-serif;letter-spacing:-.02em;margin:0 0 6px}
  .ntf p{margin:0 0 12px;color:#3a3a3a;font-size:14px}
  .ntf .lbl{font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#636363;margin:14px 0 8px}
  .ntf label.op{display:flex;gap:10px;align-items:flex-start;padding:9px 11px;border:1px solid #e2dfda;border-radius:12px;margin-bottom:6px;cursor:pointer}
  .ntf label.op:has(input:checked){border-color:#FF4C00;background:rgba(255,76,0,.06)}
  .ntf label.op input{margin-top:3px;accent-color:#FF4C00}
  .ntf label.op small{display:block;color:#636363;font-size:12.5px}
  .ntf .govs{display:flex;flex-wrap:wrap;gap:6px}
  .ntf .govs label{display:inline-flex;gap:6px;align-items:center;border:1px solid #e2dfda;border-radius:9999px;padding:6px 11px;font-size:13.5px;cursor:pointer}
  .ntf .govs label:has(input:checked){border-color:#FF4C00;background:rgba(255,76,0,.06)}
  .ntf .govs input{accent-color:#FF4C00}
  .ntf .acoes{display:flex;gap:8px;justify-content:flex-end;margin-top:16px;flex-wrap:wrap}
  .ntf button{font:600 14px Inter,system-ui,sans-serif;border-radius:12px;padding:10px 15px;cursor:pointer;border:1px solid #e2dfda;background:#fff;color:#0b0b0b}
  .ntf button.pri{background:#FF4C00;border-color:#FF4C00;color:#080808}
  .ntf button:disabled{opacity:.6;cursor:wait}
  .ntf .msg{font-size:13.5px;margin-top:10px;color:#3a3a3a}.ntf .msg.err{color:#DC2626}
  .ntf ol{margin:6px 0 12px;padding-left:20px;color:#3a3a3a;font-size:14px}`;
  document.head.appendChild(css);

  function rotulo() {
    const st = ler();
    document.querySelectorAll("[data-avisos]").forEach((b) => {
      const t = b.querySelector("[data-avisos-txt]") || b;
      t.textContent = st ? "Avisos ligados · ajustar" : (b.dataset.avisosTxt || "Receber avisos no navegador");
    });
  }

  function fecha() { const bg = document.querySelector(".ntf-bg"); if (bg) bg.remove(); }

  function abre() {
    fecha();
    const st = ler() || { freq: 2, govs: [] };
    const bg = document.createElement("div");
    bg.className = "ntf-bg";
    bg.addEventListener("click", (e) => { if (e.target === bg) fecha(); });
    let html;
    if (ios && !instalado) {
      html = `<h2>Avisos no iPhone</h2><p>No iPhone, o Safari só manda avisos de sites adicionados à Tela de Início. Leva 10 segundos:</p>
        <ol><li>Toque em <b>Compartilhar</b> (o quadrado com a seta) na barra do Safari.</li><li>Escolha <b>Adicionar à Tela de Início</b>.</li><li>Abra a <b>Apuração</b> pelo ícone novo e toque de novo em <b>Receber avisos</b>.</li></ol>
        <div class="acoes"><button class="pri" data-x>Entendi</button></div>`;
    } else if (!suporta) {
      html = `<h2>Avisos no navegador</h2><p>Este navegador não aceita avisos. Use o Chrome, o Edge, o Firefox ou o Safari atualizado — ou deixe esta página aberta: ela se atualiza sozinha.</p><div class="acoes"><button class="pri" data-x>Fechar</button></div>`;
    } else {
      html = `<h2>Receber avisos da apuração</h2>
        <p>O navegador avisa você durante a apuração do 2º turno, domingo, 25/10, a partir das 17h — mesmo com o site fechado. Tocando no aviso você cai direto nos números.</p>
        <div class="lbl">Com que frequência</div>
        ${FREQ.map(([v, t, s]) => `<label class="op"><input type="radio" name="ntf-f" value="${v}"${st.freq === v ? " checked" : ""}><span>${t}<small>${s}</small></span></label>`).join("")}
        <div class="lbl">Governador (opcional)</div>
        <div class="govs">${GOVS.map(([g, n]) => `<label title="${n}"><input type="checkbox" value="${g}"${(st.govs || []).includes(g) ? " checked" : ""}>${g}</label>`).join("")}</div>
        <p style="margin-top:12px;font-size:12.5px;color:#636363">Presidente vem sempre. Nada de cadastro: não pedimos nome, e-mail nem telefone.</p>
        <div class="msg" data-msg></div>
        <div class="acoes">${ler() ? `<button data-off>Desligar avisos</button>` : ""}<button data-x>Agora não</button><button class="pri" data-ok>${ler() ? "Salvar" : "Ativar avisos"}</button></div>`;
    }
    bg.innerHTML = `<div class="ntf" role="dialog" aria-modal="true" aria-label="Avisos da apuração">${html}</div>`;
    document.body.appendChild(bg);
    bg.querySelectorAll("[data-x]").forEach((b) => (b.onclick = fecha));
    const ok = bg.querySelector("[data-ok]"), off = bg.querySelector("[data-off]"), msg = bg.querySelector("[data-msg]");
    const diz = (t, err) => { msg.textContent = t; msg.className = "msg" + (err ? " err" : ""); };
    if (ok) ok.onclick = async () => {
      const freq = +(bg.querySelector('input[name="ntf-f"]:checked') || {}).value || 1;
      const govs = [...bg.querySelectorAll(".govs input:checked")].map((i) => i.value);
      ok.disabled = true; diz("Ligando…");
      try {
        const perm = await Notification.requestPermission();
        if (perm !== "granted") throw new Error(perm === "denied" ? "Os avisos estão bloqueados para este site. Libere nas configurações do navegador (cadeado ao lado do endereço) e tente de novo." : "Você não autorizou os avisos.");
        const reg = await navigator.serviceWorker.register("sw.js");
        await navigator.serviceWorker.ready;
        const { chave } = await fetch(PUSH + "/vapid").then((r) => r.json());
        const raw = Uint8Array.from(atob(chave.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((chave.length + 3) % 4)), (c) => c.charCodeAt(0));
        const sub = (await reg.pushManager.getSubscription()) || (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: raw }));
        const r = await fetch(PUSH + "/assinar", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ assinatura: sub.toJSON(), freq, govs }) });
        if (!r.ok) throw new Error("O servidor de avisos não respondeu. Tente de novo em instantes.");
        gravar({ freq, govs, endpoint: sub.endpoint });
        (window.gaFila = window.gaFila || []).push(["push_subscribed", { freq, governadores: govs.length }]);
        rotulo();
        diz("Pronto! Avisos ligados ✅ Um aviso de confirmação deve chegar em instantes.");
        setTimeout(fecha, 2200);
      } catch (e) { diz(e.message || "Não deu certo. Tente de novo.", true); ok.disabled = false; }
    };
    if (off) off.onclick = async () => {
      off.disabled = true;
      try {
        const reg = await navigator.serviceWorker.getRegistration();
        const sub = reg && (await reg.pushManager.getSubscription());
        if (sub) { await fetch(PUSH + "/cancelar", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ endpoint: sub.endpoint }) }).catch(() => {}); await sub.unsubscribe(); }
      } catch {}
      gravar(null); rotulo(); fecha();
    };
  }

  document.addEventListener("click", (e) => { const b = e.target.closest("[data-avisos]"); if (b) { e.preventDefault(); abre(); } });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecha(); });
  // os avisos acabam com a apuração: depois disso o botão some
  fetch(PUSH + "/vapid").then((r) => r.json()).then((c) => {
    if (!c.ativo) return;
    document.querySelectorAll("[data-avisos]").forEach((b) => (b.hidden = false));
    rotulo();
  }).catch(() => {});
})();
