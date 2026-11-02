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

// Alerta de preço: em cada produto, "Mudar" abre o quadro para escolher se avisa quando o preço
// cair uma % ou chegar a um valor em R$ (com o desconto do Pix opcional) - e mostra a conta.
(function () {
  function reais(v) {
    return "R$ " + v.toFixed(2).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }
  function numero(texto) {
    texto = String(texto || "").replace(/[^\d.,]/g, "");
    if (texto.indexOf(",") >= 0) texto = texto.replace(/\./g, "").replace(",", ".");
    return parseFloat(texto);
  }
  document.querySelectorAll("[data-aviso]").forEach(function (caixa) {
    var form = caixa.querySelector(".editor-aviso");
    var botao = caixa.querySelector("[data-mudar-aviso]");
    var resumo = caixa.querySelector(".resumo-aviso");
    var preco = parseFloat(form.getAttribute("data-preco")) || 0;
    var menor = parseFloat(form.getAttribute("data-menor")) || 0;
    var base = parseFloat(form.getAttribute("data-base")) || preco;
    function atualizar() {
      var tipo = (form.querySelector("input[name=tipo]:checked") || {}).value || "pct";
      form.querySelectorAll("[data-tipo]").forEach(function (v) { v.hidden = v.getAttribute("data-tipo") !== tipo; });
      var pct = numero(form.querySelector("[name=valor_pct]").value);
      form.querySelector("[data-conta-pct]").innerHTML = base && pct > 0 && pct < 100
        ? "avisa em <strong>" + reais(base * (100 - pct) / 100) + "</strong> ou menos" + (preco ? " (hoje " + reais(preco) + ")" : "")
        : "";
      var pix = numero(form.querySelector("[name=desconto_pix]").value) || 0;
      if (pix < 0 || pix > 50) pix = 0;
      var hoje = preco * (100 - pix) / 100;
      var alvo = numero(form.querySelector("[name=valor_reais]").value);
      var texto = preco ? (pix ? "no Pix hoje: <strong>" + reais(hoje) + "</strong> · anúncio " + reais(preco)
                               : "hoje <strong>" + reais(preco) + "</strong>") : "";
      if (menor) texto += " · menor já visto " + reais(menor);
      if (alvo > 0 && preco) {
        texto += alvo >= hoje ? " · <strong>já está nesse preço</strong> (avisa na próxima conferência)"
          : " · <strong>" + Math.round((hoje - alvo) / hoje * 100) + "% abaixo</strong> de hoje";
      }
      form.querySelector("[data-conta-reais]").innerHTML = texto;
      form.querySelector("[data-conta-pix]").innerHTML = pix && alvo > 0
        ? "avisa quando o anúncio chegar a <strong>" + reais(alvo * 100 / (100 - pix)) + "</strong> (" + reais(alvo) + " no Pix)"
        : "";
    }
    botao.addEventListener("click", function () {
      form.hidden = false;
      resumo.hidden = true;
      botao.setAttribute("aria-expanded", "true");
      atualizar();
      var campo = form.querySelector(".valor-aviso:not([hidden]) input");
      if (campo) campo.focus();
    });
    caixa.querySelector("[data-cancelar-aviso]").addEventListener("click", function () {
      form.hidden = true;
      resumo.hidden = false;
      botao.setAttribute("aria-expanded", "false");
    });
    form.addEventListener("change", atualizar);
    form.addEventListener("input", atualizar);
  });
})();
