// Tela das ofertas automáticas: mostra só os campos do modo e do tipo de busca
// escolhidos, busca nas listas de grupos e mantém os cartões de status e de ofertas
// atualizados sozinhos.
(function () {
  function mostrar() {
    var modo = (document.querySelector("#modo input:checked") || {}).value;
    document.querySelectorAll("[data-modo]").forEach(function (el) {
      el.hidden = el.dataset.modo !== modo;
    });
    // Copiando de grupos, vale sempre o envio pra todos.
    var envio = modo === "shopee" ? (document.querySelector("#modo-envio input:checked") || {}).value || "todos" : "todos";
    document.querySelectorAll("[data-envio]").forEach(function (el) {
      el.hidden = el.dataset.envio !== envio;
    });
    var listaGrupos = document.getElementById("lista-grupos");
    if (listaGrupos) {
      var antes = listaGrupos.classList.contains("por-nicho");
      listaGrupos.classList.toggle("por-nicho", envio === "nicho");
      if (envio === "nicho" && !antes) sincronizarGrupos();
    }
    var escolhido = (document.querySelector("#tipo-busca input:checked") || {}).value;
    document.querySelectorAll("[data-tipo]").forEach(function (el) {
      el.hidden = el.dataset.tipo !== escolhido;
    });
  }
  document.querySelectorAll("#modo input, #modo-envio input, #tipo-busca input").forEach(function (el) {
    el.addEventListener("change", mostrar);
  });

  // Envio por nicho: os nichos (nome, categorias, palavra-chave) e, na lista de grupos,
  // o nicho de cada grupo. Por nicho, recebe as ofertas o grupo que está num nicho.
  var listaNichos = document.getElementById("lista-nichos");
  var modeloNicho = document.getElementById("modelo-nicho");
  function nichos() {
    return listaNichos ? Array.prototype.map.call(listaNichos.querySelectorAll(".nicho"), function (card) {
      return { id: card.dataset.nicho, nome: card.querySelector("[data-nome-nicho]").value.trim(), card: card };
    }) : [];
  }
  function sincronizarGrupos() {
    var listaGrupos = document.getElementById("lista-grupos");
    if (!listaGrupos || !listaGrupos.classList.contains("por-nicho")) return;
    document.querySelectorAll("select.nicho-do-grupo").forEach(function (sel) {
      var caixa = sel.closest(".linha-grupo").querySelector('input[type="checkbox"]');
      if (caixa) caixa.checked = !!sel.value;
    });
    // recalcula o contador e o limite do plano
    listaGrupos.dispatchEvent(new Event("change"));
  }
  function atualizarNichos() {
    var lista = nichos();
    document.querySelectorAll("select.nicho-do-grupo").forEach(function (sel) {
      var valor = sel.value;
      while (sel.options.length > 1) sel.remove(1);
      lista.forEach(function (n) { sel.add(new Option(n.nome || "(sem nome)", n.id)); });
      sel.value = lista.some(function (n) { return n.id === valor; }) ? valor : "";
    });
    lista.forEach(function (n) {
      var total = document.querySelectorAll('select.nicho-do-grupo option[value="' + n.id + '"]:checked').length;
      n.card.querySelector("[data-grupos-do-nicho]").textContent = total + (total === 1 ? " grupo" : " grupos");
      var marcadas = Array.prototype.map.call(n.card.querySelectorAll(".nicho-categorias input:checked"), function (c) {
        return c.nextElementSibling.textContent.split(" (")[0];
      });
      n.card.querySelector("[data-resumo-categorias]").textContent = marcadas.length ? marcadas.join(", ") : "todas";
    });
    var botao = document.getElementById("adicionar-nicho");
    if (botao && listaNichos) botao.disabled = lista.length >= parseInt(listaNichos.dataset.maximo, 10);
  }
  if (listaNichos && modeloNicho) {
    document.getElementById("adicionar-nicho").addEventListener("click", function () {
      var id = "n" + Math.random().toString(36).slice(2, 10).replace(/[^a-z0-9]/g, "");
      var caixa = document.createElement("div");
      caixa.innerHTML = modeloNicho.innerHTML.replace(/__ID__/g, id);
      var card = caixa.firstElementChild;
      listaNichos.appendChild(card);
      atualizarNichos();
      card.querySelector("[data-nome-nicho]").focus();
    });
    listaNichos.addEventListener("click", function (e) {
      var botao = e.target.closest("[data-tirar-nicho]");
      if (!botao) return;
      botao.closest(".nicho").remove();
      atualizarNichos();
      sincronizarGrupos();
    });
    listaNichos.addEventListener("input", atualizarNichos);
    listaNichos.addEventListener("change", atualizarNichos);
    document.querySelectorAll("select.nicho-do-grupo").forEach(function (sel) {
      sel.addEventListener("change", function () { sincronizarGrupos(); atualizarNichos(); });
    });
    atualizarNichos();
  }
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
      var maximo = parseInt(busca.dataset.maximo, 10);
      if (maximo) {
        // Limite do plano: com o máximo marcado, os outros ficam travados até desmarcar algum.
        var cheio = marcados >= maximo;
        contador.textContent = marcados + " de " + maximo + " selecionados" + (cheio ? " · limite do plano" : "");
        lista.querySelectorAll('input[type="checkbox"]').forEach(function (caixa) {
          caixa.disabled = !caixa.checked && cheio;
          var linha = caixa.closest(".linha-grupo");
          var nichoDoGrupo = linha && linha.querySelector("select.nicho-do-grupo");
          if (nichoDoGrupo) nichoDoGrupo.disabled = caixa.disabled;
          if (linha) {
            linha.classList.toggle("travada", caixa.disabled);
            linha.title = caixa.disabled ? "Seu plano permite até " + maximo + " grupos e canais. Desmarque um para escolher outro." : "";
          }
        });
        return;
      }
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
