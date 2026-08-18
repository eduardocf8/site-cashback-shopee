(function () {
    var botao = document.getElementById("push-botao");
    if (!botao) return;

    var chavePublica = botao.dataset.vapidKey;
    if (!chavePublica || !("serviceWorker" in navigator) || !("PushManager" in window)) {
        botao.hidden = true;
        return;
    }

    function pegarCookie(nome) {
        var encontrado = document.cookie.match("(^|;)\\s*" + nome + "\\s*=\\s*([^;]+)");
        return encontrado ? encontrado.pop() : "";
    }

    function base64UrlParaUint8Array(base64Url) {
        var preenchimento = "=".repeat((4 - (base64Url.length % 4)) % 4);
        var base64 = (base64Url + preenchimento).replace(/-/g, "+").replace(/_/g, "/");
        var bruto = window.atob(base64);
        var saida = new Uint8Array(bruto.length);
        for (var i = 0; i < bruto.length; i++) {
            saida[i] = bruto.charCodeAt(i);
        }
        return saida;
    }

    function mandarParaBackend(rota, corpo) {
        return fetch(rota, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": pegarCookie("csrftoken") },
            body: JSON.stringify(corpo),
        });
    }

    function atualizarBotao(inscrito) {
        botao.textContent = inscrito ? "Notificações ativadas" : "Ativar notificações";
        botao.disabled = inscrito;
    }

    var registroPromise = navigator.serviceWorker.register("/sw.js");

    registroPromise
        .then(function (registro) {
            return registro.pushManager.getSubscription();
        })
        .then(function (inscricaoAtual) {
            atualizarBotao(!!inscricaoAtual);
        })
        .catch(function () {});

    botao.addEventListener("click", function () {
        if (Notification.permission === "denied") {
            botao.textContent = "Notificações bloqueadas no navegador";
            return;
        }

        registroPromise
            .then(function (registro) {
                return Notification.requestPermission().then(function (permissao) {
                    if (permissao !== "granted") {
                        throw new Error("permissao-negada");
                    }
                    return registro.pushManager.subscribe({
                        userVisibleOnly: true,
                        applicationServerKey: base64UrlParaUint8Array(chavePublica),
                    });
                });
            })
            .then(function (inscricao) {
                return mandarParaBackend("/notificacoes/inscrever/", inscricao.toJSON());
            })
            .then(function () {
                atualizarBotao(true);
            })
            .catch(function (erro) {
                if (erro.message !== "permissao-negada") {
                    botao.textContent = "Não deu pra ativar agora";
                }
            });
    });
})();
