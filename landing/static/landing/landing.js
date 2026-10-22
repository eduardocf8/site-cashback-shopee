window.landingPronta = true;

// O script de origem da Zouti reescreve a URL sem o "#seção" assim que a página carrega, e sem o "#" o
// navegador não rola até a seção (um link como /#planos, vindo de outra página, abria no topo). Guardamos o
// "#" antes (base.html), devolvemos ao endereço e rolamos até a seção; de novo no "load", se a pessoa ainda não rolou.
(function () {
  var hash = window.hashInicial;
  if (!hash || hash.length < 2) return;
  var ultima = null;
  function ir(aoCarregar) {
    var alvo; try { alvo = document.querySelector(hash); } catch (e) { return; }
    if (!alvo) return;
    if (aoCarregar && ultima !== null && Math.abs(window.scrollY - ultima) > 4) return; // a pessoa já rolou por conta própria
    if (location.hash !== hash) history.replaceState(null, "", location.pathname + location.search + hash);
    var html = document.documentElement, antes = html.style.scrollBehavior;
    html.style.scrollBehavior = "auto"; alvo.scrollIntoView(); html.style.scrollBehavior = antes;
    ultima = window.scrollY;
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { ir(false); }); else ir(false);
  window.addEventListener("load", function () { ir(true); });
  // as fontes e as imagens mudam a altura da página depois da primeira rolagem: acerta de novo, se a pessoa ainda não rolou
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { ir(true); });
  [300, 900, 1800].forEach(function (ms) { setTimeout(function () { ir(true); }, ms); });
})();

// Entrada suave dos blocos ao rolar a página: sobem e aparecem quando chegam na tela, e os cartões
// de uma mesma grade entram em sequência. Sem JavaScript, sem IntersectionObserver ou com a opção
// "reduzir movimento" do sistema, tudo aparece de uma vez (ver .js .revelar no CSS).
(function () {
  if (!("IntersectionObserver" in window) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  var GRADES = ".grade-modulos, .passos, .par-planos, .combos-prontos, .grade-notas, .grade-incluso, .faq, .checklist, .faixa-linha, .linha-passos, .split-itens, .destaque, .lista-recursos, .cartoes-premium, .faixa-recursos, .grade-recursos, .numeros-linha";
  var alvos = [];

  function marcar(el, atraso) {
    el.classList.add("revelar");
    if (atraso) el.style.setProperty("--atraso", atraso + "s");
    alvos.push(el);
  }
  document.querySelectorAll(".secao > .miolo, .secao > .miolo-estreito, .faixa > .miolo, .bloco > .miolo, .numeros > .miolo, #comparar > .miolo").forEach(function (bloco) {
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

// Montador de combo: soma os módulos escolhidos, mostra o desconto e leva ao checkout do produto que bate com a escolha.
(function () {
  var raiz = document.querySelector("[data-montador]");
  var dados = document.getElementById("dados-montador");
  if (!raiz || !dados) return;
  var info = JSON.parse(dados.textContent);
  var brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  var NIVEIS = ["Standard", "Premium"], DESCONTO = { 2: 10, 3: 20 };
  var conta = raiz.querySelector("[data-conta]"), vazio = raiz.querySelector("[data-vazio]"), resultado = raiz.querySelector("[data-resultado]");
  var degraus = document.querySelectorAll("[data-degraus] li"), dica = document.querySelector("[data-dica]");
  var DICAS = {
    0: "Escolha um módulo para começar.",
    1: "Junte mais um módulo e ganhe 10% de desconto.",
    2: "Mais um módulo e o desconto sobe para 20%.",
    3: "Desconto máximo de 20% aplicado."
  };

  function atualizar() {
    var escolha = [], linhas = [];
    info.modulos.forEach(function (m) {
      var marcado = raiz.querySelector('input[name="' + m.codigo + '"]:checked');
      var cartao = raiz.querySelector('[data-modulo="' + m.codigo + '"]');
      var ligado = !!marcado && marcado.value !== "";
      cartao.classList.toggle("escolhido", ligado);
      if (ligado) { escolha.push(m.codigo + marcado.value); linhas.push({ nome: m.nome + " " + NIVEIS[+marcado.value], preco: m.precos[+marcado.value] }); }
    });
    var n = escolha.length, combo = info.combos[escolha.join("+")];
    degraus.forEach(function (li) { var k = +li.dataset.n; li.classList.toggle("ativo", k === n); li.classList.toggle("feito", k < n); });
    if (dica) dica.textContent = DICAS[n];
    conta.classList.toggle("tem", !!combo);
    vazio.inert = !!combo; resultado.inert = !combo;
    if (!combo) return;
    var ul = raiz.querySelector("[data-linhas]"); ul.innerHTML = "";
    linhas.forEach(function (l) {
      var li = document.createElement("li");
      var nome = document.createElement("span"); nome.textContent = l.nome;
      var preco = document.createElement("b"); preco.textContent = brl.format(l.preco);
      li.appendChild(nome); li.appendChild(preco); ul.appendChild(li);
    });
    var economia = Math.round((combo.separado - combo.preco) * 100) / 100;
    var desc = raiz.querySelector("[data-desconto]");
    desc.hidden = !(economia > 0);
    if (economia > 0) {
      raiz.querySelector("[data-desc-rotulo]").textContent = "Desconto do combo (" + DESCONTO[n] + "%)";
      raiz.querySelector("[data-desc-valor]").textContent = "− " + brl.format(economia);
    }
    raiz.querySelector("[data-preco]").textContent = brl.format(combo.preco);
    raiz.querySelector("[data-economia]").textContent = economia > 0 ? "Você economiza " + brl.format(economia) + " por mês." : "";
    var botao = raiz.querySelector("[data-assinar]");
    botao.href = combo.link;
    botao.textContent = n > 1 ? "Assinar este combo" : "Assinar";
  }
  raiz.addEventListener("change", atualizar);
  atualizar();
})();

// Índice fixo das páginas de módulo: destaca a seção que está na tela.
(function () {
  var links = document.querySelectorAll(".subnav a[data-alvo]");
  if (!links.length || !("IntersectionObserver" in window)) return;
  var porId = {}; links.forEach(function (a) { porId[a.dataset.alvo] = a; });
  var visiveis = {};
  var observador = new IntersectionObserver(function (itens) {
    itens.forEach(function (i) { visiveis[i.target.id] = i.isIntersecting ? i.intersectionRatio : 0; });
    var melhor = null, nota = 0;
    Object.keys(visiveis).forEach(function (id) { if (visiveis[id] > nota) { nota = visiveis[id]; melhor = id; } });
    links.forEach(function (a) { a.classList.toggle("ativo", a.dataset.alvo === melhor); });
    var ativo = porId[melhor];
    if (ativo && ativo.scrollIntoView && ativo.parentNode.scrollWidth > ativo.parentNode.clientWidth) { var pai = ativo.parentNode; pai.scrollTo({ left: ativo.offsetLeft - pai.clientWidth / 2 + ativo.clientWidth / 2, behavior: "smooth" }); }
  }, { rootMargin: "-30% 0px -55% 0px", threshold: [0, 0.01, 0.1, 0.5] });
  Object.keys(porId).forEach(function (id) { var el = document.getElementById(id); if (el) observador.observe(el); });
})();
