/* Avisos do painel e posição da página depois de salvar.
 * - Ao enviar um formulário, a página volta para a mesma posição quando recarregar (em vez
 *   de pular para o topo ou para uma seção).
 * - Os avisos ("Salvo", erros) flutuam no topo da tela e somem sozinhos: os de sucesso e
 *   informação em 5 segundos, os de erro em 10. Dá para fechar antes no "×". */
(function () {
  var CHAVE = 'appfiliado:posicao';

  document.addEventListener('submit', function (evento) {
    var form = evento.target;
    if (evento.defaultPrevented || !form || (form.method || '').toLowerCase() !== 'post') return;
    try {
      sessionStorage.setItem(CHAVE, JSON.stringify({ caminho: location.pathname, y: window.scrollY, em: Date.now() }));
    } catch (e) { /* navegador sem sessionStorage: segue normal */ }
  });

  var salvo = null;
  try {
    salvo = JSON.parse(sessionStorage.getItem(CHAVE) || 'null');
    sessionStorage.removeItem(CHAVE);
  } catch (e) { salvo = null; }
  // Só na mesma tela e logo depois do envio (um formulário que baixa arquivo não recarrega a página).
  if (salvo && salvo.caminho === location.pathname && Date.now() - salvo.em < 15000) {
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
    var voltar = function () { window.scrollTo(0, salvo.y); };
    voltar();
    window.addEventListener('load', voltar); // de novo depois que fontes e imagens carregam
  }

  document.querySelectorAll('.avisos-flutuantes .aviso').forEach(function (aviso) {
    var fechado = false;
    function fechar() {
      if (fechado) return;
      fechado = true;
      aviso.classList.add('saindo');
      setTimeout(function () { aviso.remove(); }, 300);
    }
    var botao = aviso.querySelector('.aviso-fechar');
    if (botao) botao.addEventListener('click', fechar);
    setTimeout(fechar, aviso.classList.contains('aviso-error') ? 10000 : 5000);
  });
})();
