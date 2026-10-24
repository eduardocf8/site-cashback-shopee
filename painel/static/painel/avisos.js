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

  function cuidar(aviso) {
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
  }
  document.querySelectorAll('.avisos-flutuantes .aviso').forEach(cuidar);

  // Aviso criado pela própria tela (ex: "Dados atualizados"). Mesmo visual e mesmo tempo dos outros.
  function avisoFlutuante(texto, tipo) {
    var lista = document.querySelector('.avisos-flutuantes');
    if (!lista) {
      lista = document.createElement('ul');
      lista.className = 'avisos avisos-flutuantes';
      lista.setAttribute('role', 'status');
      lista.setAttribute('aria-live', 'polite');
      document.querySelector('main') ? document.querySelector('main').prepend(lista) : document.body.prepend(lista);
    }
    var item = document.createElement('li');
    item.className = 'aviso aviso-' + (tipo || 'success');
    var span = document.createElement('span');
    span.textContent = texto;
    var fechar = document.createElement('button');
    fechar.type = 'button';
    fechar.className = 'aviso-fechar';
    fechar.setAttribute('aria-label', 'Fechar aviso');
    fechar.textContent = '×';
    item.appendChild(span);
    item.appendChild(fechar);
    lista.appendChild(item);
    cuidar(item);
  }
  window.avisoFlutuante = avisoFlutuante;

  // A tela recarregou porque a Shopee terminou de mandar os números (painel/sincronizacao.js).
  try {
    if (sessionStorage.getItem('appfiliado:atualizado')) {
      sessionStorage.removeItem('appfiliado:atualizado');
      avisoFlutuante('Dados atualizados com a Shopee.', 'success');
    }
  } catch (e) { /* sem sessionStorage: segue sem o aviso */ }
})();
