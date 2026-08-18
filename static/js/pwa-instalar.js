(function () {
    var CHAVE_DISPENSADO = "cashb_pwa_banner_dispensado";
    if (localStorage.getItem(CHAVE_DISPENSADO)) return;

    var jaInstalado = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
    if (jaInstalado) return;

    var banner = document.getElementById("pwa-banner");
    if (!banner) return;
    var texto = banner.querySelector(".pwa-banner-texto");
    var botaoAcao = banner.querySelector(".pwa-banner-acao");
    var botaoFechar = banner.querySelector(".pwa-banner-fechar");

    function fechar() {
        banner.hidden = true;
        localStorage.setItem(CHAVE_DISPENSADO, "1");
    }
    botaoFechar.addEventListener("click", fechar);

    var agenteUsuario = window.navigator.userAgent.toLowerCase();
    var ehIOS = /iphone|ipad|ipod/.test(agenteUsuario);
    var ehSafari = /safari/.test(agenteUsuario) && !/crios|fxios|edgios/.test(agenteUsuario);

    var eventoInstalacao = null;
    window.addEventListener("beforeinstallprompt", function (evento) {
        evento.preventDefault();
        eventoInstalacao = evento;
        texto.textContent = "Instale a cash-b na tela inicial pra acessar mais rápido.";
        botaoAcao.hidden = false;
        botaoAcao.textContent = "Instalar";
        banner.hidden = false;
    });

    botaoAcao.addEventListener("click", function () {
        if (!eventoInstalacao) return;
        eventoInstalacao.prompt();
        eventoInstalacao.userChoice.finally(function () {
            eventoInstalacao = null;
            fechar();
        });
    });

    window.addEventListener("appinstalled", fechar);

    if (ehIOS && ehSafari) {
        texto.innerHTML = 'Instale a cash-b: toque em <strong>Compartilhar</strong> e depois em <strong>"Adicionar à Tela de Início"</strong>.';
        botaoAcao.hidden = true;
        banner.hidden = false;
    }
})();
