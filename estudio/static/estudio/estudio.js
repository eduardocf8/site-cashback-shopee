/* Estúdio de posts: o editor.
 * O desenho de cada slide vem de marca-appfiliado.js ou marca-cashb.js (window.EstudioMarcas).
 * A prévia é o próprio slide em HTML, reduzido na tela; o PNG sai do mesmo HTML no tamanho real
 * (html-to-image), então o que aparece é exatamente o que baixa. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const cfg = JSON.parse($('es-config').textContent);
  const inicial = JSON.parse($('es-projeto').textContent);
  const MODELOS = JSON.parse($('es-modelos-dados').textContent);
  const M = window.EstudioMarcas[cfg.marca];
  const AMOSTRAS = {
    appfiliado: { verde: '#1F3A2E', creme: '#F6F3EA', amarelo: '#F2C230', branco: '#FFFFFF', areia: '#E9E2D3' },
    cashb: { roxo: 'linear-gradient(165deg,#4c1d95,#6d28d9 55%,#a78bfa)', claro: '#f8fafc', lilas: '#f1eefb', escuro: '#111827', branco: '#FFFFFF' },
  }[cfg.marca];
  const MIN_FONTE = 26; // px na imagem final

  const copia = (x) => JSON.parse(JSON.stringify(x));
  const est = { id: inicial.id, nome: inicial.nome, formato: inicial.formato, slides: copia(inicial.slides || []), legenda: inicial.legenda || '', atual: 0, sujo: false };
  if (!est.slides.length) est.slides.push(M.novo('capa'));

  // ---- utilidades de DOM ---------------------------------------------------------------------
  function el(tag, attrs, ...filhos) {
    const e = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (v === undefined || v === null || v === false) return;
      if (k === 'on') Object.entries(v).forEach(([ev, fn]) => e.addEventListener(ev, fn));
      else if (k === 'class') e.className = v;
      else if (k === 'style') e.style.cssText = v;
      else if (k in e && typeof e[k] !== 'function' && k !== 'list') e[k] = v;
      else e.setAttribute(k, v === true ? '' : v);
    });
    filhos.flat().forEach((f) => { if (f !== null && f !== undefined && f !== false) e.append(f.nodeType ? f : document.createTextNode(String(f))); });
    return e;
  }
  const csrf = () => (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';
  async function post(url, dados, form) {
    const r = await fetch(url, { method: 'POST', headers: form ? { 'X-CSRFToken': csrf() } : { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: form || JSON.stringify(dados), credentials: 'same-origin' });
    let j = {}; try { j = await r.json(); } catch (e) { /* resposta sem JSON */ }
    if (!r.ok) throw new Error(j.erro || 'Não deu certo agora. Tente de novo.');
    return j;
  }
  const slug = (s) => (s || 'post').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50) || 'post';
  function marcarSujo() { est.sujo = true; $('es-salvar').textContent = 'Salvar *'; }

  // ---- montar um slide ------------------------------------------------------------------------
  document.head.append(el('style', {}, M.css(cfg)));
  const ctxDe = (i) => ({ i, total: est.slides.length, formato: est.formato });

  // Ajustes manuais: tamanho do título e do texto, margens extras, alinhamento e posição.
  // Os dois últimos já vêm como classes do desenho da marca; aqui entram os que mexem em medidas.
  function aplicarAjustes(no, s) {
    const a = s.ajustes || {}, b = M.base(est.formato);
    const alvo = M.margem ? no.querySelector(M.margem) : no;
    if (alvo && (a.lateral || a.vertical)) {
      const cs = getComputedStyle(alvo), dl = (a.lateral || 0) / b.escala, dv = (a.vertical || 0) / b.escala;
      alvo.style.paddingLeft = Math.max(0, parseFloat(cs.paddingLeft) + dl) + 'px';
      alvo.style.paddingRight = Math.max(0, parseFloat(cs.paddingRight) + dl) + 'px';
      alvo.style.paddingTop = Math.max(0, parseFloat(cs.paddingTop) + dv) + 'px';
      alvo.style.paddingBottom = Math.max(0, parseFloat(cs.paddingBottom) + dv) + 'px';
    }
    const ft = a.titulo || 1, fx = a.texto || 1;
    if (ft !== 1 || fx !== 1) {
      const mudar = [];
      textos(no, true).forEach((e) => {
        const f = e.closest('h1, h2') ? ft : fx;
        if (f !== 1) mudar.push([e, parseFloat(getComputedStyle(e).fontSize) * f]);
      });
      mudar.forEach(([e, px]) => { e.style.fontSize = px + 'px'; });
    }
  }
  // Elementos com texto próprio (fora do celular). comDecor inclui contador e rodapé.
  function textos(no, comDecor) {
    return [...no.querySelectorAll('*')].filter((e) => !e.closest('.celular') && (comDecor || !e.closest('[data-decor]'))
      && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()));
  }
  function montar(i, alvo) {
    alvo.innerHTML = M.render(est.slides[i], ctxDe(i), cfg);
    const no = alvo.firstElementChild;
    aplicarAjustes(no, est.slides[i]);
    return no;
  }

  // ---- margens de segurança e avisos ----------------------------------------------------------
  function zonas(s, i) {
    const capa = M.ehCapa(s, ctxDe(i));
    if (est.formato === 'story') return { seguro: { t: 250, b: 300, l: 60, r: 60 }, grade: null };
    if (est.formato === 'retrato') return capa ? { seguro: { t: 160, b: 160, l: 170, r: 170 }, grade: { t: 135, b: 135, l: 138, r: 138 } } : { seguro: { t: 40, b: 40, l: 40, r: 40 }, grade: null };
    return capa ? { seguro: { t: 40, b: 40, l: 175, r: 175 }, grade: { t: 0, b: 0, l: 135, r: 135 } } : { seguro: { t: 40, b: 40, l: 40, r: 40 }, grade: null };
  }
  function checar(no, s, i, k) {
    const b = M.base(est.formato), z = zonas(s, i).seguro, W = b.w * b.escala, H = b.h * b.escala;
    const q = no.getBoundingClientRect(), avisos = new Set(), fator = b.escala / k;
    textos(no, false).forEach((e) => {
      const r = e.getBoundingClientRect(); if (!r.width || !r.height) return;
      const x1 = (r.left - q.left) * fator, x2 = (r.right - q.left) * fator, y1 = (r.top - q.top) * fator, y2 = (r.bottom - q.top) * fator;
      const t = e.textContent.trim().slice(0, 40);
      if (x1 < z.l - 1 || x2 > W - z.r + 1 || y1 < z.t - 1 || y2 > H - z.b + 1) {
        avisos.add(est.formato === 'story' && (y1 < z.t || y2 > H - z.b) ? `"${t}" está numa faixa que o Instagram cobre (topo ou rodapé do story).`
          : z.l > 100 && (x1 < z.l || x2 > W - z.r) ? `"${t}" está perto demais da borda da grade do perfil.` : `"${t}" está fora da área segura.`);
      }
      const px = parseFloat(getComputedStyle(e).fontSize) * b.escala;
      if (px < MIN_FONTE - 0.5) avisos.add(`"${t}" está com a letra pequena (${Math.round(px)} px). O mínimo é ${MIN_FONTE} px.`);
    });
    const pe = no.querySelector('.rodape, .progresso'), bloco = no.querySelector('.bloco');
    if (pe && bloco && bloco.getBoundingClientRect().bottom > pe.getBoundingClientRect().top + 2) avisos.add('O texto está encostando no rodapé. Diminua o texto ou as margens.');
    if (bloco && bloco.scrollHeight > bloco.clientHeight + 4 && getComputedStyle(bloco).overflow !== 'visible') avisos.add('O conteúdo não coube no slide.');
    (M.avisos ? M.avisos(s) : []).forEach((a) => avisos.add(a));
    return [...avisos];
  }

  // ---- prévia ---------------------------------------------------------------------------------
  let escalaPalco = 1;
  function desenharPalco() {
    const i = est.atual, s = est.slides[i], b = M.base(est.formato);
    const area = $('es-palco-area'), largura = Math.max(260, area.clientWidth), altura = Math.max(320, window.innerHeight - 270);
    const k = Math.min(largura / b.w, altura / b.h); escalaPalco = k;
    const esc = $('es-escala'); esc.style.width = b.w * k + 'px'; esc.style.height = b.h * k + 'px';
    const quadro = $('es-quadro'); quadro.style.transform = `scale(${k})`;
    const no = montar(i, quadro);
    const guias = $('es-guias-camada'); guias.innerHTML = ''; guias.style.width = b.w + 'px'; guias.style.height = b.h + 'px'; guias.style.transform = `scale(${k})`;
    if ($('es-guias').checked) {
      const z = zonas(s, i), e = b.escala, caixa = (m, cls, rotulo) => {
        const d = el('div', { class: cls, style: `left:${m.l / e}px;top:${m.t / e}px;right:${m.r / e}px;bottom:${m.b / e}px` });
        d.append(el('span', { style: `left:6px;top:6px;transform:scale(${1 / k});transform-origin:0 0` }, rotulo)); guias.append(d);
      };
      if (z.grade) caixa(z.grade, 'grade', 'O que aparece na grade do perfil');
      caixa(z.seguro, '', est.formato === 'story' ? 'Área segura do story' : 'Área segura');
    }
    const avisos = checar(no, s, i, k), ul = $('es-avisos'); ul.innerHTML = '';
    if (avisos.length) avisos.forEach((a) => ul.append(el('li', {}, a)));
    else ul.append(el('li', { class: 'ok' }, 'Tudo dentro das margens e legível.'));
  }
  function miniatura(i, caixa, largura) {
    const b = M.base(est.formato), k = largura / b.w;
    caixa.style.height = b.h * k + 'px';
    const dentro = caixa.firstElementChild || caixa.appendChild(el('div'));
    dentro.style.transform = `scale(${k})`;
    montar(i, dentro);
  }
  function desenharLista() {
    const rolagem = document.querySelector('.es-lista'), y = rolagem.scrollTop;
    const lista = $('es-slides'); lista.innerHTML = '';
    est.slides.forEach((s, i) => {
      const img = el('div', { class: 'es-mini-img' });
      const mover = (d) => (ev) => { ev.stopPropagation(); const j = i + d; [est.slides[i], est.slides[j]] = [est.slides[j], est.slides[i]]; est.atual = j; tudo(); marcarSujo(); };
      const barra = el('div', { class: 'es-mini-barra' }, el('span', {}, `${i + 1}. ${(cfg.tipos[s.tipo] || {}).nome || s.tipo}`),
        el('span', {},
          el('button', { type: 'button', title: 'Subir', disabled: i === 0, on: { click: mover(-1) } }, '↑'),
          el('button', { type: 'button', title: 'Descer', disabled: i === est.slides.length - 1, on: { click: mover(1) } }, '↓'),
          el('button', { type: 'button', title: 'Duplicar', disabled: est.slides.length >= cfg.max_slides, on: { click: (ev) => { ev.stopPropagation(); est.slides.splice(i + 1, 0, copia(s)); est.atual = i + 1; tudo(); marcarSujo(); } } }, '⧉'),
          el('button', { type: 'button', title: 'Apagar', disabled: est.slides.length === 1, on: { click: (ev) => { ev.stopPropagation(); if (!confirm('Apagar este slide?')) return; est.slides.splice(i, 1); est.atual = Math.min(est.atual, est.slides.length - 1); tudo(); marcarSujo(); } } }, '🗑')));
      const item = el('div', { class: 'es-mini' + (i === est.atual ? ' ativo' : ''), on: { click: () => selecionar(i) } }, img, barra);
      lista.append(item);
      miniatura(i, img, lista.clientWidth - 16 || 180);
    });
    $('es-adicionar').disabled = est.slides.length >= cfg.max_slides;
    rolagem.scrollTop = y;
    mostrarAtual();
  }
  let pendente = null;
  function atualizar() {
    marcarSujo();
    clearTimeout(pendente);
    pendente = setTimeout(() => {
      desenharPalco();
      const caixa = document.querySelectorAll('#es-slides .es-mini-img')[est.atual];
      if (caixa) miniatura(est.atual, caixa, $('es-slides').clientWidth - 16 || 180);
    }, 70);
  }
  function tudo() { desenharLista(); desenharPalco(); desenharCampos(); }

  // Troca o slide aberto sem redesenhar a lista, para a rolagem do painel ficar onde está.
  function selecionar(i) {
    if (i < 0 || i >= est.slides.length) return;
    est.atual = i;
    document.querySelectorAll('#es-slides .es-mini').forEach((m, k) => m.classList.toggle('ativo', k === i));
    desenharPalco(); desenharCampos(); mostrarAtual();
  }
  // Deixa o slide aberto visível na lista (só rola se ele estiver fora da área visível).
  function mostrarAtual() {
    const m = document.querySelectorAll('#es-slides .es-mini')[est.atual];
    const caixa = document.querySelector('.es-lista');
    if (m && caixa) { // rola só a lista, nunca a página
      const r = m.getBoundingClientRect(), c = caixa.getBoundingClientRect();
      if (r.top < c.top) caixa.scrollTop -= c.top - r.top + 8;
      else if (r.bottom > c.bottom) caixa.scrollTop += r.bottom - c.bottom + 8;
    }
    $('es-anterior').disabled = est.atual === 0;
    $('es-proximo').disabled = est.atual === est.slides.length - 1;
    $('es-posicao').textContent = `Slide ${est.atual + 1} de ${est.slides.length}`;
  }
  $('es-anterior').addEventListener('click', () => selecionar(est.atual - 1));
  $('es-proximo').addEventListener('click', () => selecionar(est.atual + 1));

  // ---- campos do slide ------------------------------------------------------------------------
  const ROTULOS_LISTA = {
    itens: { nome: 'Itens', novo: () => ({ titulo: '', texto: '' }), campos: [['titulo', 'Título do item', 60], ['texto', 'Texto do item', 110]] },
    pares: { nome: 'Números', novo: () => ({ valor: '', legenda: '' }), campos: [['valor', 'Número', 14], ['legenda', 'Legenda', 50]] },
    linhas: { nome: 'Linhas', novo: () => ({ rotulo: '', valor: '', detalhe: '' }), campos: [['rotulo', 'Rótulo', 40], ['valor', 'Valor', 20], ['detalhe', 'Detalhe (opcional)', 40]] },
    baloes: { nome: 'Mensagens', novo: () => ({ texto: '', meu: false }), campos: [['texto', 'Mensagem', 160]] },
  };
  const LONGOS = new Set(['titulo', 'texto', 'destaque', 'nota']);

  function campoTexto(s, campo) {
    const [rotulo, limite] = cfg.campos_texto[campo];
    const props = { value: s[campo] || '', maxLength: limite, on: { input: (e) => { s[campo] = e.target.value; atualizar(); } } };
    const entrada = LONGOS.has(campo) ? el('textarea', Object.assign({ rows: campo === 'titulo' ? 2 : 3 }, props)) : el('input', Object.assign({ type: 'text' }, props));
    if (LONGOS.has(campo)) entrada.value = s[campo] || '';
    return el('label', { class: 'es-campo' }, el('span', {}, rotulo), entrada);
  }
  function campoLista(s, campo) {
    const def = ROTULOS_LISTA[campo], grupo = el('div', { class: 'es-campo' }, el('span', {}, def.nome));
    const itens = s[campo] = s[campo] || [];
    itens.forEach((it, k) => {
      const caixa = el('div', { class: 'es-item' });
      caixa.append(el('div', { class: 'es-item-barra' }, el('span', {}, `${k + 1}`), el('span', {},
        el('button', { type: 'button', disabled: k === 0, on: { click: () => { [itens[k - 1], itens[k]] = [itens[k], itens[k - 1]]; atualizar(); desenharCampos(); } } }, '↑'),
        el('button', { type: 'button', on: { click: () => { itens.splice(k, 1); atualizar(); desenharCampos(); } } }, 'Remover'))));
      def.campos.forEach(([c, r, lim]) => {
        const props = { value: it[c] || '', maxLength: lim, placeholder: r, on: { input: (e) => { it[c] = e.target.value; atualizar(); } } };
        caixa.append(c === 'texto' && campo === 'baloes' ? Object.assign(el('textarea', Object.assign({ rows: 2 }, props)), { value: it[c] || '' }) : el('input', Object.assign({ type: 'text' }, props)));
      });
      if (campo === 'itens' && cfg.marca === 'appfiliado') caixa.append(el('label', { class: 'es-pequeno' }, el('input', { type: 'checkbox', checked: !!it.premium, on: { change: (e) => { it.premium = e.target.checked; atualizar(); } } }), 'Selo Premium'));
      if (campo === 'baloes') caixa.append(el('label', { class: 'es-pequeno' }, el('input', { type: 'checkbox', checked: !!it.meu, on: { change: (e) => { it.meu = e.target.checked; atualizar(); } } }), 'Mensagem da pessoa (balão verde)'));
      grupo.append(caixa);
    });
    if (itens.length < cfg.limites[campo]) grupo.append(el('button', { type: 'button', class: 'es-bt', on: { click: () => { itens.push(def.novo()); atualizar(); desenharCampos(); } } }, '+ Adicionar'));
    return grupo;
  }
  function faixa(rotulo, valor, min, max, passo, fmt, aoMudar) {
    const mostra = el('span', { class: 'es-valor' }, fmt(valor));
    return el('label', { class: 'es-campo' }, el('span', {}, rotulo), el('div', { class: 'es-linha' },
      el('input', { type: 'range', min, max, step: passo, value: valor, on: { input: (e) => { const v = +e.target.value; mostra.textContent = fmt(v); aoMudar(v); } } }), mostra));
  }
  function selecao(rotulo, opcoes, valor, aoMudar) {
    const sel = el('select', { on: { change: (e) => aoMudar(e.target.value) } }, opcoes.map(([v, t]) => el('option', { value: v, selected: v === valor }, t)));
    return el('label', { class: 'es-campo' }, el('span', {}, rotulo), sel);
  }

  function grupoFundo(s) {
    const f = s.fundo = s.fundo || { modo: 'cor', cor: Object.keys(cfg.cores)[0] };
    const g = el('div', { class: 'es-grupo' }, el('b', {}, 'Fundo'));
    const aba = (modo, nome) => el('button', { type: 'button', class: 'es-bt' + (f.modo === modo ? ' ativo' : ''), on: { click: () => {
      if (modo === 'cor') s.fundo = { modo: 'cor', cor: f.cor || Object.keys(cfg.cores)[0] };
      if (modo === 'arte') s.fundo = { modo: 'arte', arte: f.arte || M.artes[0], tom: f.tom || 'escuro' };
      if (modo === 'imagem') s.fundo = { modo: 'imagem', imagem: f.imagem || '', veu: f.veu === undefined ? 0.45 : f.veu };
      atualizar(); desenharCampos();
    } } }, nome);
    g.append(el('div', { class: 'es-abas' }, aba('cor', 'Cor'), aba('arte', 'Arte'), aba('imagem', 'Imagem')));
    if (f.modo === 'cor') {
      g.append(el('div', { class: 'es-cores' }, Object.entries(cfg.cores).map(([k, nome]) => el('button', { type: 'button', title: nome, class: 'es-cor' + (f.cor === k ? ' ativo' : ''), style: `background:${AMOSTRAS[k]}`,
        on: { click: () => { f.cor = k; atualizar(); desenharCampos(); } } }))));
    } else if (f.modo === 'arte') {
      g.append(selecao('Tom', Object.entries(cfg.tons), f.tom || 'escuro', (v) => { f.tom = v; atualizar(); desenharCampos(); }));
      const grade = el('div', { class: 'es-artes' });
      Object.entries(cfg.artes).forEach(([k, nome]) => {
        const amostra = M.fundo({ modo: 'arte', arte: k, tom: f.tom }, 300, 300).html;
        const bt = el('button', { type: 'button', class: 'es-arte' + (f.arte === k ? ' ativo' : ''), title: nome, on: { click: () => { f.arte = k; atualizar(); desenharCampos(); } } });
        bt.innerHTML = `<div style="position:absolute;inset:0;transform:scale(1);">${amostra}</div>`;
        bt.firstChild.querySelectorAll('.fundo').forEach((d) => { d.style.position = 'absolute'; d.style.inset = '0'; });
        const svg = bt.querySelector('svg'); if (svg) { svg.setAttribute('width', '100%'); svg.setAttribute('height', '100%'); svg.setAttribute('preserveAspectRatio', 'xMidYMid slice'); }
        bt.append(el('span', {}, nome)); grade.append(bt);
      });
      g.append(grade);
    } else {
      const galeria = el('div', { class: 'es-imagens' }, el('p', { class: 'es-dica' }, 'Carregando imagens…'));
      const enviar = el('input', { type: 'file', accept: 'image/jpeg,image/png,image/webp', on: { change: async (e) => {
        const arq = e.target.files[0]; if (!arq) return;
        const fd = new FormData(); fd.append('arquivo', arq);
        try { const j = await post(cfg.urls.imagens, null, fd); f.imagem = j.imagens[0].url; atualizar(); desenharCampos(); }
        catch (erro) { alert(erro.message); }
      } } });
      g.append(el('label', { class: 'es-campo' }, el('span', {}, 'Enviar imagem (JPG, PNG ou WebP, até 12 MB)'), enviar), galeria,
        faixa('Escurecer a imagem (véu)', f.veu || 0, 0, 0.85, 0.05, (v) => `${Math.round(v * 100)}%`, (v) => { f.veu = v; atualizar(); }),
        el('p', { class: 'es-dica' }, 'Com véu de 30% ou mais, o texto fica claro. Sem véu, o texto fica escuro.'));
      fetch(cfg.urls.imagens, { credentials: 'same-origin' }).then((r) => r.json()).then((j) => {
        galeria.innerHTML = '';
        if (!j.imagens.length) galeria.append(el('p', { class: 'es-dica' }, 'Nenhuma imagem enviada ainda.'));
        j.imagens.forEach((im) => galeria.append(el('button', { type: 'button', title: im.nome, class: 'es-imagem' + (f.imagem === im.url ? ' ativo' : ''),
          on: { click: () => { f.imagem = im.url; atualizar(); desenharCampos(); } } }, el('img', { src: im.url, alt: im.nome, loading: 'lazy' }))));
      }).catch(() => { galeria.innerHTML = ''; });
    }
    return g;
  }

  function grupoAjustes(s, i) {
    const a = s.ajustes = s.ajustes || {};
    const g = el('div', { class: 'es-grupo' }, el('b', {}, 'Ajustes'));
    const pct = (v) => `${Math.round(v * 100)}%`, px = (v) => `${v > 0 ? '+' : ''}${v} px`;
    g.append(
      faixa('Tamanho do título', a.titulo || 1, 0.6, 1.6, 0.05, pct, (v) => { a.titulo = v; atualizar(); }),
      faixa('Tamanho do texto', a.texto || 1, 0.6, 1.6, 0.05, pct, (v) => { a.texto = v; atualizar(); }),
      faixa('Margem lateral', a.lateral || 0, -60, 200, 5, px, (v) => { a.lateral = v; atualizar(); }),
      faixa('Margem de cima e de baixo', a.vertical || 0, -60, 200, 5, px, (v) => { a.vertical = v; atualizar(); }),
      selecao('Alinhamento', [['', 'Padrão do tipo de slide'], ['esquerda', 'À esquerda'], ['centro', 'Centralizado']], a.alinhar || '', (v) => { a.alinhar = v; atualizar(); }),
      selecao('Posição do texto', [['', 'Padrão do tipo de slide'], ['topo', 'Em cima'], ['meio', 'No meio'], ['base', 'Embaixo']], a.posicao || '', (v) => { a.posicao = v; atualizar(); }),
      el('div', { class: 'es-linha' },
        el('button', { type: 'button', class: 'es-bt', on: { click: () => { s.ajustes = {}; atualizar(); desenharCampos(); } } }, 'Voltar ao padrão'),
        el('button', { type: 'button', class: 'es-bt', on: { click: () => { if (!confirm('Aplicar estes ajustes em todos os slides?')) return; est.slides.forEach((x, j) => { if (j !== i) x.ajustes = copia(a); }); marcarSujo(); desenharLista(); } } }, 'Aplicar em todos os slides')));
    return g;
  }

  function desenharCampos() {
    const i = est.atual, s = est.slides[i], tipo = cfg.tipos[s.tipo] || { campos: [] };
    const c = $('es-campos'), yCampos = c.scrollTop, mesmoSlide = desenharCampos.ultimo === i; c.innerHTML = '';
    desenharCampos.ultimo = i;
    const topo = el('div', { class: 'es-grupo' }, el('b', {}, `Slide ${i + 1}`),
      selecao('Tipo do slide', Object.entries(cfg.tipos).map(([k, t]) => [k, t.nome]), s.tipo, (v) => {
        const novo = M.novo(v); Object.keys(novo).forEach((k) => { if (k === 'tipo' || s[k] === undefined || s[k] === '') s[k] = novo[k]; }); s.tipo = v;
        atualizar(); desenharCampos(); desenharLista();
      }));
    if (est.formato !== 'story') {
      const marcado = M.ehCapa(s, ctxDe(i));
      topo.append(el('label', { class: 'es-pequeno' }, el('input', { type: 'checkbox', checked: marcado, on: { change: (e) => { s.capa = e.target.checked; atualizar(); desenharCampos(); } } }),
        'Usar como capa (margens maiores, que cabem na grade do perfil)'));
    }
    c.append(topo);
    const textos_ = el('div', { class: 'es-grupo' }, el('b', {}, 'Conteúdo'));
    tipo.campos.forEach((campo) => {
      if (cfg.campos_texto[campo]) textos_.append(campoTexto(s, campo));
      else if (ROTULOS_LISTA[campo]) textos_.append(campoLista(s, campo));
      else if (campo === 'numerada') textos_.append(el('label', { class: 'es-pequeno' }, el('input', { type: 'checkbox', checked: !!s.numerada, on: { change: (e) => { s.numerada = e.target.checked; atualizar(); } } }), 'Lista numerada'));
      else if (campo === 'logo') textos_.append(el('label', { class: 'es-pequeno' }, el('input', { type: 'checkbox', checked: s.logo !== false, on: { change: (e) => { s.logo = e.target.checked; atualizar(); } } }), 'Mostrar o logo'));
      else if (campo === 'icone') textos_.append(selecao('Ícone', [['', 'Sem ícone']].concat(cfg.icones.map((k) => [k, M.nomesIcones[k] || k])), s.icone || '', (v) => { s.icone = v; atualizar(); }));
      else if (campo === 'print') textos_.append(selecao('Tela do painel', Object.keys(cfg.prints).map((k) => [k, k]), s.print || '', (v) => { s.print = v; atualizar(); }));
      else if (campo === 'recorte') textos_.append(faixa('Descer a tela', s.recorte || 0, 0, 3000, 10, (v) => `${v}`, (v) => { s.recorte = v; atualizar(); }));
    });
    textos_.append(el('p', { class: 'es-dica' }, 'Para destacar uma palavra, coloque entre asteriscos: *destaque*.'));
    c.append(textos_, grupoFundo(s), grupoAjustes(s, i));
    c.scrollTop = mesmoSlide ? yCampos : 0;
  }

  // ---- exportar -------------------------------------------------------------------------------
  async function carregarImagens(no) {
    const urls = new Set();
    no.querySelectorAll('[style*="url("]').forEach((e) => { const m = e.getAttribute('style').match(/url\(['"]?([^'")]+)['"]?\)/); if (m) urls.add(m[1]); });
    await Promise.all([...urls].map((u) => new Promise((ok) => { const im = new Image(); im.onload = im.onerror = ok; im.src = u; })));
    await document.fonts.ready;
  }
  async function imagem(i, tipo, largura) {
    const b = M.base(est.formato), caixa = $('es-exportar');
    const no = montar(i, caixa); await carregarImagens(no);
    const fontEmbedCSS = imagem.fontes || (imagem.fontes = await htmlToImage.getFontEmbedCSS(no));
    const op = { width: b.w, height: b.h, pixelRatio: largura ? largura / b.w : b.escala, fontEmbedCSS, cacheBust: false };
    const url = tipo === 'jpg' ? await htmlToImage.toJpeg(no, Object.assign({ quality: 0.82, backgroundColor: '#ffffff' }, op)) : await htmlToImage.toPng(no, op);
    caixa.innerHTML = '';
    return url;
  }
  function baixar(url, nome) { const a = el('a', { href: url, download: nome }); document.body.append(a); a.click(); a.remove(); }
  async function ocupado(bt, fn) { bt.disabled = true; const t = bt.textContent; bt.textContent = 'Aguarde…'; try { await fn(); } catch (e) { alert(e.message || 'Não deu certo.'); } finally { bt.disabled = false; bt.textContent = t; } }

  $('es-baixar').addEventListener('click', (e) => ocupado(e.target, async () => {
    baixar(await imagem(est.atual, 'png'), `${slug(est.nome)}-${String(est.atual + 1).padStart(2, '0')}.png`);
  }));
  $('es-zip').addEventListener('click', (e) => ocupado(e.target, async () => {
    const zip = new JSZip();
    for (let i = 0; i < est.slides.length; i++) zip.file(`${String(i + 1).padStart(2, '0')}.png`, (await imagem(i, 'png')).split(',')[1], { base64: true });
    if (est.legenda.trim()) zip.file('legenda.txt', est.legenda);
    const blob = await zip.generateAsync({ type: 'blob' }), url = URL.createObjectURL(blob);
    baixar(url, `${slug(est.nome)}.zip`); setTimeout(() => URL.revokeObjectURL(url), 5000);
  }));

  // ---- salvar ---------------------------------------------------------------------------------
  async function salvar() {
    let miniatura = '';
    try { miniatura = await imagem(0, 'jpg', 360); } catch (e) { /* sem miniatura, salva assim mesmo */ }
    const j = await post(cfg.urls.salvar, { id: est.id, nome: est.nome, formato: est.formato, slides: est.slides, legenda: est.legenda, miniatura });
    if (!est.id) { est.id = j.id; history.replaceState(null, '', j.url); }
    est.sujo = false; $('es-salvar').textContent = 'Salvo ✓';
    setTimeout(() => { if (!est.sujo) $('es-salvar').textContent = 'Salvar'; }, 2500);
  }
  $('es-salvar').addEventListener('click', (e) => ocupado(e.target, salvar));
  document.addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); $('es-salvar').click(); } });
  window.addEventListener('beforeunload', (e) => { if (est.sujo) { e.preventDefault(); e.returnValue = ''; } });

  // ---- barra de cima ----------------------------------------------------------------------------
  $('es-nome').value = est.nome;
  $('es-nome').addEventListener('input', (e) => { est.nome = e.target.value; $('migalha').textContent = est.nome; marcarSujo(); });
  Object.entries(cfg.formatos).forEach(([k, f]) => $('es-formato').append(el('option', { value: k, selected: k === est.formato }, `${f.nome} (${f.w}x${f.h})`)));
  $('es-formato').addEventListener('change', (e) => { est.formato = e.target.value; marcarSujo(); tudo(); });
  Object.entries(cfg.tipos).forEach(([k, t]) => $('es-novo-tipo').append(el('option', { value: k }, t.nome)));
  $('es-adicionar').addEventListener('click', () => {
    if (est.slides.length >= cfg.max_slides) return;
    est.slides.splice(est.atual + 1, 0, M.novo($('es-novo-tipo').value)); est.atual += 1; marcarSujo(); tudo();
  });
  $('es-guias').addEventListener('change', desenharPalco);
  $('es-legenda').value = est.legenda;
  const contarLegenda = () => { $('es-legenda-conta').textContent = `${est.legenda.length}/2200 caracteres`; };
  $('es-legenda').addEventListener('input', (e) => { est.legenda = e.target.value; contarLegenda(); marcarSujo(); });
  contarLegenda();
  $('es-copiar').addEventListener('click', async (e) => { await navigator.clipboard.writeText(est.legenda); e.target.textContent = 'Copiada ✓'; setTimeout(() => { e.target.textContent = 'Copiar legenda'; }, 2000); });
  window.addEventListener('resize', () => { clearTimeout(pendente); pendente = setTimeout(tudo, 150); });

  // ---- IA ---------------------------------------------------------------------------------------
  const dIA = $('es-dialogo-ia');
  $('es-ia').addEventListener('click', () => {
    if (!cfg.ia_ligada) { alert('A IA não está configurada no servidor (falta a ANTHROPIC_API_KEY).'); return; }
    $('es-ia-erro').textContent = ''; dIA.showModal();
  });
  $('es-ia-gerar').addEventListener('click', (e) => ocupado(e.target, async () => {
    const ajustar = dIA.querySelector('[name=es-ia-modo]:checked').value === 'ajustar';
    const pedido = $('es-ia-pedido').value.trim();
    if (!pedido) { $('es-ia-erro').textContent = 'Escreva o que você quer no post.'; return; }
    if (!ajustar && est.sujo && !confirm('O post novo vai substituir os slides e a legenda que estão no editor. Continuar?')) return;
    $('es-ia-erro').textContent = 'A IA está montando o post. Isso leva de 20 segundos a 1 minuto…';
    try {
      const j = await post(cfg.urls.ia, { pedido, formato: est.formato, ajustar, slides: est.slides, legenda: est.legenda });
      est.slides = j.slides; est.legenda = j.legenda || est.legenda; if (!ajustar) { est.nome = j.nome; $('es-nome').value = est.nome; $('migalha').textContent = est.nome; }
      $('es-legenda').value = est.legenda; contarLegenda(); est.atual = 0; marcarSujo(); dIA.close(); tudo();
    } catch (erro) { $('es-ia-erro').textContent = erro.message; }
  }));

  // ---- modelos ----------------------------------------------------------------------------------
  const dMod = $('es-dialogo-modelos');
  $('es-modelos').addEventListener('click', () => {
    const lista = $('es-modelos-lista'); lista.innerHTML = '';
    if (!MODELOS.length) lista.append(el('p', { class: 'es-quieto' }, 'Ainda não há modelos para esta marca. Use a IA ou comece do zero.'));
    dMod.showModal();
    const formatoAtual = est.formato, slidesAtuais = est.slides;
    MODELOS.forEach((m) => {
      const img = el('div', { class: 'es-mini-img' });
      lista.append(el('button', { type: 'button', class: 'es-modelo', on: { click: () => {
        if (est.slides.length > 1 && !confirm(`Trocar os slides deste post pelo modelo "${m.nome}"?`)) return;
        est.formato = m.formato; est.slides = copia(m.slides); est.legenda = m.legenda || ''; est.atual = 0;
        if (!est.id) { est.nome = m.nome.replace(/^(Post|Destaque): /, ''); $('es-nome').value = est.nome; }
        $('es-formato').value = est.formato; $('es-legenda').value = est.legenda; contarLegenda(); marcarSujo(); dMod.close(); tudo();
      } } }, img, el('b', {}, m.nome)));
      est.formato = m.formato; est.slides = m.slides;
      miniatura(0, img, 150);
      est.formato = formatoAtual; est.slides = slidesAtuais;
    });
  });

  // começa
  if (!inicial.id && !inicial.slides.length) est.sujo = false;
  requestAnimationFrame(tudo);
  document.fonts.ready.then(() => tudo());
})();
