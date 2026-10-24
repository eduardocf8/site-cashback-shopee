// Aba Mensagens do Bot: mostra só os campos de "pra quem" e "quando" escolhidos, monta a
// prévia (com a formatação do WhatsApp e a foto) e filtra a lista de grupos.
(function () {
  var form = document.getElementById("form-mensagem");
  if (!form) return;

  function escolhido(id) { return (document.querySelector("#" + id + " input:checked") || {}).value; }
  function mostrar() {
    var destino = escolhido("destino"), quando = escolhido("quando");
    document.querySelectorAll("[data-destino]").forEach(function (el) { el.hidden = el.dataset.destino !== destino; });
    document.querySelectorAll("[data-quando]").forEach(function (el) { el.hidden = el.dataset.quando !== quando; });
    var botao = document.getElementById("botao-mensagem");
    botao.textContent = quando === "agora" ? botao.dataset.agora : botao.dataset.agendar;
  }
  document.querySelectorAll("#destino input, #quando input").forEach(function (el) { el.addEventListener("change", mostrar); });
  mostrar();

  // Embaixo da escolha do nicho: os grupos que estão nele.
  var seletorNicho = form.querySelector("select[name=nicho]");
  var dadosNicho = document.getElementById("dados-grupos-por-nicho");
  if (seletorNicho && dadosNicho) {
    var gruposPorNicho = JSON.parse(dadosNicho.textContent);
    var mostrarGrupos = function () {
      var nomes = gruposPorNicho[seletorNicho.value];
      document.getElementById("grupos-do-nicho").textContent = nomes ? "Vai pra: " + nomes + "." : "";
    };
    seletorNicho.addEventListener("change", mostrarGrupos);
    mostrarGrupos();
  }

  // Prévia: *negrito*, _itálico_, ~riscado~ e as quebras de linha, como no WhatsApp.
  var texto = form.querySelector("textarea[name=texto]");
  var previa = document.getElementById("previa-texto");
  var contador = form.querySelector(".contador-texto");
  function escapar(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function formatar(s) {
    return escapar(s)
      .replace(/(^|[\s(])\*([^*\n]+)\*(?=$|[\s.,!?:;)\]])/g, "$1<strong>$2</strong>")
      .replace(/(^|[\s(])_([^_\n]+)_(?=$|[\s.,!?:;)\]])/g, "$1<em>$2</em>")
      .replace(/(^|[\s(])~([^~\n]+)~(?=$|[\s.,!?:;)\]])/g, "$1<s>$2</s>")
      .replace(/(https?:\/\/[^\s<]+)/g, '<span class="link-previa">$1</span>')
      .replace(/\n/g, "<br>");
  }
  function atualizar() {
    previa.innerHTML = texto.value.trim() ? formatar(texto.value) : '<span class="suave">Sua mensagem aparece aqui.</span>';
    if (contador) {
      var maximo = parseInt(contador.dataset.maximo, 10);
      contador.textContent = texto.value.length + " de " + maximo + " caracteres.";
      contador.classList.toggle("erro", texto.value.length > maximo);
    }
  }
  texto.addEventListener("input", atualizar);
  atualizar();

  var foto = document.getElementById("previa-foto");
  var atual = document.getElementById("foto-atual");
  var remover = document.getElementById("remover-foto");
  var arquivo = form.querySelector("input[type=file]");
  function mostrarFoto() {
    if (arquivo.files && arquivo.files[0]) {
      foto.src = URL.createObjectURL(arquivo.files[0]);
      foto.hidden = false;
    } else if (atual && !(remover && remover.checked)) {
      foto.src = atual.src;
      foto.hidden = false;
    } else {
      foto.hidden = true;
    }
  }
  arquivo.addEventListener("change", mostrarFoto);
  if (remover) remover.addEventListener("change", mostrarFoto);
  mostrarFoto();

  // Hora em 24 h: põe os ":" sozinho ("2030" vira "20:30").
  form.querySelectorAll("input[data-hora]").forEach(function (campo) {
    campo.addEventListener("input", function () {
      var d = campo.value.replace(/\D/g, "").slice(0, 4);
      campo.value = d.length > 2 ? d.slice(0, 2) + ":" + d.slice(2) : d;
    });
  });

  // Busca na lista de grupos.
  function normalizar(s) { return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim(); }
  document.querySelectorAll("input[data-lista]").forEach(function (busca) {
    var lista = document.getElementById(busca.dataset.lista);
    var contadorGrupos = busca.parentNode.querySelector(".contador");
    function contar() {
      var n = lista.querySelectorAll("input:checked").length;
      contadorGrupos.textContent = n ? n + " selecionado" + (n > 1 ? "s" : "") : "";
    }
    busca.addEventListener("input", function () {
      var termo = normalizar(busca.value), visiveis = 0;
      lista.querySelectorAll(".linha-grupo").forEach(function (linha) {
        var mostra = !termo || normalizar(linha.dataset.nome).indexOf(termo) !== -1;
        linha.hidden = !mostra;
        if (mostra) visiveis += 1;
      });
      lista.querySelector(".nenhum-grupo").hidden = visiveis > 0;
    });
    busca.addEventListener("keydown", function (e) { if (e.key === "Enter") e.preventDefault(); });
    lista.addEventListener("change", contar);
    contar();
  });
})();
