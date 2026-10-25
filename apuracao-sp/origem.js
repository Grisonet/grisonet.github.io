/* De onde vêm os votos já apurados: fatia de cada região (e do exterior) nos votos válidos
   dos boletins de urna lidos pelo coletor GR Data. Lê o snapshot do relay a cada 30 s.
   Uso: <div data-origem></div> + <script src="origem.js" defer></script> */
(function () {
  const QS = new URLSearchParams(location.search);
  const LIVE = QS.get("fonte") || "https://grdata-apuracao-production.up.railway.app";
  const COR = { Exterior: "#FF4C00", Norte: "#FFC200", Nordeste: "#B23600", "Centro-Oeste": "#C9C7C4", Sudeste: "#ffffff", Sul: "#7a7a7a" };
  const fmt = (v, d) => v.toLocaleString("pt-BR", { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 });
  const css = `.orig{margin-top:14px;max-width:760px;border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:12px 16px;font-size:13.5px;line-height:1.45;color:inherit}
.orig h4{margin:0 0 8px;font-size:13px;font-weight:700;letter-spacing:.2px}
.orig .bar{display:flex;height:12px;border-radius:9999px;overflow:hidden;background:rgba(255,255,255,.1)}
.orig .bar i{display:block;height:100%}
.orig .leg{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:8px}
.orig .leg span{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.orig .leg b{font-variant-numeric:tabular-nums}
.orig .leg em{width:10px;height:10px;border-radius:3px;display:inline-block;font-style:normal}
.orig .nota{margin-top:8px;opacity:.85}
.orig .alerta{color:#FFC200;font-weight:600}`;
  function render(el, s) {
    const rs = (s.regioes || []).map(r => ({ nome: r.nome, v: (r.va || 0) + (r.vb || 0) })).filter(r => r.v > 0);
    const tot = rs.reduce((a, r) => a + r.v, 0);
    if (!tot) { el.hidden = true; return; }
    rs.sort((a, b) => b.v - a.v);
    const ext = (rs.find(r => r.nome === "Exterior") || { v: 0 }).v / tot * 100;
    const sec = s.secoes || {};
    const hora = s.gerado_painel ? new Date(s.gerado_painel).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : "";
    let nota;
    if (ext >= 50) nota = `<span class="alerta">Por enquanto, a maior parte dos votos apurados vem de urnas do exterior</span>, onde o eleitorado vota diferente do Brasil. O placar ainda não representa o país.`;
    else if (ext >= 15) nota = `As urnas do exterior ainda pesam ${fmt(ext)}% dos votos apurados. O placar vai mudar conforme chegam as urnas do Brasil.`;
    else nota = `Amostra já dominada por urnas do Brasil.`;
    el.hidden = false;
    el.innerHTML = `<div class="orig"><h4>De onde vêm os votos já apurados</h4>
<div class="bar">${rs.map(r => `<i style="width:${r.v / tot * 100}%;background:${COR[r.nome] || "#999"}" title="${r.nome}"></i>`).join("")}</div>
<div class="leg">${rs.map(r => `<span><em style="background:${COR[r.nome] || "#999"}"></em>${r.nome} <b>${fmt(r.v / tot * 100, r.v / tot < .01 ? 1 : 0)}%</b></span>`).join("")}</div>
<div class="nota">${nota} <span style="opacity:.7">${sec.apuradas ? fmt(sec.apuradas) + " urnas lidas pela GR Data" : ""}${hora ? " · " + hora : ""}.</span></div></div>`;
  }
  /* Aviso piscante "TSE pausou a divulgação" (25/10/2026: votação prorrogada até 19h).
     Fica no ar enquanto nem o placar oficial do TSE nem a lista de boletins de urna forem
     atualizados depois das 19h; some sozinho quando o TSE voltar a publicar. */
  const RETOMA = new Date("2026-10-25T19:00:00-03:00");
  const FIM_AVISO = new Date("2026-10-26T06:00:00-03:00");
  const cssPausa = `#pausa-tse{background:#DC2626;color:#fff;font:600 14px/1.4 Inter,system-ui,sans-serif;text-align:center;padding:10px 16px;position:relative;z-index:40}
#pausa-tse b{font-weight:800}#pausa-tse .dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#fff;margin-right:8px;vertical-align:1px;animation:pausaPisca 1s steps(2,start) infinite}
#pausa-tse .txt{animation:pausaFade 1.6s ease-in-out infinite}
@keyframes pausaPisca{to{visibility:hidden}}@keyframes pausaFade{50%{opacity:.55}}
@media (prefers-reduced-motion:reduce){#pausa-tse .dot,#pausa-tse .txt{animation:none}}`;
  let tseHora = null;
  async function horaTSE() {
    try {
      const d = await (await fetch("https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json?t=" + Date.now(), { cache: "no-store" })).json();
      const [dd, mm, aa] = (d.dg || "").split("/");
      if (aa && d.hg) tseHora = new Date(`${aa}-${mm}-${dd}T${d.hg}-03:00`);
    } catch (e) { /* sem acesso ao TSE: decide só pelo snapshot */ }
  }
  function aviso(s) {
    const agora = new Date();
    const ultimos = [tseHora, s && s.gerado_tse ? new Date(s.gerado_tse) : null].filter(Boolean);
    const voltou = ultimos.some(t => t >= RETOMA);
    const pausado = agora < FIM_AVISO && ultimos.length && !voltou;
    let el = document.getElementById("pausa-tse");
    if (!pausado) { if (el) el.remove(); return; }
    if (!el) {
      el = document.createElement("div"); el.id = "pausa-tse"; el.setAttribute("role", "status");
      document.body.insertBefore(el, document.body.firstChild);
    }
    const h = ultimos.sort((a, b) => b - a)[0].toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    el.innerHTML = `<span class="dot"></span><span class="txt"><b>O TSE pausou a divulgação dos resultados</b> às ${h}, por causa da prorrogação da votação até as 19h. Nenhuma urna nova foi publicada desde então. A apuração volta depois das 19h e esta página se atualiza sozinha.</span>`;
  }
  async function tick(els) {
    let s = null;
    try {
      s = await (await fetch(LIVE + "/snapshot.json?t=" + Date.now(), { cache: "no-store" })).json();
      els.forEach(el => render(el, s));
    } catch (e) { /* mantém o último quadro */ }
    await horaTSE();
    aviso(s);
  }
  function init() {
    const els = [...document.querySelectorAll("[data-origem]")];
    const st = document.createElement("style"); st.textContent = css + cssPausa; document.head.appendChild(st);
    els.forEach(el => el.hidden = true);
    tick(els); setInterval(() => tick(els), 30000);
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", init) : init();
})();
