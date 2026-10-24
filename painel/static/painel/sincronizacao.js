// Enquanto a tela mostra "Atualizando com a Shopee…", pergunta ao painel a cada 5 s
// se a busca terminou e recarrega a página quando os números novos chegarem.
(function () {
  var caixa = document.querySelector("[data-estado-url]");
  if (!caixa || !window.fetch) return;
  var url = caixa.getAttribute("data-estado-url");
  var texto = caixa.querySelector("[data-estado-texto]");
  var tentativas = 0;
  var maximo = 60; // 5 minutos

  function desistir() {
    if (texto) texto.textContent = "Está demorando mais que o normal. Recarregue a página daqui a pouco.";
  }

  function conferir() {
    tentativas += 1;
    fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (resposta) { return resposta.ok ? resposta.json() : null; })
      .then(function (dados) {
        if (dados && dados.atualizando === false) {
          try { sessionStorage.setItem("appfiliado:atualizado", "1"); } catch (e) { /* segue sem o aviso */ }
          window.location.reload();
        } else if (tentativas < maximo) {
          setTimeout(conferir, 5000);
        } else {
          desistir();
        }
      })
      .catch(function () {
        if (tentativas < maximo) setTimeout(conferir, 5000); else desistir();
      });
  }

  setTimeout(conferir, 5000);
})();
