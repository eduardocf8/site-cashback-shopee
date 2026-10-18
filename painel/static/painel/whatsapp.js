// Tela do Bot de WhatsApp: enquanto algo está acontecendo (QR Code na tela,
// reconectando, mensagem na fila, buscando grupos), pergunta ao painel a cada 3 s
// e atualiza o QR Code ou recarrega a página quando a situação muda.
(function () {
  var raiz = document.getElementById("whatsapp");
  if (!raiz || !window.fetch) return;
  var inicial = {
    estado: raiz.dataset.estado,
    pendentes: Number(raiz.dataset.pendentes || 0),
    grupos: raiz.dataset.grupos === "1",
    semResposta: raiz.dataset.semResposta === "1",
  };
  var ativo = inicial.estado === "aguardando_qr" || inicial.estado === "reconectando" ||
    inicial.pendentes > 0 || inicial.grupos;
  if (!ativo || inicial.semResposta) return;

  var url = raiz.dataset.url;
  var caixa = document.getElementById("qr-caixa");
  var qrAtual = caixa ? caixa.innerHTML : "";
  var tentativas = 0;

  function conferir() {
    tentativas += 1;
    fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return proxima();
        var mudou = d.estado !== inicial.estado || d.sem_resposta ||
          (inicial.pendentes > 0 && d.pendentes < inicial.pendentes) ||
          (inicial.grupos && !d.pedido_grupos);
        if (mudou) { window.location.reload(); return; }
        if (caixa && d.qr && d.qr !== qrAtual) { caixa.innerHTML = d.qr; qrAtual = d.qr; }
        proxima();
      })
      .catch(proxima);
  }

  function proxima() {
    if (tentativas < 400) setTimeout(conferir, 3000); // ~20 minutos
  }

  setTimeout(conferir, 3000);
})();
