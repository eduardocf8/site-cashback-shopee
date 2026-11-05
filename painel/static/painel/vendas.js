// Vendas do período (aba Resultados): os filtros de Sub ID e ordem valem assim que
// mudam; a busca vale com Enter ou ao sair do campo.
(function () {
  // No celular a lista mostra 10 vendas por página (no computador, 20). O servidor não
  // sabe o tamanho da tela, então o tipo de tela fica num cookie; se a página veio com
  // o tamanho errado (primeira visita), recarrega uma vez.
  var secao = document.getElementById("vendas");
  if (secao && window.matchMedia) {
    var tela = window.matchMedia("(max-width: 700px)").matches ? "celular" : "computador";
    if (secao.dataset.tela !== tela) {
      document.cookie = "appf_tela=" + tela + "; path=/; max-age=31536000; SameSite=Lax";
      if (document.cookie.indexOf("appf_tela=" + tela) !== -1) { window.location.reload(); return; }
    }
  }

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

// Filtros do topo (período e origem): no celular cada linha rola de lado. Se o chip escolhido
// ficou fora da vista, a linha já abre rolada até ele (só a rolagem muda; o HTML fica igual).
(function () {
  document.querySelectorAll(".chips-rolam").forEach(function (linha) {
    var ativo = linha.querySelector(".chip.ativo");
    if (!ativo || linha.scrollWidth <= linha.clientWidth) return;
    var caixa = linha.getBoundingClientRect(), chip = ativo.getBoundingClientRect();
    if (chip.right > caixa.right || chip.left < caixa.left) {
      linha.scrollLeft += chip.left - caixa.left - (caixa.width - chip.width) / 2;
    }
  });
})();
