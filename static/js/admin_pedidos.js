// Botão "Expandir tabela" na página de pedidos do admin: esconde o cabeçalho,
// a barra lateral e o painel de filtros pra tabela usar a largura inteira da
// tela. O estado fica salvo no navegador pra sobreviver a troca de página
// (paginação, busca, filtro).
document.addEventListener("DOMContentLoaded", function () {
    var CHAVE_LOCALSTORAGE = "cashb_admin_pedidos_tabela_expandida";

    var botao = document.createElement("button");
    botao.type = "button";
    botao.id = "toggle-tabela-expandida";
    document.body.appendChild(botao);

    function aplicarEstado(expandida) {
        document.body.classList.toggle("pedidos-tabela-expandida", expandida);
        botao.textContent = expandida ? "✕ Sair da visualização expandida" : "⛶ Expandir tabela";
    }

    botao.addEventListener("click", function () {
        var novoEstado = !document.body.classList.contains("pedidos-tabela-expandida");
        aplicarEstado(novoEstado);
        try {
            window.localStorage.setItem(CHAVE_LOCALSTORAGE, novoEstado ? "1" : "0");
        } catch (erro) {
            // localStorage indisponível (modo privado, etc.) - só não persiste entre páginas.
        }
    });

    var estadoSalvo = null;
    try {
        estadoSalvo = window.localStorage.getItem(CHAVE_LOCALSTORAGE);
    } catch (erro) {
        // idem
    }
    aplicarEstado(estadoSalvo === "1");
});
