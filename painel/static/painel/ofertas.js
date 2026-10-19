// Tela das ofertas automáticas: mostra só o campo do tipo de busca escolhido e,
// durante o "Testar busca", confere a cada 3 s e recarrega quando terminar.
(function () {
  var tipos = document.querySelectorAll("#tipo-busca input");
  function mostrar() {
    var escolhido = (document.querySelector("#tipo-busca input:checked") || {}).value;
    document.querySelectorAll("[data-tipo]").forEach(function (el) {
      el.hidden = el.dataset.tipo !== escolhido;
    });
  }
  tipos.forEach(function (el) { el.addEventListener("change", mostrar); });
  mostrar();

  var raiz = document.getElementById("ofertas");
  if (!raiz || raiz.dataset.testando !== "1" || !window.fetch) return;
  var tentativas = 0;
  function conferir() {
    tentativas += 1;
    fetch(raiz.dataset.url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (d && !d.testando) { window.location.hash = "teste"; window.location.reload(); return; }
        if (tentativas < 100) setTimeout(conferir, 3000);
      })
      .catch(function () { if (tentativas < 100) setTimeout(conferir, 3000); });
  }
  setTimeout(conferir, 3000);
})();
