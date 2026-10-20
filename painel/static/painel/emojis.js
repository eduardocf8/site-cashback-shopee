/* Botão de emoji nos campos de texto marcados com data-emoji: abre uma paleta e coloca o
 * emoji onde está o cursor (e avisa o campo, para a prévia do site atualizar na hora). */
(function () {
  var EMOJIS = ("🔥 💥 ⚡ ✨ ⭐ 🌟 💯 ✅ 🎉 🎁 🛒 🛍️ 🏷️ 💰 💸 🤑 💲 📦 🚚 ⏰ 🔔 📢 🆕 👉 👇 👆 🔗 💬 📲 📱 " +
                "❤️ 💖 😍 🤩 😊 😉 😎 🥰 👏 🙌 🤝 🙏 💎 👗 👟 👜 💄 🏠 🍳 🧸 👶 🐶 🎮 📚 🏋️ 🌸 ☀️ 🎄 🧡 💚").split(" ");
  var aberta = null;
  var ultimoFocado = null;  // o campo onde a pessoa estava digitando antes de clicar no botão

  function fechar() {
    if (aberta) { aberta.remove(); aberta = null; }
  }

  function inserir(campo, emoji) {
    // Sem o cursor no campo (a pessoa só clicou no botão), o emoji vai no fim do texto.
    var focado = campo === ultimoFocado;
    var ini = !focado || campo.selectionStart == null ? campo.value.length : campo.selectionStart;
    var fim = !focado || campo.selectionEnd == null ? ini : campo.selectionEnd;
    var max = campo.maxLength > 0 ? campo.maxLength : Infinity;
    var novo = campo.value.slice(0, ini) + emoji + campo.value.slice(fim);
    if (novo.length > max) return;
    campo.value = novo;
    campo.focus();
    campo.setSelectionRange(ini + emoji.length, ini + emoji.length);
    campo.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function abrir(botao, campo) {
    fechar();
    var paleta = document.createElement("div");
    paleta.className = "paleta-emoji";
    paleta.setAttribute("role", "dialog");
    paleta.setAttribute("aria-label", "Escolher emoji");
    EMOJIS.forEach(function (emoji) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = emoji;
      b.addEventListener("click", function () { inserir(campo, emoji); fechar(); });
      paleta.appendChild(b);
    });
    botao.parentNode.appendChild(paleta);
    aberta = paleta;
  }

  document.querySelectorAll("input[data-emoji], textarea[data-emoji]").forEach(function (campo) {
    campo.addEventListener("focus", function () { ultimoFocado = campo; });
    var caixa = document.createElement("span");
    caixa.className = "campo-com-emoji" + (campo.tagName === "TEXTAREA" ? " em-texto-longo" : "");
    campo.parentNode.insertBefore(caixa, campo);
    caixa.appendChild(campo);
    var botao = document.createElement("button");
    botao.type = "button";
    botao.className = "botao-emoji";
    botao.title = "Colocar emoji";
    botao.setAttribute("aria-label", "Colocar emoji");
    botao.textContent = "😊";
    botao.addEventListener("click", function (e) {
      e.stopPropagation();
      if (aberta && aberta.parentNode === caixa) fechar(); else abrir(botao, campo);
    });
    caixa.appendChild(botao);
  });

  document.addEventListener("click", function (e) { if (aberta && !aberta.contains(e.target)) fechar(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") fechar(); });
})();
