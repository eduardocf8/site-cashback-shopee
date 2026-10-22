// Montador de combo: soma os módulos escolhidos e leva ao checkout do produto que bate com a escolha.
(function () {
  var raiz = document.querySelector("[data-montador]");
  var dados = document.getElementById("dados-montador");
  if (!raiz || !dados) return;
  var info = JSON.parse(dados.textContent);
  var brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  var vazio = raiz.querySelector("[data-vazio]"), resultado = raiz.querySelector("[data-resultado]");

  function atualizar() {
    var escolha = [];
    info.modulos.forEach(function (m) {
      var marcado = raiz.querySelector('input[name="' + m.codigo + '"]:checked');
      if (marcado && marcado.value !== "") escolha.push(m.codigo + marcado.value);
    });
    var combo = info.combos[escolha.join("+")];
    vazio.hidden = !!combo;
    resultado.hidden = !combo;
    if (!combo) return;
    raiz.querySelector("[data-nome]").textContent = combo.nome;
    raiz.querySelector("[data-preco]").textContent = brl.format(combo.preco);
    var economia = Math.round((combo.separado - combo.preco) * 100) / 100;
    raiz.querySelector("[data-economia]").textContent = economia > 0
      ? "Separado seria " + brl.format(combo.separado) + ". Você economiza " + brl.format(economia) + " por mês."
      : "";
    var botao = raiz.querySelector("[data-assinar]");
    botao.href = combo.link;
    botao.textContent = escolha.length > 1 ? "Assinar este combo" : "Assinar";
  }
  raiz.addEventListener("change", atualizar);
  atualizar();
})();
