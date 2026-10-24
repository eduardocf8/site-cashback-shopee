/* Cartões que minimizam/expandem: um botão com data-recolher="<nome>" e aria-controls="<id do
 * corpo>". Cada pessoa tem a escolha lembrada neste navegador. Se a página abrir apontando para o
 * cartão (ex: #teste depois de "Testar busca"), ele abre. */
(function () {
  document.querySelectorAll('[data-recolher]').forEach(function (botao) {
    var chave = 'appfiliado:recolhido:' + botao.getAttribute('data-recolher');
    var corpo = document.getElementById(botao.getAttribute('aria-controls'));
    var cartao = botao.closest('section') || botao.parentElement;
    if (!corpo) return;
    function aplicar(recolhido) {
      cartao.classList.toggle('recolhido', recolhido);
      corpo.hidden = recolhido;
      botao.setAttribute('aria-expanded', String(!recolhido));
      botao.title = recolhido ? 'Expandir' : 'Minimizar';
    }
    var recolhido = false;
    try { recolhido = localStorage.getItem(chave) === '1'; } catch (e) { /* sem localStorage: aberto */ }
    if (cartao.id && location.hash === '#' + cartao.id) recolhido = false;
    aplicar(recolhido);
    botao.addEventListener('click', function () {
      recolhido = !recolhido;
      aplicar(recolhido);
      try { localStorage.setItem(chave, recolhido ? '1' : '0'); } catch (e) { /* segue sem lembrar */ }
    });
  });
})();
