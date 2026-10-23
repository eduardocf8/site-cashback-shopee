// Tela de Metas: mostra os campos do tipo de bônus escolhido (faixas fixas ou % do GMV).
(function () {
  var form = document.querySelector("form[data-metas]");
  if (!form) return;
  function atualizar() {
    var tipo = (form.querySelector('input[name="tipo"]:checked') || {}).value || "faixas";
    form.querySelectorAll("[data-bloco]").forEach(function (b) { b.hidden = b.dataset.bloco !== tipo; });
  }
  form.addEventListener("change", atualizar);
  atualizar();
})();
