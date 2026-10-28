// Foto redonda com ajuste (Meu site e Link de entrada): ao escolher o arquivo, abre a janela
// #ajustar-foto para arrastar e dar zoom e envia só o recorte quadrado pelo #form-foto.
(function () {
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
})();
