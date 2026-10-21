// Modo campanha: cada interruptor ("Mudar o texto das ofertas", "Enviar a página da
// campanha") apaga os campos do seu bloco quando desligado (o que está neles fica guardado).
(function () {
  document.querySelectorAll("[data-ligado-por]").forEach(function (bloco) {
    var chave = document.getElementById(bloco.getAttribute("data-ligado-por"));
    if (!chave) return;
    function atualizar() {
      bloco.classList.toggle("desligado", !chave.checked);
      // Só leitura, não "disabled": campo desativado não vai junto ao salvar e o texto se perderia.
      bloco.querySelectorAll("input").forEach(function (el) { el.readOnly = !chave.checked; });
      bloco.querySelectorAll("button").forEach(function (el) { el.disabled = !chave.checked; });
    }
    chave.addEventListener("change", atualizar);
    atualizar();
  });
})();

// Marcar ou desmarcar uma data salva na hora (sem precisar do "Salvar" do fim da página).
(function () {
  var lista = document.querySelector(".lista-datas[data-url]");
  if (!lista) return;
  var token = document.querySelector("#form-campanha input[name=csrfmiddlewaretoken]");
  lista.querySelectorAll('input[name="datas_ligadas"]').forEach(function (caixa) {
    caixa.addEventListener("change", function () {
      var linha = caixa.closest("li");
      var dados = new FormData();
      dados.append("csrfmiddlewaretoken", token ? token.value : "");
      dados.append("acao", "marcar_data");
      dados.append("chave", caixa.value);
      dados.append("ligada", caixa.checked ? "1" : "0");
      caixa.disabled = true;
      fetch(lista.getAttribute("data-url"), { method: "POST", body: dados, credentials: "same-origin" })
        .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
        .then(function (resposta) {
          linha.classList.toggle("ligada", caixa.checked);
          var proxima = document.getElementById("proxima-campanha");
          if (proxima) proxima.textContent = resposta.proxima ? "Próxima campanha: " + resposta.proxima + "." : "Nenhuma data marcada nos próximos 12 meses.";
          if (window.avisoFlutuante) window.avisoFlutuante(resposta.texto, "success");
        })
        .catch(function () {
          caixa.checked = !caixa.checked;  // volta como estava
          if (window.avisoFlutuante) window.avisoFlutuante("Não deu para salvar. Tente de novo.", "error");
        })
        .finally(function () { caixa.disabled = false; });
    });
  });
})();
