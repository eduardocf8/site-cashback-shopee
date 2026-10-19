// Editor do Meu site: mostra só os campos da vitrine escolhida, troca a foto assim que
// escolhe o arquivo, copia o link e atualiza a prévia enquanto a pessoa digita.
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

  // Foto: abre a janela para ajustar (arrastar e zoom) e envia só o recorte quadrado.
  var foto = document.getElementById("campo-foto");
  var janela = document.getElementById("ajustar-foto");
  if (foto) foto.addEventListener("change", function () {
    if (!foto.files.length) return;
    if (!janela || !janela.showModal || !window.DataTransfer) { document.getElementById("form-foto").submit(); return; }
    abrirAjuste(foto.files[0]);
  });
  function abrirAjuste(arquivo) {
    var tela = janela.querySelector("canvas"), ctx = tela.getContext("2d"), zoom = janela.querySelector('input[type="range"]');
    var L = tela.width, D = L * 0.84;  // D = diâmetro do círculo (o que vai virar a foto)
    var img = new Image(), url = URL.createObjectURL(arquivo);
    var x = 0, y = 0, base = 1, toques = {}, distancia = 0;
    function escala() { return base * parseFloat(zoom.value); }
    function prender() {
      var s = escala(), mx = Math.max(0, (img.width * s - D) / 2), my = Math.max(0, (img.height * s - D) / 2);
      x = Math.min(mx, Math.max(-mx, x)); y = Math.min(my, Math.max(-my, y));
    }
    function desenhar() {
      prender();
      var s = escala(), w = img.width * s, h = img.height * s;
      ctx.clearRect(0, 0, L, L);
      ctx.drawImage(img, L / 2 + x - w / 2, L / 2 + y - h / 2, w, h);
      ctx.save();  // escurece o que fica fora do círculo
      ctx.fillStyle = "rgba(0,0,0,.55)";
      ctx.beginPath(); ctx.rect(0, 0, L, L); ctx.arc(L / 2, L / 2, D / 2, 0, Math.PI * 2, true); ctx.fill("evenodd");
      ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(L / 2, L / 2, D / 2, 0, Math.PI * 2); ctx.stroke();
      ctx.restore();
    }
    function fator() { return L / tela.getBoundingClientRect().width; }  // pixels da tela -> do canvas
    function aoMover(e) {
      if (!toques[e.pointerId]) return;
      var antes = toques[e.pointerId];
      toques[e.pointerId] = { x: e.clientX, y: e.clientY };
      var ids = Object.keys(toques);
      if (ids.length === 2) {  // pinça
        var a = toques[ids[0]], b = toques[ids[1]], d = Math.hypot(a.x - b.x, a.y - b.y);
        if (distancia) zoom.value = Math.min(4, Math.max(1, parseFloat(zoom.value) * d / distancia));
        distancia = d;
      } else {
        x += (e.clientX - antes.x) * fator(); y += (e.clientY - antes.y) * fator();
      }
      desenhar();
    }
    function soltar(e) { delete toques[e.pointerId]; distancia = 0; }
    function aoApertar(e) { tela.setPointerCapture(e.pointerId); toques[e.pointerId] = { x: e.clientX, y: e.clientY }; distancia = 0; }
    function aoRolar(e) { e.preventDefault(); zoom.value = Math.min(4, Math.max(1, parseFloat(zoom.value) * (e.deltaY < 0 ? 1.08 : 0.93))); desenhar(); }
    function fechar() {
      tela.removeEventListener("pointerdown", aoApertar); tela.removeEventListener("pointermove", aoMover);
      tela.removeEventListener("pointerup", soltar); tela.removeEventListener("pointercancel", soltar);
      tela.removeEventListener("wheel", aoRolar); zoom.removeEventListener("input", desenhar);
      janela.querySelector("[data-usar]").onclick = null; janela.querySelector("[data-fechar]").onclick = null;
      janela.onclose = null; URL.revokeObjectURL(url); foto.value = "";
      if (janela.open) janela.close();
    }
    img.onerror = function () { URL.revokeObjectURL(url); document.getElementById("form-foto").submit(); };  // formato que o navegador não abre: o servidor tenta
    img.onload = function () {
      base = D / Math.min(img.width, img.height); zoom.value = 1; x = 0; y = 0;
      tela.addEventListener("pointerdown", aoApertar); tela.addEventListener("pointermove", aoMover);
      tela.addEventListener("pointerup", soltar); tela.addEventListener("pointercancel", soltar);
      tela.addEventListener("wheel", aoRolar, { passive: false }); zoom.addEventListener("input", desenhar);
      janela.querySelector("[data-fechar]").onclick = fechar;
      janela.onclose = fechar;  // Esc
      janela.querySelector("[data-usar]").onclick = function () {
        var saida = document.createElement("canvas"), T = 640, k = T / D, s = escala();
        saida.width = saida.height = T;
        var c = saida.getContext("2d");
        c.fillStyle = "#fff"; c.fillRect(0, 0, T, T);
        c.drawImage(img, (x - img.width * s / 2 + D / 2) * k, (y - img.height * s / 2 + D / 2) * k, img.width * s * k, img.height * s * k);
        saida.toBlob(function (blob) {
          var dt = new DataTransfer();
          dt.items.add(new File([blob], "foto.jpg", { type: "image/jpeg" }));
          janela.onclose = null;
          janela.close();
          foto.files = dt.files;
          document.getElementById("form-foto").submit();
        }, "image/jpeg", 0.9);
      };
      janela.showModal();
      desenhar();
    };
    img.src = url;
  }

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
