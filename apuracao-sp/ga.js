/* GA4 da Griso: Consent Mode v2, aviso de cookies (LGPD) e page_view em SPA de hash.
   Uso: <script src="ga.js" data-ga-id="G-XXXXXXX" async></script>
   Opções na mesma tag: data-ga-domains="a.com.br,b.com.br" (domínios cruzados),
   data-ga-hash (rotas em #/…, page_view manual), data-ga-cor="#FF4C00" (botão do aviso),
   data-ga-produto="grdata" (vai como "product" em todo evento).
   Eventos: window.gaEvento(nome, params); data-ga-evento="nome" + data-ga-p-<param> num
   elemento clicável; links wa.me/tel:/mailto: viram generate_lead sozinhos.
   Sem ID válido, ou rodando em localhost, não faz nada. Mesmo arquivo em todos os sites. */
(function () {
  var tag = document.currentScript;
  var ID = tag && tag.getAttribute('data-ga-id');
  if (!ID || !/^G-[A-Z0-9]{4,}$/.test(ID)) return;
  if (/^(localhost|127\.0\.0\.1|0\.0\.0\.0|192\.168\.|10\.)|^$/.test(location.hostname)) return;

  var LS = 'griso-consentimento';
  var ler = function () { try { return localStorage.getItem(LS); } catch (e) { return null; } };
  var gravar = function (v) { try { localStorage.setItem(LS, v); } catch (e) {} };

  window.dataLayer = window.dataLayer || [];
  var gtag = window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };

  // tudo começa negado; a medição só grava cookie depois do "Aceitar"
  var escolha = ler();
  gtag('consent', 'default', {
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
    analytics_storage: escolha === 'sim' ? 'granted' : 'denied',
    wait_for_update: 500
  });
  gtag('js', new Date());

  var hash = tag.hasAttribute('data-ga-hash');
  var dominios = (tag.getAttribute('data-ga-domains') || '').split(',').map(function (d) { return d.trim(); }).filter(Boolean);
  var cfg = {};
  if (dominios.length) cfg.linker = { domains: dominios };
  if (hash) cfg.send_page_view = false;
  gtag('config', ID, cfg);

  var s = document.createElement('script');
  s.async = true;
  s.src = 'https://www.googletagmanager.com/gtag/js?id=' + ID;
  document.head.appendChild(s);

  // SPA com rotas em #/…: vira /rota no page_location, para o relatório de páginas separar as telas
  if (hash) {
    var ultima = null;
    var pagina = function () {
      var rota = location.hash.replace(/^#\/?/, '').split('?')[0];
      var url = location.origin + location.pathname.replace(/\/$/, '') + (rota ? '/' + rota : '/');
      if (url === ultima) return;
      ultima = url;
      gtag('event', 'page_view', { page_location: url, page_title: document.title });
    };
    pagina();
    window.addEventListener('hashchange', pagina);
  }

  // eventos: window.gaEvento('nome', {params}) em qualquer página; data-ga-produto na tag
  // entra como "product" em todo evento. Sem dado pessoal em parâmetro (o Google apaga a propriedade).
  var produto = tag.getAttribute('data-ga-produto');
  var evento = window.gaEvento = function (nome, params) {
    var p = {};
    if (produto) p.product = produto;
    for (var k in params || {}) if (params[k] != null && params[k] !== '') p[k] = params[k];
    gtag('event', nome, p);
  };
  // a página pode chamar antes deste arquivo carregar: (window.gaFila = window.gaFila || []).push([nome, params])
  (window.gaFila || []).forEach(function (f) { evento(f[0], f[1]); });
  window.gaFila = { push: function (f) { evento(f[0], f[1]); } };

  // cliques: link de WhatsApp, telefone ou e-mail é lead; data-ga-evento="nome" dispara o evento,
  // e cada data-ga-p-<param>="valor" do mesmo elemento vira parâmetro
  document.addEventListener('click', function (e) {
    var el = e.target && e.target.closest ? e.target.closest('a, button, [data-ga-evento]') : null;
    if (!el) return;
    var nome = el.getAttribute('data-ga-evento');
    if (nome) {
      var params = {};
      for (var i = 0; i < el.attributes.length; i++) {
        var a = el.attributes[i];
        if (a.name.indexOf('data-ga-p-') === 0) params[a.name.slice(10).replace(/-/g, '_')] = a.value;
      }
      evento(nome, params);
    }
    var href = el.getAttribute('href') || '';
    var metodo = /^https:\/\/(wa\.me|api\.whatsapp\.com)\//.test(href) ? 'whatsapp'
      : /^tel:/.test(href) ? 'telefone' : /^mailto:/.test(href) ? 'email' : null;
    if (metodo) evento('generate_lead', { method: metodo, origem: el.getAttribute('data-ga-origem') || undefined });
  }, true);

  if (escolha === 'sim' || escolha === 'nao') return;

  var aviso = function () {
    var cor = tag.getAttribute('data-ga-cor') || '#FF4C00';
    var box = document.createElement('div');
    box.setAttribute('role', 'region');
    box.setAttribute('aria-label', 'Aviso de cookies');
    box.style.cssText = 'position:fixed;left:16px;right:16px;bottom:16px;z-index:2147483000;max-width:560px;margin:0 auto;' +
      'background:#111;color:#f5f5f5;border-radius:12px;padding:14px 16px;font:14px/1.45 system-ui,-apple-system,sans-serif;' +
      'display:flex;flex-wrap:wrap;gap:12px;align-items:center;box-shadow:0 6px 24px rgba(0,0,0,.25)';
    var txt = document.createElement('p');
    txt.style.cssText = 'margin:0;flex:1 1 260px';
    txt.textContent = 'Usamos cookies de medição para entender como o site é usado. Nenhum dado pessoal é coletado.';
    var botao = function (rotulo, primario, valor) {
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = rotulo;
      b.style.cssText = 'border:0;border-radius:8px;padding:8px 14px;font:600 14px system-ui,sans-serif;cursor:pointer;' +
        (primario ? 'background:' + cor + ';color:#fff' : 'background:transparent;color:#f5f5f5;outline:1px solid #555');
      b.onclick = function () {
        gravar(valor);
        gtag('consent', 'update', { analytics_storage: valor === 'sim' ? 'granted' : 'denied' });
        box.remove();
      };
      return b;
    };
    box.appendChild(txt);
    box.appendChild(botao('Recusar', false, 'nao'));
    box.appendChild(botao('Aceitar', true, 'sim'));
    document.body.appendChild(box);
  };
  if (document.body) aviso(); else document.addEventListener('DOMContentLoaded', aviso);
})();
