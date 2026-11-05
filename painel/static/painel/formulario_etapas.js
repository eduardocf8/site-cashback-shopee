// Formulários do Bot em passos (Automação e Campanhas).
// 1. Um link pra um passo (#onde-enviar, #datas...) abre esse passo e rola até ele.
// 2. No celular, a faixa "Salvar" fica escondida até a pessoa mudar algum campo do formulário
//    (sem JavaScript ela continua sempre à vista). Campos que salvam sozinhos (data-salva-na-hora),
//    campos de outro formulário (atributo form=) e buscas sem nome não contam.
(function () {
  function abrirPeloEndereco() {
    var id = decodeURIComponent((window.location.hash || "").slice(1));
    var alvo = id && document.getElementById(id);
    var passo = alvo && (alvo.matches("details.etapa") ? alvo : alvo.closest("details.etapa"));
    if (!passo) return;
    passo.open = true;
    alvo.scrollIntoView({ block: "start" });
  }
  abrirPeloEndereco();
  window.addEventListener("hashchange", abrirPeloEndereco);

  document.querySelectorAll(".barra-salvar[data-aparece-ao-mudar]").forEach(function (barra) {
    var form = barra.closest("form");
    if (!form) return;
    if (!barra.classList.contains("mudou")) barra.classList.add("esperando");
    function marcar(e) {
      var campo = e.target;
      if (!campo.name || campo.form !== form || campo.hasAttribute("data-salva-na-hora")) return;
      barra.classList.remove("esperando");
      barra.classList.add("mudou");
    }
    form.addEventListener("input", marcar);
    form.addEventListener("change", marcar);
  });
})();
