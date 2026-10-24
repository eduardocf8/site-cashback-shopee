// Alerta de preço: trava o botão enquanto busca os produtos dos links (pode levar alguns
// segundos com link curto). Os interruptores de "Onde avisar" ficam em campanhas.js.
(function () {
  document.querySelectorAll("form [data-enviando]").forEach(function (botao) {
    botao.form.addEventListener("submit", function () {
      botao.disabled = true;
      botao.textContent = botao.getAttribute("data-enviando");
    });
  });
})();
