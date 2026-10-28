// Aba Membros do Bot de WhatsApp: busca na lista de grupos, contador "X de 500" (trava os outros no
// limite) e os atalhos "Marcar todos" / "Desmarcar todos" (só os que aparecem na busca).
(function () {
  var busca = document.querySelector('input[data-lista="lista-grupos-membros"]');
  if (!busca) return;
  var lista = document.getElementById("lista-grupos-membros");
  var contador = busca.parentNode.querySelector(".contador");
  var nenhum = lista.querySelector(".nenhum-grupo");
  var maximo = parseInt(busca.dataset.maximo, 10) || 500;
  var caixas = Array.prototype.slice.call(lista.querySelectorAll('input[type="checkbox"]'));

  function normalizar(texto) {
    return (texto || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
  }
  function contar() {
    var marcados = caixas.filter(function (c) { return c.checked; }).length;
    var cheio = marcados >= maximo;
    contador.textContent = marcados + " de " + maximo + " selecionados" + (cheio ? " · limite" : "");
    caixas.forEach(function (c) {
      c.disabled = !c.checked && cheio;
      var linha = c.closest(".linha-grupo");
      if (linha) linha.classList.toggle("travada", c.disabled);
    });
  }
  function visiveis() {
    return caixas.filter(function (c) { return !c.closest(".linha-grupo").hidden; });
  }
  busca.addEventListener("input", function () {
    var termo = normalizar(busca.value);
    var mostrados = 0;
    lista.querySelectorAll(".linha-grupo").forEach(function (linha) {
      var mostra = !termo || normalizar(linha.dataset.nome).indexOf(termo) !== -1;
      linha.hidden = !mostra;
      if (mostra) mostrados += 1;
    });
    if (nenhum) nenhum.hidden = mostrados > 0;
  });
  lista.addEventListener("change", contar);
  document.getElementById("marcar-todos").addEventListener("click", function (e) {
    e.preventDefault();
    var marcados = caixas.filter(function (c) { return c.checked; }).length;
    visiveis().forEach(function (c) {
      if (!c.checked && marcados < maximo) { c.checked = true; marcados += 1; }
    });
    contar();
  });
  document.getElementById("desmarcar-todos").addEventListener("click", function (e) {
    e.preventDefault();
    visiveis().forEach(function (c) { c.checked = false; });
    contar();
  });
  contar();
})();
