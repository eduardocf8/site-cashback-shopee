// Tela das ofertas automáticas: mostra só o campo do tipo de busca escolhido, busca
// na lista de grupos e,
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

  // Busca na lista de grupos e canais: filtra pelo nome (sem ligar para acento e
  // maiúscula). Os marcados continuam marcados mesmo escondidos pela busca.
  var busca = document.getElementById("busca-grupos");
  var lista = document.getElementById("lista-grupos");
  var contador = document.getElementById("contador-grupos");
  var nenhum = document.getElementById("nenhum-grupo");
  function normalizar(texto) {
    return (texto || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
  }
  function contar() {
    if (!lista || !contador) return;
    var marcados = lista.querySelectorAll('input[type="checkbox"]:checked').length;
    contador.textContent = marcados ? marcados + " selecionado" + (marcados > 1 ? "s" : "") : "";
  }
  if (busca && lista) {
    busca.addEventListener("input", function () {
      var termo = normalizar(busca.value);
      var visiveis = 0;
      lista.querySelectorAll(".linha-grupo").forEach(function (linha) {
        var mostra = !termo || normalizar(linha.dataset.nome).indexOf(termo) !== -1;
        linha.hidden = !mostra;
        if (mostra) visiveis += 1;
      });
      if (nenhum) nenhum.hidden = visiveis > 0;
    });
    busca.addEventListener("keydown", function (e) {
      if (e.key === "Enter") e.preventDefault(); // Enter na busca não envia o formulário
    });
    lista.addEventListener("change", contar);
    contar();
  }

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
