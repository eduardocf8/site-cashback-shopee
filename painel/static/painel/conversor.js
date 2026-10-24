// Conversor de links: mostra a explicação do modo escolhido, trava o botão enquanto
// converte (pode levar alguns segundos com link curto) e copia o resultado.
(function () {
  var form = document.getElementById("form-conversor");
  if (!form) return;

  function mostrarAjudaDoModo() {
    var marcado = form.querySelector('input[name="modo"]:checked');
    form.querySelectorAll("[data-modo]").forEach(function (el) {
      el.hidden = !marcado || el.getAttribute("data-modo") !== marcado.value;
    });
  }
  form.querySelectorAll('input[name="modo"]').forEach(function (r) { r.addEventListener("change", mostrarAjudaDoModo); });
  mostrarAjudaDoModo();

  form.addEventListener("submit", function () {
    var botao = form.querySelector("[data-convertendo]");
    if (botao) { botao.disabled = true; botao.textContent = botao.getAttribute("data-convertendo"); }
  });

  var copiar = document.getElementById("copiar-resultado");
  var resultado = document.getElementById("resultado");
  // O resultado cresce até caber o texto todo (até 640px), para conferir sem rolar.
  function crescer() { resultado.style.height = "auto"; resultado.style.height = Math.min(resultado.scrollHeight + 4, 640) + "px"; }
  if (resultado) {
    resultado.addEventListener("input", crescer); crescer();
    // No celular o resultado fica embaixo do formulário: vai direto para ele.
    if (window.matchMedia("(max-width: 900px)").matches) resultado.closest(".card").scrollIntoView({ block: "start" });
  }
  if (copiar && resultado) {
    copiar.addEventListener("click", function () {
      function pronto() { if (window.avisoFlutuante) window.avisoFlutuante("Copiado. É só colar onde quiser.", "success"); }
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(resultado.value).then(pronto, function () { resultado.select(); document.execCommand("copy"); pronto(); });
      } else {
        resultado.select(); document.execCommand("copy"); pronto();
      }
    });
  }
})();
