// Tela das ofertas automáticas: mostra só os campos do modo e do tipo de busca
// escolhidos, busca nas listas de grupos e mantém os cartões de status e de ofertas
// atualizados sozinhos.
(function () {
  function mostrar() {
    var modo = (document.querySelector("#modo input:checked") || {}).value;
    document.querySelectorAll("[data-modo]").forEach(function (el) {
      el.hidden = el.dataset.modo !== modo;
    });
    var escolhido = (document.querySelector("#tipo-busca input:checked") || {}).value;
    document.querySelectorAll("[data-tipo]").forEach(function (el) {
      el.hidden = el.dataset.tipo !== escolhido;
    });
  }
  document.querySelectorAll("#modo input, #tipo-busca input").forEach(function (el) {
    el.addEventListener("change", mostrar);
  });
  // Horários em 24 h: põe os ":" sozinho (digitar "0730" vira "07:30").
  document.querySelectorAll("input[data-hora]").forEach(function (campo) {
    campo.addEventListener("input", function () {
      var digitos = campo.value.replace(/\D/g, "").slice(0, 4);
      campo.value = digitos.length > 2 ? digitos.slice(0, 2) + ":" + digitos.slice(2) : digitos;
    });
    campo.addEventListener("blur", function () {
      var m = campo.value.match(/^(\d{1,2}):?(\d{0,2})$/);
      if (m && campo.value) campo.value = ("0" + m[1]).slice(-2) + ":" + ((m[2] || "00") + "0").slice(0, 2);
    });
  });

  // Os tipos de revisão só aparecem com a IA ligada.
  var iaAtiva = document.querySelector('input[name="ia_ativa"]');
  var tiposIa = document.getElementById("tipos-ia");
  if (iaAtiva && tiposIa) {
    var mostrarTipos = function () { tiposIa.hidden = !iaAtiva.checked; };
    iaAtiva.addEventListener("change", mostrarTipos);
    mostrarTipos();
  }
  mostrar();

  // Busca nas listas de grupos e canais (destinos e origens): filtra pelo nome sem
  // ligar para acento e maiúscula. Os marcados continuam marcados mesmo escondidos.
  function normalizar(texto) {
    return (texto || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
  }
  document.querySelectorAll("input[data-lista]").forEach(function (busca) {
    var lista = document.getElementById(busca.dataset.lista);
    if (!lista) return;
    var contador = busca.parentNode.querySelector(".contador");
    var nenhum = lista.querySelector(".nenhum-grupo");
    function contar() {
      if (!contador) return;
      var marcados = lista.querySelectorAll('input[type="checkbox"]:checked').length;
      contador.textContent = marcados ? marcados + " selecionado" + (marcados > 1 ? "s" : "") : "";
    }
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
  });

  // Tela ao vivo: a cada 5 s pergunta ao servidor se algo mudou (oferta enviada,
  // recebida, status). Se mudou, busca a página de novo e troca só os cartões marcados
  // com data-ao-vivo - o formulário fica como está, sem perder o que a pessoa digitou.
  // Durante o "Testar busca", recarrega a página quando o teste termina.
  var raiz = document.getElementById("ofertas");
  if (!raiz || !window.fetch || !window.DOMParser) return;
  var versao = raiz.dataset.versao;
  var testando = raiz.dataset.testando === "1";
  var INTERVALO = 5000;

  // O aviso verde de "ligadas" some quando a primeira oferta nova sair de verdade.
  function ultimaQueSaiu(raizDoc) {
    var maior = 0;
    raizDoc.querySelectorAll("#cartao-enviadas [data-saiu]").forEach(function (li) {
      maior = Math.max(maior, parseInt(li.dataset.saiu, 10) || 0);
    });
    return maior;
  }
  var saiuAteAgora = ultimaQueSaiu(document);
  function esconderAvisoSeSaiu() {
    var agora = ultimaQueSaiu(document);
    if (agora <= saiuAteAgora) return;
    saiuAteAgora = agora;
    document.querySelectorAll("[data-some-ao-enviar]").forEach(function (aviso) {
      aviso.style.transition = "opacity .4s";
      aviso.style.opacity = "0";
      setTimeout(function () {
        var lista = aviso.parentNode;
        aviso.remove();
        if (lista && !lista.children.length) lista.remove();
      }, 400);
    });
  }

  function trocarCartoes() {
    return fetch(window.location.pathname, { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) {
        if (!html) return;
        var nova = new DOMParser().parseFromString(html, "text/html");
        document.querySelectorAll("[data-ao-vivo]").forEach(function (cartao) {
          var novo = nova.getElementById(cartao.id);
          if (novo) cartao.replaceWith(document.importNode(novo, true));
        });
        var novaRaiz = nova.getElementById("ofertas");
        if (novaRaiz) versao = novaRaiz.dataset.versao;
        esconderAvisoSeSaiu();
      });
  }

  function conferir() {
    if (document.hidden) { setTimeout(conferir, INTERVALO); return; }
    fetch(raiz.dataset.url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return;
        if (testando && !d.testando) { window.location.hash = "teste"; window.location.reload(); return "parar"; }
        testando = !!d.testando;
        if (d.versao && d.versao !== versao) return trocarCartoes();
      })
      .catch(function () {})
      .then(function (fim) { if (fim !== "parar") setTimeout(conferir, INTERVALO); });
  }
  setTimeout(conferir, INTERVALO);
})();
