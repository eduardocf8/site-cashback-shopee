// Modo campanha: com "Usar a mensagem da campanha" desligado, os campos da mensagem
// ficam apagados (o que está neles continua guardado para a próxima vez).
(function () {
  var chave = document.getElementById("id_mensagem_ativa");
  var bloco = document.getElementById("bloco-mensagem");
  if (!chave || !bloco) return;
  function atualizar() {
    bloco.classList.toggle("desligado", !chave.checked);
    // Só leitura, não "disabled": campo desativado não vai junto ao salvar e o texto se perderia.
    bloco.querySelectorAll("input").forEach(function (el) { el.readOnly = !chave.checked; });
    bloco.querySelectorAll("button").forEach(function (el) { el.disabled = !chave.checked; });
  }
  chave.addEventListener("change", atualizar);
  atualizar();
})();
