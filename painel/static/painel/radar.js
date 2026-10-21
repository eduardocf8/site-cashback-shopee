// Radar de ofertas: trocar a ordem busca na hora; "Copiar link" pede o link de afiliado
// ao servidor e copia (se o navegador não deixar copiar, mostra o link para copiar à mão).
(function () {
  document.querySelectorAll("input[data-envia]").forEach(function (el) {
    el.addEventListener("change", function () { el.form.submit(); });
  });
  document.querySelectorAll("form [data-enviando]").forEach(function (botao) {
    botao.form.addEventListener("submit", function () { botao.disabled = true; botao.textContent = botao.getAttribute("data-enviando"); });
  });

  // "Mais filtros": aberto no computador; no celular, só se algum desses filtros estiver em uso.
  var mais = document.querySelector(".mais-filtros");
  if (mais && !mais.hasAttribute("data-em-uso")) mais.open = window.matchMedia("(min-width: 901px)").matches;

  var base = document.querySelector("[data-url-link]");
  if (!base) return;
  var url = base.getAttribute("data-url-link");
  var token = base.querySelector("input[name=csrfmiddlewaretoken]");
  function aviso(texto, tipo) { if (window.avisoFlutuante) window.avisoFlutuante(texto, tipo); }

  document.querySelectorAll("[data-copiar-link]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      var original = botao.innerHTML;
      botao.disabled = true;
      var dados = new FormData();
      dados.append("csrfmiddlewaretoken", token ? token.value : "");
      dados.append("link", botao.getAttribute("data-copiar-link"));
      fetch(url, { method: "POST", body: dados, credentials: "same-origin" })
        .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.erro || ""); return j; }); })
        .then(function (resposta) {
          var copiar = navigator.clipboard && window.isSecureContext ? navigator.clipboard.writeText(resposta.link) : Promise.reject();
          return copiar.then(function () { aviso("Link de afiliado copiado.", "success"); },
                             function () { window.prompt("Copie o seu link de afiliado:", resposta.link); });
        })
        .catch(function (erro) { aviso((erro && erro.message) || "Não deu para gerar o link agora.", "error"); })
        .finally(function () { botao.disabled = false; botao.innerHTML = original; });
    });
  });
})();
