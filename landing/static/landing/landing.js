window.landingPronta = true;

// Entrada suave dos blocos ao rolar a página: sobem e aparecem quando chegam na tela, e os cartões
// de uma mesma grade entram em sequência. Sem JavaScript, sem IntersectionObserver ou com a opção
// "reduzir movimento" do sistema, tudo aparece de uma vez (ver .js .revelar no CSS).
(function () {
  if (!("IntersectionObserver" in window) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  var GRADES = ".grade-modulos, .passos, .par-planos, .combos-prontos, .grade-notas, .grade-incluso, .faq, .checklist, .faixa-linha";
  var alvos = [];

  function marcar(el, atraso) {
    el.classList.add("revelar");
    if (atraso) el.style.setProperty("--atraso", atraso + "s");
    alvos.push(el);
  }
  document.querySelectorAll(".secao > .miolo, .secao > .miolo-estreito, .faixa > .miolo").forEach(function (bloco) {
    Array.prototype.forEach.call(bloco.children, function (filho) {
      if (filho.matches(GRADES)) {
        Array.prototype.forEach.call(filho.children, function (cartao, i) { marcar(cartao, Math.min(i, 5) * 0.08); });
      } else if (!filho.matches("script, noscript")) {
        marcar(filho, 0);
      }
    });
  });

  var observador = new IntersectionObserver(function (itens) {
    itens.forEach(function (item) {
      if (!item.isIntersecting) return;
      var el = item.target;
      observador.unobserve(el);
      el.classList.add("visivel");
      // Depois de entrar, volta ao estilo normal (senão o atraso da entrada atrapalharia o :hover).
      var limpar = function () { el.classList.remove("revelar", "visivel"); el.style.removeProperty("--atraso"); };
      el.addEventListener("transitionend", limpar, { once: true });
      setTimeout(limpar, 1800);
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
  alvos.forEach(function (el) { observador.observe(el); });
})();

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
