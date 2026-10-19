// Editor do Meu site: mostra só os campos da vitrine escolhida, troca a foto assim que
// escolhe o arquivo, copia o link e atualiza a prévia enquanto a pessoa digita.
(function () {
  function mostrar() {
    var fonte = (document.querySelector("#fonte-vitrine input:checked") || {}).value;
    document.querySelectorAll("[data-vitrine]").forEach(function (el) { el.hidden = el.dataset.vitrine !== fonte; });
    var tipo = (document.querySelector("#tipo-busca input:checked") || {}).value;
    document.querySelectorAll("[data-tipo]").forEach(function (el) { el.hidden = el.dataset.tipo !== tipo; });
  }
  document.querySelectorAll("#fonte-vitrine input, #tipo-busca input").forEach(function (el) {
    el.addEventListener("change", mostrar);
  });
  mostrar();

  var foto = document.getElementById("campo-foto");
  if (foto) foto.addEventListener("change", function () { if (foto.files.length) document.getElementById("form-foto").submit(); });

  document.querySelectorAll("[data-copiar]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      var texto = botao.dataset.copiar;
      var pronto = function () { var antes = botao.textContent; botao.textContent = "Copiado!"; setTimeout(function () { botao.textContent = antes; }, 1500); };
      if (navigator.clipboard) navigator.clipboard.writeText(texto).then(pronto, function () {});
    });
  });

  // Prévia ao vivo (mesmo domínio: dá para mexer no documento do iframe).
  var previa = document.getElementById("previa");
  function doc() { try { return previa && previa.contentDocument; } catch (e) { return null; } }
  function ligar(nome, aplicar) {
    var campo = document.querySelector('[name="' + nome + '"]');
    if (!campo) return;
    var tratar = function () { var d = doc(); if (d && d.body) aplicar(d, campo); };
    campo.addEventListener("input", tratar);
    campo.addEventListener("change", tratar);
  }
  ligar("nome", function (d, campo) { var h = d.querySelector("h1"); if (h) h.textContent = campo.value || "Seu nome"; });
  ligar("frase", function (d, campo) { var p = d.querySelector(".frase"); if (p) p.textContent = campo.value; });
  // Textos do conversor: em branco volta o padrão (o placeholder do campo).
  ["titulo", "texto", "botao"].forEach(function (parte) {
    ligar("conversor_" + parte, function (d, campo) {
      var el = d.querySelector('[data-conversor="' + parte + '"]');
      if (el) el.textContent = campo.value || campo.placeholder;
    });
  });
  document.querySelectorAll('[name="cor"]').forEach(function (radio) {
    radio.addEventListener("change", function () {
      var d = doc();
      if (d) d.documentElement.style.setProperty("--cor", radio.value);
      var circulo = document.querySelector(".foto-site");
      if (circulo) circulo.style.background = radio.value;
    });
  });
})();
