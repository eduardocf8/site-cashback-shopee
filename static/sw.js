self.addEventListener("push", function (evento) {
    var dados = {};
    try {
        dados = evento.data.json();
    } catch (erro) {
        dados = {};
    }

    var titulo = dados.titulo || "cash-b";
    var opcoes = {
        body: dados.corpo || "",
        icon: "/static/icons/icon-192.png",
        badge: "/static/icons/icon-192.png",
        data: { url: dados.url || "/" },
    };

    evento.waitUntil(self.registration.showNotification(titulo, opcoes));
});

self.addEventListener("notificationclick", function (evento) {
    evento.notification.close();
    var url = (evento.notification.data && evento.notification.data.url) || "/";
    evento.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (listaJanelas) {
            for (var i = 0; i < listaJanelas.length; i++) {
                if (listaJanelas[i].url === url && "focus" in listaJanelas[i]) {
                    return listaJanelas[i].focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(url);
            }
        })
    );
});
