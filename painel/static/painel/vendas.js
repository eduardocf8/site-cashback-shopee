// Vendas do período (aba Resultados): os filtros de Sub ID e ordem valem assim que
// mudam; a busca vale com Enter ou ao sair do campo.
(function () {
  var form = document.getElementById("filtros-vendas");
  if (!form) return;
  form.querySelectorAll("select").forEach(function (el) {
    el.addEventListener("change", function () { form.submit(); });
  });
  var busca = form.querySelector('input[name="busca"]');
  var inicial = busca ? busca.value : "";
  if (busca) {
    busca.addEventListener("change", function () { if (busca.value !== inicial) form.submit(); });
    busca.addEventListener("search", function () { if (busca.value !== inicial) form.submit(); }); // botão "x" da busca
  }
})();
