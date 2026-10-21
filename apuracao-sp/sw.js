// Service worker dos avisos da apuração (GR Data): mostra o aviso e abre o site ao tocar.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("push", (e) => {
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
