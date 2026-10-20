/* Notas fiscais: acompanha a emissão sem recarregar a página.
 * Um bloco com data-acompanhar="<url>" (e, no lote, data-lote="<id>") pergunta ao servidor a
 * cada poucos segundos a situação das notas da lista e o resumo do lote: a barra enche, os
 * números sobem e o selo de cada nota muda na hora. Quando o lote termina (ou uma nota avulsa
 * sai da fila), a página recarrega uma vez para mostrar PDF, XML e mensagens. */
(function () {
  const bloco = document.querySelector('[data-acompanhar]');
  if (!bloco) return;
  const url = bloco.dataset.acompanhar;
  const lote = bloco.dataset.lote || '';
  const linhas = () => [...document.querySelectorAll('tr[data-nota]')];
  const iniciais = Object.fromEntries(linhas().map((tr) => [tr.dataset.nota, tr.dataset.situacao]));
  const intervalo = lote ? 3000 : 5000;
  let parado = false;

  function campo(nome, valor) {
    document.querySelectorAll(`[data-campo="${nome}"]`).forEach((el) => {
      if (nome === 'barra') {
        el.style.width = valor + '%';
        el.parentElement.setAttribute('aria-valuenow', valor);
      } else if (el.textContent !== String(valor)) {
        el.textContent = valor;
      }
    });
  }

  async function perguntar() {
    if (parado || document.visibilityState === 'hidden') return;
    const ids = linhas().map((tr) => tr.dataset.nota).join(',');
    let dados;
    try {
      const r = await fetch(`${url}?ids=${ids}&lote=${lote}`, { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
      if (!r.ok) return;
      dados = await r.json();
    } catch (e) { return; } // sem internet por um instante: tenta na próxima
    let mudouAvulsa = false;
    for (const tr of linhas()) {
      const n = dados.notas[tr.dataset.nota];
      if (!n) continue;
      const selo = tr.querySelector('.notas-situacao');
      if (selo && selo.textContent !== n.rotulo) {
        selo.textContent = n.rotulo;
        selo.className = 'notas-situacao selo-venda ' + n.classe;
      }
      tr.dataset.situacao = n.situacao;
      if (!lote && n.situacao !== iniciais[tr.dataset.nota] && !['fila', 'enviando'].includes(n.situacao)) mudouAvulsa = true;
    }
    if (dados.lote) {
      const l = dados.lote;
      campo('barra', l.progresso); campo('progresso', l.progresso); campo('feitas', l.feitas);
      campo('autorizadas', l.autorizadas); campo('problemas', l.problemas); campo('fila', l.fila); campo('emails', l.emails);
      if (l.estado !== 'emitindo') { parado = true; window.location.reload(); }
    }
    if (mudouAvulsa) { parado = true; window.location.reload(); }
  }

  setInterval(perguntar, intervalo);
  document.addEventListener('visibilitychange', perguntar);
})();
