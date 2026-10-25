// Service worker dos avisos da apuração (GR Data): mostra o aviso e abre o site ao tocar.
self.addEventListener("install", () => self.skipWaiting());
// Endereço antigo (grisonet.github.io): o navegador mostra o domínio de quem assinou. Lá o worker
// cancela a assinatura e, no próximo aviso, pede para reativar em apuracao.grisodata.com.br.
const ANTIGO = self.location.hostname !== "apuracao.grisodata.com.br";
const PUSH = "https://grdata-push-production.up.railway.app";
async function sairDoAntigo() {
  const sub = await self.registration.pushManager.getSubscription();
  if (!sub) return;
  await fetch(PUSH + "/cancelar", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ endpoint: sub.endpoint }) }).catch(() => {});
  await sub.unsubscribe().catch(() => {});
}
self.addEventListener("activate", (e) => e.waitUntil(Promise.all([self.clients.claim(), ANTIGO ? sairDoAntigo() : null])));
self.addEventListener("push", (e) => {
  if (ANTIGO) {
    e.waitUntil(Promise.all([self.registration.showNotification("Os avisos da apuração mudaram de endereço", {
      body: "Toque para reativar em apuracao.grisodata.com.br e continuar recebendo as parciais.",
      tag: "migrar", icon: "icone-192.png", badge: "icone-badge.png", lang: "pt-BR",
      data: { url: "https://apuracao.grisodata.com.br/?utm_source=push&utm_medium=migracao" },
    }), sairDoAntigo()]));
    return;
  }
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch { d = { title: "Apuração do 2º turno", body: e.data && e.data.text() }; }
  e.waitUntil(self.registration.showNotification(d.title || "Apuração do 2º turno", {
    body: d.body || "Toque para ver os números.",
    tag: d.tag || "apuracao", renotify: !!d.renotify,
    icon: "icone-192.png", badge: "icone-badge.png", lang: "pt-BR",
    data: { url: d.url || "https://apuracao.grisodata.com.br/" },
  }));
});
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = e.notification.data && e.notification.data.url;
  e.waitUntil((async () => {
    const abas = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const c of abas) if (c.url.split("?")[0] === url.split("?")[0] && "focus" in c) { c.navigate(url).catch(() => {}); return c.focus(); }
    return self.clients.openWindow(url);
  })());
});
