// Editor do Meu site: mostra só os campos da vitrine escolhida (a foto fica em foto_recorte.js),
// copia o link e atualiza a prévia enquanto a pessoa digita.
(function () {
  function mostrar() {
    var fonte = (document.querySelector("#fonte-vitrine input:checked") || {}).value;
    document.querySelectorAll("[data-vitrine]").forEach(function (el) { el.hidden = el.dataset.vitrine !== fonte; });
    document.querySelectorAll("[data-sem-vitrine-esconde]").forEach(function (el) { el.hidden = fonte === "nenhuma"; });
    var tipo = (document.querySelector("#tipo-busca input:checked") || {}).value;
    document.querySelectorAll("[data-tipo]").forEach(function (el) { el.hidden = el.dataset.tipo !== tipo; });
  }
  document.querySelectorAll("#fonte-vitrine input, #tipo-busca input").forEach(function (el) {
    el.addEventListener("change", mostrar);
  });
  mostrar();

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
  ligar("nome", function (d, campo) { var f = d.querySelector(".foto"); if (f && !f.querySelector("img")) f.textContent = (Array.from(campo.value.trim())[0] || "?").toUpperCase(); });
  // Formato da vitrine (lista ou carrossel) muda na prévia na hora.
  document.querySelectorAll('[name="vitrine_formato"]').forEach(function (radio) {
    radio.addEventListener("change", function () {
      var d = doc();
      var lista = d && d.getElementById("lista-vitrine");
      if (!lista) return;
      var carrossel = radio.value === "carrossel";
      lista.classList.toggle("carrossel", carrossel);
      d.getElementById("moldura-vitrine").classList.toggle("em-carrossel", carrossel);
    });
  });
  // Textos do conversor: em branco volta o padrão (o placeholder do campo).
  ["titulo", "texto", "botao"].forEach(function (parte) {
    ligar("conversor_" + parte, function (d, campo) {
      var el = d.querySelector('[data-conversor="' + parte + '"]');
      if (el) el.textContent = campo.value || campo.placeholder;
    });
  });
  // Cor: as mesmas contas de meusite/cores.py, para a prévia ficar igual ao site.
  function rgb(c) { return [1, 3, 5].map(function (i) { return parseInt(c.substr(i, 2), 16); }); }
  function misturar(a, b, peso) {
    var x = rgb(a), y = rgb(b);
    return "#" + x.map(function (v, i) { return ("0" + Math.round(v * peso + y[i] * (1 - peso)).toString(16)).slice(-2); }).join("").toUpperCase();
  }
  function luminancia(c) {
    var k = rgb(c).map(function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2];
  }
  function tema(cor) {
    var fundo = misturar(cor, "#1A1A1A", 0.78), escuro = luminancia(fundo) > 0.22, texto = cor;
    while (luminancia(texto) > 0.3) texto = misturar(texto, "#000000", 0.85);
    return {
      "--cor": cor, "--fundo": fundo, "--tinta": escuro ? "#1C2B23" : "#FFFFFF",
      "--tinta-suave": escuro ? "rgba(28,43,35,.75)" : "rgba(255,255,255,.82)",
      "--vidro": escuro ? "rgba(0,0,0,.08)" : "rgba(255,255,255,.16)",
      "--sobre-cor": luminancia(cor) > 0.22 ? "#1C2B23" : "#FFFFFF", "--cor-texto": texto,
    };
  }
  var seletor = document.getElementById("seletor-cor");
  var outra = document.querySelector('[name="cor"][value="outra"]');
  function corEscolhida() {
    var marcada = document.querySelector('[name="cor"]:checked');
    if (!marcada) return null;
    return marcada.value === "outra" ? (seletor && seletor.value.toUpperCase()) : marcada.value;
  }
  function aplicarCor() {
    var cor = corEscolhida();
    if (!cor) return;
    var d = doc(), vars = tema(cor);
    if (d) Object.keys(vars).forEach(function (k) { d.documentElement.style.setProperty(k, vars[k]); });
    var circulo = document.querySelector(".foto-site");
    if (circulo) circulo.style.background = cor;
  }
  document.querySelectorAll('[name="cor"]').forEach(function (radio) { radio.addEventListener("change", aplicarCor); });
  if (outra && seletor) {
    var bolinha = outra.parentNode.querySelector("span");
    var pintar = function () { bolinha.style.setProperty("--cor-escolhida", seletor.value); };
    pintar();
    outra.addEventListener("click", function () {
      try { if (seletor.showPicker) { seletor.showPicker(); return; } } catch (e) { /* segue */ }
      seletor.click();
    });
    seletor.addEventListener("input", function () { outra.checked = true; pintar(); aplicarCor(); });
  }
  // Estilo do site (fundo colorido ou claro).
  document.querySelectorAll('[name="layout"]').forEach(function (radio) {
    radio.addEventListener("change", function () {
      var d = doc();
      if (d && d.body) d.body.className = "tema-" + radio.value;
    });
  });

  // Botões: o que a pessoa digita (antes de salvar) já aparece na prévia.
  function navBotoes(d) {
    var nav = d.querySelector("nav.botoes");
    if (nav) nav.hidden = !nav.querySelector("[data-botao]:not([hidden])");
  }
  document.querySelectorAll("[data-botao-texto]").forEach(function (campo) {
    campo.addEventListener("input", function () {
      var d = doc(), link = d && d.querySelector('[data-botao="' + campo.dataset.botaoTexto + '"]');
      if (!link) return;
      link.textContent = campo.value;
      if (campo.dataset.botaoTexto === "novo") link.hidden = !campo.value.trim();
      navBotoes(d);
    });
  });
  document.querySelectorAll("[data-botao-destaque]").forEach(function (caixa) {
    caixa.addEventListener("change", function () {
      var d = doc(), link = d && d.querySelector('[data-botao="' + caixa.dataset.botaoDestaque + '"]');
      if (link) link.classList.toggle("destaque", caixa.checked);
    });
  });
  // Redes sociais: o ícone aparece assim que o campo tem alguma coisa e some quando esvazia.
  document.querySelectorAll('input[name^="rede_"]').forEach(function (campo) {
    campo.addEventListener("input", function () {
      var d = doc(), rede = campo.name.slice(5), icone = d && d.querySelector('[data-rede="' + rede + '"]');
      if (!icone) return;
      icone.hidden = !campo.value.trim();
      var nav = d.querySelector("[data-redes]");
      if (nav) nav.hidden = !nav.querySelector("[data-rede]:not([hidden])");
    });
  });
  // Conversor ligado/desligado e vitrine sim/não.
  ligar("mostrar_conversor", function (d, campo) { var c = d.getElementById("conversor"); if (c) c.hidden = !campo.checked; });
  document.querySelectorAll('#fonte-vitrine input').forEach(function (radio) {
    radio.addEventListener("change", function () {
      var d = doc(), secao = d && d.getElementById("secao-vitrine");
      if (secao && radio.checked) secao.hidden = radio.value === "nenhuma";
    });
  });

  // Categoria de cada produto da vitrine: salva na hora e recarrega a prévia.
  var listaProdutos = document.querySelector("[data-url-categoria]");
  if (listaProdutos) {
    var csrf = (document.querySelector('#form-site [name="csrfmiddlewaretoken"]') || {}).value;
    listaProdutos.querySelectorAll(".categoria-produto").forEach(function (select) {
      select.addEventListener("change", function () {
        var url = listaProdutos.dataset.urlCategoria.replace("/0/", "/" + select.dataset.produto + "/");
        var corpo = new FormData();
        corpo.append("categoria", select.value);
        select.disabled = true;
        fetch(url, { method: "POST", body: corpo, headers: { "X-CSRFToken": csrf }, credentials: "same-origin" })
          .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
          .then(function () {
            select.classList.add("salvo");
            setTimeout(function () { select.classList.remove("salvo"); }, 1200);
            if (previa && previa.contentWindow) previa.contentWindow.location.reload();
          })
          .catch(function () { alert("Não consegui salvar a categoria agora. Tente de novo."); })
          .finally(function () { select.disabled = false; });
      });
    });
  }

  // A prévia mostra o site na largura de um celular (390px) e reduz para caber na moldura.
  var celular = previa && previa.parentNode;
  function encaixar() {
    if (!celular) return;
    var largura = celular.clientWidth, escala = largura / 390;
    previa.style.width = "390px";
    previa.style.height = (celular.clientHeight / escala) + "px";
    previa.style.transform = "scale(" + escala + ")";
    previa.style.transformOrigin = "0 0";
  }
  encaixar();
  if (window.ResizeObserver && celular) new ResizeObserver(encaixar).observe(celular);
})();
