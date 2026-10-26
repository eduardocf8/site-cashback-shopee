/* Estúdio Instagram: "Publicar no Instagram" (agora ou agendado).
 * Salva o post, desenha cada slide em JPEG de 1080 px (o mesmo desenho do "Baixar") e manda para o
 * painel, que publica pela API do Instagram (instagram_painel/publicar.py). */
(function () {
  'use strict';
  // Espera o fim do login do Instagram, aberto numa janela à parte. A página do Instagram corta a ligação entre as
  // duas janelas, então a janela do login avisa por BroadcastChannel (e localStorage, nos navegadores antigos).
  // `voltou` roda quando a pessoa volta pra esta página sem ter terminado (fechou a janela do login, por exemplo):
  // como a ligação entre as janelas é cortada, não dá pra saber se ela fechou; o botão volta ao normal e o aviso
  // de "pronto" continua valendo se ela terminar depois.
  window.esperarInstagram = function (pronto, voltou) {
    let feito = false, saiu = false;
    const fim = () => { if (feito) return; feito = true; pronto(); };
    try { const canal = new BroadcastChannel('appfiliado-instagram'); canal.onmessage = (e) => { if (e.data === 'pronto') fim(); }; } catch (e) { /* sem canal */ }
    window.addEventListener('storage', (e) => { if (e.key === 'appfiliado-instagram') fim(); });
    if (!voltou) return;
    window.addEventListener('blur', () => { saiu = true; });
    window.addEventListener('focus', () => {
      if (!saiu || feito) return;
      saiu = false;
      setTimeout(() => { if (!feito) voltou(); }, 700);  // dá tempo do aviso de "pronto" chegar antes
    });
  };

  const $ = (id) => document.getElementById(id);
  const botao = $('es-publicar'), dialogo = $('es-dialogo-publicar');
  if (!botao || !dialogo || !window.Estudio) return;
  const E = window.Estudio, url = botao.dataset.url;
  const csrf = () => (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';
  let info = null;

  function el(tag, attrs, ...filhos) {
    const e = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => { if (k === 'class') e.className = v; else if (v !== undefined && v !== null) e.setAttribute(k, v); });
    filhos.flat().forEach((f) => { if (f !== null && f !== undefined && f !== false) e.append(f.nodeType ? f : document.createTextNode(String(f))); });
    return e;
  }
  const doisDigitos = (n) => String(n).padStart(2, '0');
  const local = (d) => `${d.getFullYear()}-${doisDigitos(d.getMonth() + 1)}-${doisDigitos(d.getDate())}T${doisDigitos(d.getHours())}:${doisDigitos(d.getMinutes())}`;

  function mostrarConta() {
    const caixa = $('pub-conta'); caixa.innerHTML = '';
    if (!info.ig) {
      caixa.append(el('p', {}, 'Conecte o seu Instagram profissional para publicar daqui.'));
      if (info.conectar) {
        const b = el('a', { class: 'es-bt es-salvar', href: info.conectar }, 'Conectar Instagram');
        b.addEventListener('click', (e) => {
          const l = 560, a = 760, x = window.screenX + Math.max(0, (window.outerWidth - l) / 2), y = window.screenY + Math.max(0, (window.outerHeight - a) / 2);
          const janela = window.open(b.href, 'conectar-instagram', `width=${l},height=${a},left=${x},top=${y}`);
          if (!janela) return; // bloqueou a janela: segue no link (o post já foi salvo ao abrir)
          e.preventDefault(); b.textContent = 'Conectando… (termine na janela do Instagram)';
          if (b.dataset.esperando) return;
          b.dataset.esperando = '1';
          esperarInstagram(carregar, () => { b.textContent = 'Conectar Instagram'; });
        });
        caixa.append(b);
      } else caixa.append(el('p', { class: 'es-quieto' }, 'A conexão com o Instagram ainda não está configurada.'));
      $('pub-corpo').hidden = true; $('pub-enviar').disabled = true;
      return;
    }
    caixa.append(el('div', { class: 'pub-perfil' },
      info.ig.foto ? el('img', { src: info.ig.foto, alt: '', referrerpolicy: 'no-referrer' }) : el('span', { class: 'ig-sem-foto' }, '@'),
      el('div', {}, el('strong', {}, `@${info.ig.username}`), el('small', {}, 'Vai para esta conta.'))));
    const n = E.est.slides.length, story = info.tipo === 'story';
    $('pub-como').textContent = story ? (n > 1 ? `Vai como ${n} stories, um depois do outro.` : 'Vai como 1 story.')
      : (n > 1 ? `Vai como carrossel de ${n} imagens no feed, com a legenda do editor.` : 'Vai como post de 1 imagem no feed, com a legenda do editor.');
    $('pub-aviso-story').hidden = !story;
    $('pub-aviso-legenda').hidden = story || !!E.est.legenda.trim();
    $('pub-corpo').hidden = false; $('pub-enviar').disabled = false;
  }

  function mostrarLista() {
    const caixa = $('pub-lista'); caixa.innerHTML = '';
    if (!info.publicacoes.length) return;
    caixa.append(el('h3', {}, 'Publicações deste post'));
    const ul = el('ul', {});
    info.publicacoes.forEach((p) => {
      const li = el('li', { class: `pub-${p.estado}` }, el('span', { class: 'pub-selo' }, p.estado_nome), ` ${p.tipo}${p.conta ? ' · ' + p.conta : ''} · ${p.quando}`);
      if (p.link) li.append(' · ', el('a', { href: p.link, target: '_blank', rel: 'noopener' }, 'Ver no Instagram'));
      if (p.erro) li.append(el('small', { class: 'es-erro' }, p.erro));
      [['cancelar', 'Cancelar'], ['tentar', 'Tentar de novo']].forEach(([k, nome]) => {
        if (!p[k]) return;
        const b = el('button', { type: 'button', class: 'es-bt pub-acao' }, nome);
        b.addEventListener('click', async () => {
          if (k === 'cancelar' && !confirm('Cancelar esta publicação?')) return;
          b.disabled = true;
          const r = await fetch(p[k], { method: 'POST', headers: { 'X-CSRFToken': csrf(), Accept: 'application/json' }, credentials: 'same-origin' });
          const j = await r.json().catch(() => ({}));
          $('pub-ok').textContent = j.mensagem || ''; carregar();
        });
        li.append(' ', b);
      });
      ul.append(li);
    });
    caixa.append(ul);
  }

  async function carregar() {
    const r = await fetch(url, { credentials: 'same-origin' });
    if (!r.ok) { $('pub-conta').textContent = 'Não consegui conferir o seu Instagram agora.'; return; }
    info = await r.json();
    mostrarConta(); mostrarLista();
    // Enquanto um post "agora" não sai, confere de novo a cada 5 segundos.
    const andando = info.publicacoes.some((p) => p.estado === 'publicando' || (p.estado === 'pendente' && p.agora));
    clearTimeout(carregar.t);
    if (dialogo.open && andando) carregar.t = setTimeout(carregar, 5000);
  }

  botao.addEventListener('click', () => {
    $('pub-erro').textContent = ''; $('pub-ok').textContent = '';
    const agora = new Date(Date.now() + 10 * 60000), max = new Date(Date.now() + 59 * 86400000);
    $('pub-data').min = local(agora); $('pub-data').max = local(max);
    if (!$('pub-data').value) { const d = new Date(Date.now() + 60 * 60000); d.setMinutes(0); $('pub-data').value = local(d); }
    dialogo.showModal(); carregar();
  });
  dialogo.addEventListener('close', () => clearTimeout(carregar.t));
  dialogo.querySelectorAll('[name=pub-quando]').forEach((r) => r.addEventListener('change', () => {
    const agendar = dialogo.querySelector('[name=pub-quando]:checked').value === 'agendar';
    $('pub-data').hidden = !agendar; $('pub-enviar').textContent = agendar ? 'Agendar' : 'Publicar';
  }));

  $('pub-enviar').addEventListener('click', async () => {
    const b = $('pub-enviar'), texto = b.textContent;
    const quando = dialogo.querySelector('[name=pub-quando]:checked').value;
    $('pub-erro').textContent = ''; $('pub-ok').textContent = '';
    if (quando === 'agendar' && !$('pub-data').value) { $('pub-erro').textContent = 'Escolha o dia e a hora.'; return; }
    b.disabled = true;
    try {
      b.textContent = 'Salvando…';
      await E.salvar();
      const form = new FormData();
      form.append('quando', quando);
      // Vai com o fuso de quem agendou (o campo do navegador não tem fuso).
      if (quando === 'agendar') form.append('data', new Date($('pub-data').value).toISOString());
      for (let i = 0; i < E.est.slides.length; i++) {
        b.textContent = `Preparando imagem ${i + 1} de ${E.est.slides.length}…`;
        const dados = await E.imagem(i, 'jpg', 1080, 0.92);
        form.append(`imagem_${i}`, await (await fetch(dados)).blob(), `${doisDigitos(i + 1)}.jpg`);
      }
      b.textContent = 'Enviando…';
      const r = await fetch(url, { method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: form, credentials: 'same-origin' });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.erro || 'Não deu certo agora. Tente de novo.');
      $('pub-ok').textContent = j.mensagem;
      await carregar();
    } catch (erro) {
      $('pub-erro').textContent = erro.message || 'Não deu certo agora. Tente de novo.';
    } finally { b.disabled = !info || !info.ig; b.textContent = texto; }
  });
})();
