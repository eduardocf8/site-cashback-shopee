// Editor do link de entrada: mostra só os campos do modelo escolhido, abre os campos dos blocos
// ligados, cuida da "outra cor" e atualiza a prévia ao lado enquanto a pessoa edita.
(function () {
  var form = document.getElementById("form-entrada");
  if (!form) return;

  function modelo() { return (form.querySelector('[name="modelo"]:checked') || {}).value; }
  function mostrar() {
    var m = modelo();
    form.querySelectorAll("[data-modelos]").forEach(function (el) { el.hidden = el.dataset.modelos.split(" ").indexOf(m) < 0; });
    form.querySelectorAll("[data-modelo-ajuda]").forEach(function (el) { el.classList.toggle("ativa", el.dataset.modeloAjuda === m); });
    form.querySelectorAll("[data-abre]").forEach(function (caixa) {
      form.querySelectorAll('[data-aberto-por="' + caixa.dataset.abre + '"]').forEach(function (el) { el.hidden = !caixa.checked; });
    });
  }

  // Outra cor: o último círculo abre o seletor do navegador.
  var seletor = document.getElementById("seletor-cor");
  var outra = form.querySelector('[name="cor"][value="outra"]');
  if (outra && seletor) {
    var bolinha = outra.parentNode.querySelector("span");
    var pintar = function () { bolinha.style.setProperty("--cor-escolhida", seletor.value); };
    pintar();
    outra.addEventListener("click", function () {
      try { if (seletor.showPicker) { seletor.showPicker(); return; } } catch (e) { /* segue */ }
      seletor.click();
    });
    seletor.addEventListener("input", function () { outra.checked = true; pintar(); atualizar(); });
  }

  // Prévia: a página de verdade, montada pelo servidor com o que está no formulário (sem salvar).
  var previa = document.getElementById("previa");
  var FORA_DA_PREVIA = ["csrfmiddlewaretoken", "acao", "grupos", "admins_dos_novos", "slug", "pixel_id", "limite_por_grupo"];
  var espera = null;
  function atualizar() {
    mostrar();
    if (!previa) return;
    clearTimeout(espera);
    espera = setTimeout(function () {
      var dados = new URLSearchParams();
      new FormData(form).forEach(function (valor, nome) { if (FORA_DA_PREVIA.indexOf(nome) < 0) dados.append(nome, valor); });
      var rolagem = 0;
      try { rolagem = previa.contentWindow.scrollY; } catch (e) { /* segue */ }
      previa.onload = function () { try { previa.contentWindow.scrollTo(0, rolagem); } catch (e) { /* segue */ } };
      previa.src = previa.dataset.url + "?" + dados.toString();
    }, 350);
  }
  form.addEventListener("input", atualizar);
  form.addEventListener("change", atualizar);
  mostrar();

  // A prévia mostra a página na largura de um celular (390px) e reduz para caber na moldura.
  var celular = previa && previa.parentNode;
  function encaixar() {
    if (!celular) return;
    var escala = celular.clientWidth / 390;
    previa.style.width = "390px";
    previa.style.height = (celular.clientHeight / escala) + "px";
    previa.style.transform = "scale(" + escala + ")";
    previa.style.transformOrigin = "0 0";
  }
  encaixar();
  if (window.ResizeObserver && celular) new ResizeObserver(encaixar).observe(celular);
})();

// "Mudar o endereço": leva até o campo e já deixa pronto para digitar.
document.querySelectorAll("[data-ir-para-campo]").forEach(function (link) {
  link.addEventListener("click", function (e) {
    var campo = document.querySelector(link.getAttribute("href"));
    if (!campo) return;
    e.preventDefault();
    campo.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(function () { campo.focus(); campo.select(); }, 400);
  });
});
