/* Editor de carrossel do painel. Desenha os slides no navegador (carrossel.js e modelos),
 * salva sozinho o que a pessoa muda (o servidor confere tudo de novo: carrosseis/servicos.py)
 * e baixa os slides em PNG ou num ZIP. Os dados iniciais vêm do <script id="dados-carrossel">. */
(async function () {
  const C = window.Carrossel, $ = (id) => document.getElementById(id);
  const D = JSON.parse($('dados-carrossel').textContent);
  const CSRF = (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';

  // ---- o que cada tipo de slide tem para editar (mesmos limites de carrosseis/roteiro.py) --
  const CAMPOS = {
    capa: [['selo', 'Etiqueta de cima', 28], ['titulo', 'Título', 60, 'marca']],
    texto: [['rotulo', 'Etiqueta de cima', 24], ['titulo', 'Título', 60, 'marca'], ['texto', 'Texto', 110, 'area']],
    produto: [['rotulo', 'Etiqueta de cima', 24], ['titulo', 'Nome do produto', 70, 'marca'], ['chips', 'Destaques', 18, 'lista', 3]],
    preco: [], prova: [['titulo', 'Título', 50, 'marca'], ['texto', 'Texto', 90, 'area']],
    cta: [['titulo', 'Chamada', 40, 'marca'], ['botao', 'Texto do botão', 18], ['passos', 'Passos', 42, 'lista', 3]],
    final: [['titulo', 'Título', 50, 'marca'], ['texto', 'Texto', 80, 'area']],
    vantagens: [['rotulo', 'Etiqueta de cima', 24], ['titulo', 'Título', 40, 'marca'], ['itens', 'Vantagens', 40, 'lista', 4]],
    numeros: [['rotulo', 'Etiqueta de cima', 24], ['titulo', 'Título', 40, 'marca'], ['numeros', 'Números', 0, 'numeros', 3]],
    anotado: [['rotulo', 'Etiqueta de cima', 24], ['titulo', 'Título', 40, 'marca'], ['rotulos', 'Qualidades', 24, 'lista', 4]],
  };
  const NOMES_TIPO = { capa: 'Capa', texto: 'Texto + arte', produto: 'Produto', preco: 'Preço', prova: 'Avaliações', cta: 'Chamada', final: 'Final', vantagens: 'Vantagens', numeros: 'Em números', anotado: 'Qualidades' };
  const NOVOS = { padrao: ['texto', 'produto', 'prova', 'final'], premium: ['vantagens', 'numeros', 'anotado'] };
  const NOVO_EXEMPLO = { texto: { rotulo: 'Sabe quando', titulo: 'Escreva aqui o *gancho*', texto: 'Uma frase curta explicando.' }, produto: { rotulo: 'Conheça', titulo: D.produto.nome || 'Nome do produto', chips: ['Destaque 1', 'Destaque 2'] },
    prova: { titulo: 'Quem comprou *aprovou*', texto: 'Nota alta e muitas vendas.' }, final: { titulo: 'Gostou? *Salva* e compartilha', texto: 'Siga para mais achadinhos' },
    vantagens: { rotulo: 'Por que vale a pena', titulo: 'Escreva o *título*', itens: ['Vantagem 1', 'Vantagem 2', 'Vantagem 3'] },
    numeros: { rotulo: 'Em números', titulo: 'Escreva o *título*', numeros: [{ valor: '1', legenda: 'legenda' }, { valor: '2', legenda: 'legenda' }] },
    anotado: { rotulo: 'Em detalhes', titulo: 'Escreva o *título*', rotulos: ['Qualidade 1', 'Qualidade 2', 'Qualidade 3', 'Qualidade 4'] } };
  const MODELOS = { padrao: [['destaque', 'Destaque'], ['editorial', 'Editorial'], ['promo', 'Promo'], ['neon', 'Neon'], ['polaroid', 'Polaroid'], ['bento', 'Bento']],
    premium: [['vitrine', 'Vitrine'], ['anotado', 'Anotado'], ['etiqueta', 'Etiqueta'], ['ficha', 'Ficha']] };
  const FAMILIA = (m) => (MODELOS.premium.some(([k]) => k === m) ? 'premium' : 'padrao');
  const TEMAS = [['verde', '#1F3A2E'], ['laranja', '#E8541E'], ['rosa', '#D6336C'], ['azul', '#2F6FDE'], ['preto', '#141414']];
  const plano = D.premium ? 'premium' : 'padrao';

  // ---- estado --------------------------------------------------------------------------
  const copia = (x) => JSON.parse(JSON.stringify(x));
  const carregar = (u, cors) => new Promise((ok) => { if (!u) return ok(null); const i = new Image(); if (cors) i.crossOrigin = 'anonymous'; i.onload = () => ok(i); i.onerror = () => ok(null); i.src = u; });
  function semFoto() { // se a foto da Shopee não carregar, o slide sai com um quadro neutro no lugar
    const k = document.createElement('canvas'); k.width = k.height = 800; const c = k.getContext('2d'); c.fillStyle = '#ECE8DD'; c.fillRect(0, 0, 800, 800);
    c.fillStyle = '#9A9384'; c.font = '600 44px "DM Sans", sans-serif'; c.textAlign = 'center'; c.fillText('Foto indisponível', 400, 410); return k; }
  const fotoShopee = (await carregar(D.produto.imagem, true)) || semFoto();
  let fotoPropria = await carregar(D.fotoPropria, false);
  let recorte = await carregar(D.recorte, false); // o produto sem fundo (PNG recortado nas bordas), se já foi feito
  await Promise.all(['400 40px "DM Sans"', '500 40px "DM Sans"', '700 40px "DM Sans"', '800 40px "DM Sans"', '400 40px "Bebas Neue"', '900 40px "Playfair Display"', 'italic 800 40px "Playfair Display"', '700 40px "JetBrains Mono"',
    '400 40px "Instrument Serif"', '700 40px "Sora"', '800 40px "Sora"', '500 40px "Manrope"', '800 40px "Manrope"'].map((x) => document.fonts.load(x).catch(() => null)));

  const originais = {}; ['padrao', 'premium'].forEach((f) => Object.values((D.originais || {})[f] || {}).forEach((s) => { originais[s._id] = s; }));
  let seq = 1000; ['padrao', 'premium'].forEach((f) => ((D.roteiros || {})[f] || []).forEach((s) => { seq = Math.max(seq, s._id || 0, s._orig || 0); }));
  const est = Object.assign({ roteiros: { padrao: D.roteiros.padrao || [], premium: D.roteiros.premium || [] }, legenda: D.legenda || '', hashtags: D.hashtags || '' }, D.opcoes);
  est.familia = FAMILIA(est.modelo);
  if (est.familia === 'premium' && plano !== 'premium') { est.modelo = 'destaque'; est.familia = 'padrao'; }
  let atual = 0, timerAudit = null, avisos = [];
  const roteiro = () => est.roteiros[est.familia];
  const arteDoProduto = () => ((est.roteiros.padrao || []).find((s) => s.tipo === 'texto' && s.arte) || {}).arte || 'presente';

  function dados() {
    const p = D.produto, d = { nome: p.nome, por: p.preco, de: p.de || 0, desconto: p.desconto || 0, nota: p.nota || 0, vendas: p.vendas || 0,
      arroba: est.arroba || '', img: fotoPropria || fotoShopee, recorte: (plano === 'premium' && est.usarRecorte !== false) ? recorte : null, det: null };
    if (!est.mostraNota) Object.assign(d, { nota: 0, vendas: 0 });
    if (!est.mostraDe) Object.assign(d, { de: 0, desconto: 0 });
    d.semArrasta = !est.mostraArrasta; return d;
  }
  function opcoes() {
    let tema = est.tema;
    if (est.cor) { const mix = (a, b, q) => { const h = (x) => [1, 3, 5].map((i) => parseInt(x.substr(i, 2), 16)); const A = h(a), B = h(b); return '#' + A.map((v, i) => Math.round(v * q + B[i] * (1 - q)).toString(16).padStart(2, '0')).join(''); };
      C.TEMAS.minha = { a: est.cor, b: mix(est.cor, '#FFFFFF', 0.08), acc: '#F2C230', ink: mix(est.cor, '#141414', 0.18) }; tema = 'minha'; }
    const fonte = est.fonte === 'modelo' ? (est.familia === 'premium' ? 'modelo' : 'moderna') : est.fonte;
    return { tema, fonte, modelo: est.modelo };
  }

  // ---- salvar sozinho ------------------------------------------------------------------
  let timerSalvar = null, salvando = false, pendente = false;
  function status(txt, ruim) { const s = $('statusSalvo'); s.textContent = txt; s.classList.toggle('ruim', !!ruim); }
  function agendarSalvar() { status('Alterações não salvas'); clearTimeout(timerSalvar); timerSalvar = setTimeout(salvarAgora, 1200); }
  async function postar(url, corpo) {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF }, body: JSON.stringify(corpo), credentials: 'same-origin' });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.erro || 'Não consegui falar com o servidor.');
    return j;
  }
  async function salvarAgora() {
    if (salvando) { pendente = true; return; }
    salvando = true; status('Salvando…');
    const op = { modelo: est.modelo, tema: est.tema, cor: est.cor, fonte: est.fonte, usarRecorte: est.usarRecorte, mostraNota: est.mostraNota, mostraDe: est.mostraDe, mostraArrasta: est.mostraArrasta, arroba: est.arroba };
    try { await postar(D.urls.salvar, { roteiros: est.roteiros, opcoes: op, legenda: est.legenda, hashtags: est.hashtags }); status('Salvo'); }
    catch (e) { status('Não salvou', true); toast(e.message); }
    finally { salvando = false; if (pendente) { pendente = false; salvarAgora(); } }
  }
  window.addEventListener('beforeunload', (e) => { if (timerSalvar && $('statusSalvo').textContent !== 'Salvo') { salvarAgora(); e.preventDefault(); e.returnValue = ''; } });

  // ---- conversão entre famílias de modelos (Standard <-> Premium) -----------------------
  // Cada slide convertido guarda a versão de origem (_de); na volta ela é restaurada com o
  // título e a etiqueta que a pessoa tenha editado no meio do caminho.
  const semMarca = (t) => (t || '').replace(/\*/g, '');
  const FAMILIA_TIPO = (t) => (['vantagens', 'numeros', 'anotado'].includes(t) ? 'premium' : ['texto', 'produto', 'prova', 'final'].includes(t) ? 'padrao' : 'ambos');
  function voltar(s, fam) { if (!s._de || FAMILIA_TIPO(s._de.tipo) !== fam) return null; return Object.assign(copia(s._de), { titulo: s.titulo, rotulo: s.rotulo, _id: s._id, _orig: s._orig }); }
  function paraPadrao(r) { return r.map((s) => { const v = voltar(s, 'padrao'); if (v) return v; const b = { _id: s._id, _orig: s._orig, _de: copia(s) }; delete b._de._de;
    if (s.tipo === 'vantagens') return Object.assign(b, { tipo: 'texto', rotulo: s.rotulo, titulo: s.titulo, texto: (s.itens || []).join(' • ').slice(0, 110), arte: arteDoProduto() });
    if (s.tipo === 'numeros') return Object.assign(b, { tipo: 'texto', rotulo: s.rotulo, titulo: s.titulo, texto: (s.numeros || []).map((n) => n.valor + ' ' + n.legenda).join(' • ').slice(0, 110), arte: arteDoProduto() });
    if (s.tipo === 'anotado') return Object.assign(b, { tipo: 'produto', rotulo: s.rotulo, titulo: s.titulo, chips: (s.rotulos || []).slice(0, 3).map((x) => x.slice(0, 18)) });
    return Object.assign(copia(s), { _id: s._id, _orig: s._orig }); }); }
  function paraPremium(r) { return r.filter((s) => s.tipo !== 'prova' && s.tipo !== 'final').map((s) => { const v = voltar(s, 'premium'); if (v) return v; const b = { _id: s._id, _orig: s._orig, _de: copia(s) }; delete b._de._de;
    if (s.tipo === 'texto') return Object.assign(b, { tipo: 'vantagens', rotulo: s.rotulo, titulo: (s.titulo || '').slice(0, 40), itens: (s.texto || '').split(' • ').filter(Boolean).slice(0, 4).map((x) => x.slice(0, 40)) });
    if (s.tipo === 'produto') return Object.assign(b, { tipo: 'anotado', rotulo: s.rotulo, titulo: (s.titulo || '').slice(0, 40), rotulos: (s.chips || []).slice(0, 4) });
    return Object.assign(copia(s), { _id: s._id, _orig: s._orig }); }); }

  // ---- desenho -------------------------------------------------------------------------
  function desenharEm(canvas, i) { C.desenhar(canvas, roteiro(), i, dados(), opcoes()); }
  function miniatura(i) { const aux = $('aux'); desenharEm(aux, i); const m = document.querySelector(`.mini[data-i="${i}"] canvas`); if (!m) return; const c = m.getContext('2d'); c.clearRect(0, 0, m.width, m.height); c.drawImage(aux, 0, 0, m.width, m.height); }
  function redesenhar(soAtual) { desenharEm($('grande'), atual); if (soAtual) miniatura(atual); else roteiro().forEach((_, i) => miniatura(i)); $('pos').textContent = `${atual + 1} / ${roteiro().length}`; agendarAuditoria(); }
  function mudou(soAtual) { redesenhar(soAtual); agendarSalvar(); }
  function montarTira() {
    const t = $('tira'); t.innerHTML = '';
    roteiro().forEach((s, i) => { const d = document.createElement('button'); d.type = 'button'; d.className = 'mini' + (i === atual ? ' on' : ''); d.dataset.i = i;
      d.setAttribute('aria-label', `Slide ${i + 1}: ${NOMES_TIPO[s.tipo] || s.tipo}`);
      d.innerHTML = `<canvas width="192" height="240"></canvas><span class="n">${i + 1}</span>`; d.onclick = () => { atual = i; montarTudo(true); }; t.appendChild(d); });
  }

  // ---- emojis: botão ao lado de cada campo de texto abre a mesma paleta ---------------
  const EMOJIS = '🔥 ✨ 😍 🤩 👀 😱 🥰 🤑 💸 💰 🛒 🛍️ 🎁 📦 🚚 🏷️ ⭐ ✅ 💯 ⚡ 🎉 👉 👇 🙌 ❤️ 💖 💜 💚 🧡 💛 🖤 ☕ 🏠 👶 💄 🎧 🎮 🐶 🍳 🎄'.split(' ');
  let alvoEmoji = null; const paleta = document.createElement('div'); paleta.id = 'emojis'; paleta.hidden = true; paleta.setAttribute('role', 'dialog'); paleta.setAttribute('aria-label', 'Escolher emoji');
  EMOJIS.forEach((e) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = e; b.setAttribute('aria-label', 'Inserir ' + e);
    b.onclick = () => { const el = alvoEmoji; if (!el) return; const i = el.selectionStart ?? el.value.length, j = el.selectionEnd ?? i, antes = el.value.slice(0, i), ins = (antes && !/\s$/.test(antes) ? ' ' : '') + e, novo = antes + ins + el.value.slice(j);
      if (el.maxLength > 0 && novo.length > el.maxLength) return toast('Esse campo já está no limite de caracteres');
      el.value = novo; el.focus(); el.setSelectionRange(i + ins.length, i + ins.length); el.dispatchEvent(new Event('input', { bubbles: true })); paleta.hidden = true; }; paleta.appendChild(b); });
  document.body.appendChild(paleta);
  document.addEventListener('click', (e) => { if (!paleta.hidden && !paleta.contains(e.target) && !e.target.closest('.bt-emoji')) paleta.hidden = true; });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') paleta.hidden = true; });
  function comEmoji(el) { const w = document.createElement('div'); w.className = 'campo-emoji'; const b = document.createElement('button'); b.type = 'button'; b.className = 'bt-emoji'; b.textContent = '😊'; b.setAttribute('aria-label', 'Inserir emoji');
    b.onclick = (ev) => { ev.preventDefault(); if (!paleta.hidden && alvoEmoji === el) { paleta.hidden = true; return; } alvoEmoji = el; paleta.hidden = false;
      const r = b.getBoundingClientRect(), pw = paleta.offsetWidth, x = Math.max(16, Math.min(r.right - pw, window.innerWidth - pw - 16));
      paleta.style.left = (x + window.scrollX) + 'px'; paleta.style.top = (r.bottom + 6 + window.scrollY) + 'px'; paleta.firstChild.focus(); };
    w.append(el, b); return w; }

  // ---- campos de texto -----------------------------------------------------------------
  function palavrasDe(txt) { const out = []; let dentro = false; (txt || '').trim().split(/\s+/).filter(Boolean).forEach((p) => { if (p.startsWith('*')) dentro = true; out.push({ t: p.replace(/\*/g, ''), d: dentro }); if (p.endsWith('*')) dentro = false; }); return out; }
  function juntar(ps) { let s = '', i = 0; while (i < ps.length) { if (ps[i].d) { let j = i; while (j + 1 < ps.length && ps[j + 1].d) j++; s += (s ? ' ' : '') + '*' + ps.slice(i, j + 1).map((p) => p.t).join(' ') + '*'; i = j + 1; } else { s += (s ? ' ' : '') + ps[i].t; i++; } } return s; }
  const escapa = (t) => String(t || '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  function montarFoto() {
    const s = roteiro()[atual], bf = $('blocoFoto'), temModelo = FAMILIA(est.modelo) === 'premium';
    const seg = (k, ops, atualV) => `<div class="seg" data-k="${k}">${ops.map(([v, n]) => `<button type="button" data-v="${v}" class="${atualV === v ? 'on' : ''}" aria-pressed="${atualV === v}">${n}</button>`).join('')}</div>`;
    bf.innerHTML = `<div class="ec-linha"><span>Foto do produto neste slide<span class="selo-premium">PREMIUM</span></span><input type="checkbox" class="sw" role="switch" id="fotoSlide" ${s.semFoto && temModelo ? '' : 'checked'} ${temModelo && plano === 'premium' ? '' : 'disabled'}></div>`
      + (plano !== 'premium' ? '' : !temModelo ? '<p class="dica">Disponível nos modelos com ★.</p>' : s.semFoto
        ? `<div class="ec-linha"><span>Posição do texto</span>${seg('posicao', [['topo', 'Topo'], ['meio', 'Meio'], ['base', 'Base']], s.posicao || 'meio')}</div>`
          + `<div class="ec-linha"><span>Alinhamento</span>${seg('alinhar', [['esq', 'Esquerda'], ['centro', 'Centro']], s.alinhar || 'esq')}</div>` : '');
    const sw = $('fotoSlide'); sw.onchange = () => { s.semFoto = !sw.checked; montarFoto(); mudou(true); };
    bf.querySelectorAll('.seg button').forEach((b) => b.onclick = () => { s[b.parentElement.dataset.k] = b.dataset.v; montarFoto(); mudou(true); });
  }
  function montarCampos() {
    montarFoto(); const s = roteiro()[atual], box = $('campos'); box.innerHTML = '';
    const h = document.createElement('h3'); h.textContent = `Slide ${atual + 1} · ${NOMES_TIPO[s.tipo] || s.tipo}`; box.appendChild(h);
    const campos = CAMPOS[s.tipo] || [];
    if (!campos.length) { const p = document.createElement('div'); p.className = 'info'; p.textContent = 'Este slide usa o preço, a nota e as vendas que vêm da Shopee.' + (plano === 'premium' ? ' Dá para esconder a nota ou o preço antigo na aba Infos.' : ''); box.appendChild(p); }
    campos.forEach(([k, rotulo, max, tipo, qtd]) => {
      const l = document.createElement('label'); l.className = 'ed-campo'; l.append(rotulo);
      if (tipo === 'lista') {
        const lista = document.createElement('div'); lista.className = 'lista'; const vals = (s[k] || []).slice();
        for (let i = 0; i < qtd; i++) { const inp = document.createElement('input'); inp.type = 'text'; inp.maxLength = max; inp.value = vals[i] || ''; inp.placeholder = i < vals.length ? '' : '(opcional)';
          inp.oninput = () => { s[k] = [...lista.querySelectorAll('input')].map((x) => x.value.trim()).filter(Boolean); mudou(true); }; lista.appendChild(comEmoji(inp)); }
        l.appendChild(lista);
      } else if (tipo === 'numeros') {
        const lista = document.createElement('div'); lista.className = 'lista'; const vals = s[k] || [];
        for (let i = 0; i < qtd; i++) { const ln = document.createElement('div'); ln.className = 'linha'; const v = vals[i] || {};
          ln.innerHTML = `<input type="text" maxlength="9" placeholder="valor" aria-label="Valor ${i + 1}" value="${escapa(v.valor)}"><input type="text" maxlength="32" placeholder="legenda" aria-label="Legenda ${i + 1}" value="${escapa(v.legenda)}">`;
          lista.appendChild(ln); }
        lista.oninput = () => { s[k] = [...lista.querySelectorAll('.linha')].map((ln) => { const [a, b] = ln.querySelectorAll('input'); return { valor: a.value.trim(), legenda: b.value.trim() }; }).filter((n) => n.valor); mudou(true); };
        const dica = document.createElement('span'); dica.className = 'dica'; dica.textContent = 'Use só números que estão na página do produto.';
        l.append(lista, dica);
      } else {
        const inp = document.createElement(tipo === 'area' ? 'textarea' : 'input'); if (tipo === 'area') inp.rows = 3; else inp.type = 'text';
        inp.maxLength = max; inp.value = tipo === 'marca' ? semMarca(s[k]) : (s[k] || ''); l.appendChild(comEmoji(inp));
        const conta = document.createElement('span'); conta.className = 'contador'; const atualizaConta = () => { conta.textContent = `${inp.value.length}/${max}`; conta.classList.toggle('mais', inp.value.length >= max); }; atualizaConta(); l.appendChild(conta);
        let chipsBox = null;
        if (tipo === 'marca') { chipsBox = document.createElement('div'); chipsBox.className = 'palavras'; const dica = document.createElement('span'); dica.className = 'dica'; dica.textContent = 'Toque nas palavras para destacar com marca-texto:'; l.append(dica, chipsBox); }
        const chips = () => { if (!chipsBox) return; chipsBox.innerHTML = ''; palavrasDe(s[k]).forEach((p, i, arr) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = p.t; if (p.d) b.className = 'on'; b.setAttribute('aria-pressed', p.d);
          b.onclick = (e) => { e.preventDefault(); arr[i].d = !arr[i].d; s[k] = juntar(arr); chips(); mudou(true); }; chipsBox.appendChild(b); }); };
        chips();
        inp.oninput = () => { atualizaConta();
          if (tipo === 'marca') { const marcadas = new Set(palavrasDe(s[k]).filter((p) => p.d).map((p) => p.t.toLowerCase())); s[k] = juntar(inp.value.split(/\s+/).filter(Boolean).map((t) => ({ t, d: marcadas.has(t.toLowerCase()) }))); chips(); }
          else s[k] = inp.value; mudou(true); };
      }
      box.appendChild(l);
    });
  }

  // ---- auditoria ao vivo (a mesma dos testes) ------------------------------------------
  function traduz(m) { if (/estoura|tamanho mínimo/.test(m)) return 'texto longo demais: encurte um pouco'; if (/sobrepõe|cruza|cortado|está sobre/.test(m)) return 'texto encostando em outro elemento'; if (/contraste/.test(m)) return 'texto difícil de ler com esta cor';
    if (/margem|fora do slide|invade/.test(m)) return 'texto saindo da área do slide'; return 'algo fora do lugar neste slide'; }
  function agendarAuditoria() { clearTimeout(timerAudit); timerAudit = setTimeout(auditar, 350); }
  function auditar() {
    avisos = C.auditar($('audit'), roteiro(), dados(), opcoes()) || [];
    document.querySelectorAll('.mini .alerta').forEach((x) => x.remove());
    const porSlide = {}; avisos.forEach((a) => { (porSlide[a.slide - 1] = porSlide[a.slide - 1] || []).push(a); });
    Object.keys(porSlide).forEach((i) => { if (!porSlide[i].some((a) => a.nivel === 'erro')) return; const m = document.querySelector(`.mini[data-i="${i}"]`); if (m) { const s = document.createElement('span'); s.className = 'alerta'; s.textContent = '!'; m.appendChild(s); } });
    const meus = porSlide[atual] || [], box = $('problemas');
    if (!meus.length) { box.className = 'problemas ok'; box.textContent = 'Tudo certo com este slide.'; }
    else { const unicos = [...new Set(meus.map((a) => traduz(a.msg)))]; const erro = meus.some((a) => a.nivel === 'erro'); box.className = 'problemas ' + (erro ? 'ruim' : 'ok');
      box.innerHTML = (erro ? 'Atenção neste slide:' : 'Dica:') + '<ul>' + unicos.map((u) => `<li>${u}</li>`).join('') + '</ul>'; }
  }

  // ---- montagem / travas ---------------------------------------------------------------
  function aplicarTravas() { document.querySelectorAll('[data-premium]').forEach((el) => el.classList.toggle('fechada', plano !== 'premium')); }
  function montarVisual() {
    const sel = $('modelo'); sel.innerHTML = ''; const lista = plano === 'premium' ? [...MODELOS.premium.map((m) => [...m, 'premium']), ...MODELOS.padrao.map((m) => [...m, 'padrao'])] : MODELOS.padrao.map((m) => [...m, 'padrao']);
    lista.forEach(([k, n, f]) => { const o = document.createElement('option'); o.value = k; o.textContent = n + (plano === 'premium' && f === 'premium' ? ' ★' : ''); if (k === est.modelo) o.selected = true; sel.appendChild(o); });
    const t = $('temas'); t.innerHTML = '';
    TEMAS.forEach(([k, cor]) => { const b = document.createElement('button'); b.type = 'button'; b.style.background = cor; b.title = k; b.setAttribute('aria-label', 'Cor ' + k); if (!est.cor && est.tema === k) b.className = 'on';
      b.onclick = () => { est.tema = k; est.cor = ''; montarVisual(); mudou(); }; t.appendChild(b); });
    const wrap = document.createElement('span'); wrap.className = 'trava' + (plano === 'premium' ? '' : ' fechada');
    wrap.innerHTML = `<input type="color" id="corLivre" value="${est.cor || '#7B3FA0'}" title="Qualquer cor" aria-label="Escolher qualquer cor"><span class="selo-premium">PREMIUM</span>`; t.appendChild(wrap);
    $('corLivre').oninput = (e) => { est.cor = e.target.value; [...t.querySelectorAll('button')].forEach((b) => b.classList.remove('on')); mudou(); };
    $('fonte').value = est.fonte;
    $('mostraNota').checked = est.mostraNota; $('mostraDe').checked = est.mostraDe; $('mostraArrasta').checked = est.mostraArrasta; $('arroba').value = est.arroba;
    $('removerFoto').hidden = !fotoPropria;
    $('removerRecorte').hidden = !recorte; $('linhaRecorte').hidden = !recorte; $('usarRecorte').checked = est.usarRecorte !== false;
    $('tirarFundo').textContent = recorte ? 'Refazer o recorte' : 'Remover o fundo da foto';
    const nv = $('novo'); nv.innerHTML = '<option value="">+ Adicionar slide…</option>'; NOVOS[est.familia].forEach((k) => { const o = document.createElement('option'); o.value = k; o.textContent = NOMES_TIPO[k]; nv.appendChild(o); });
  }
  function montarTudo(soSelecao) {
    if (atual >= roteiro().length) atual = roteiro().length - 1;
    if (!soSelecao) { aplicarTravas(); montarVisual(); $('legenda').value = est.legenda; $('hashtags').value = est.hashtags; }
    montarTira(); montarCampos(); redesenhar();
  }
  function toast(m) { const t = $('toast'); t.textContent = m; t.classList.add('on'); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('on'), 3200); }

  // ---- eventos -------------------------------------------------------------------------
  document.querySelectorAll('.ec-abas button').forEach((b) => b.onclick = () => { document.querySelectorAll('.ec-abas button').forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-selected', x === b); });
    document.querySelectorAll('.aba').forEach((a) => a.classList.toggle('on', a.id === 'aba-' + b.dataset.aba)); });
  $('ant').onclick = () => { if (atual > 0) { atual--; montarTudo(true); } };
  $('prox').onclick = () => { if (atual < roteiro().length - 1) { atual++; montarTudo(true); } };
  const mover = (dx) => { const r = roteiro(), j = atual + dx; if (j < 0 || j >= r.length) return; if (j === 0 || atual === 0) return toast('A capa fica sempre no primeiro slide');
    [r[atual], r[j]] = [r[j], r[atual]]; atual = j; montarTudo(true); agendarSalvar(); };
  $('esq').onclick = () => mover(-1); $('dir').onclick = () => mover(1);
  $('remover').onclick = () => { const r = roteiro(); if (r.length <= 2) return toast('O carrossel precisa de pelo menos 2 slides'); if (atual === 0) return toast('A capa não pode ser removida'); r.splice(atual, 1); montarTudo(true); agendarSalvar(); };
  $('duplicar').onclick = () => { const r = roteiro(); if (r.length >= 10) return toast('Máximo de 10 slides'); if (atual === 0) return toast('A capa não pode ser duplicada'); const c = copia(r[atual]); c._id = ++seq; r.splice(atual + 1, 0, c); atual++; montarTudo(true); agendarSalvar(); };
  $('novo').onchange = (e) => { const k = e.target.value; e.target.value = ''; if (!k) return; const r = roteiro(); if (r.length >= 10) return toast('Máximo de 10 slides');
    const s = Object.assign({ tipo: k }, copia(NOVO_EXEMPLO[k]), { _id: ++seq }); s._orig = s._id; if (k === 'texto') s.arte = arteDoProduto(); originais[s._id] = copia(s); r.splice(atual + 1, 0, s); atual++; montarTudo(true); agendarSalvar(); };
  $('original').onclick = () => { const r = roteiro(), s = r[atual], o = originais[s._orig];
    if (!o || o.tipo !== s.tipo) return toast('Este slide veio de outro modelo; não há original para ele aqui');
    r[atual] = Object.assign(copia(o), { _id: s._id, _orig: s._orig }); montarTudo(true); agendarSalvar(); toast('Slide voltou ao texto original'); };
  $('outra').onclick = async () => { const b = $('outra'), s = roteiro()[atual]; if (!(CAMPOS[s.tipo] || []).length) return toast('Este slide não tem texto para reescrever');
    b.disabled = true; b.textContent = '✨ Escrevendo…';
    try { const j = await postar(D.urls.reescrever, { slide: s, familia: est.familia }); roteiro()[atual] = Object.assign(j.slide, { _id: s._id, _orig: s._orig, _de: s._de }); montarTudo(true); agendarSalvar();
      toast(`Pronto. Restam ${j.restantes.reescritas} reescritas hoje.`); }
    catch (e) { toast(e.message); } finally { b.disabled = false; b.textContent = '✨ Outra versão'; } };
  $('modelo').onchange = (e) => { const novo = e.target.value, fam = FAMILIA(novo);
    if (fam !== est.familia) { est.roteiros[fam] = fam === 'premium' ? paraPremium(roteiro()) : paraPadrao(roteiro()); est.familia = fam; toast('Textos levados para o novo modelo'); }
    est.modelo = novo; montarTudo(); agendarSalvar(); };
  $('fonte').onchange = (e) => { est.fonte = e.target.value; mudou(); };
  $('foto').onchange = async (e) => { const f = e.target.files[0]; e.target.value = ''; if (!f) return; const fd = new FormData(); fd.append('foto', f); toast('Enviando a foto…');
    try { const r = await fetch(D.urls.foto, { method: 'POST', body: fd, headers: { 'X-CSRFToken': CSRF }, credentials: 'same-origin' }); const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.erro || 'Não consegui enviar a foto.');
      fotoPropria = await carregar(j.url, false); recorte = null; montarVisual(); redesenhar(); toast('Foto trocada'); } catch (err) { toast(err.message); } };
  $('removerFoto').onclick = async () => { const fd = new FormData(); fd.append('remover', '1');
    try { const r = await fetch(D.urls.foto, { method: 'POST', body: fd, headers: { 'X-CSRFToken': CSRF }, credentials: 'same-origin' }); if (!r.ok) throw new Error('Não consegui voltar para a foto da Shopee.');
      fotoPropria = null; recorte = null; montarVisual(); redesenhar(); toast('Voltou para a foto da Shopee'); } catch (err) { toast(err.message); } };
  // ---- remover o fundo da foto (no navegador; o servidor só guarda o PNG pronto) -------------------
  // A biblioteca roda a IA em segundo plano (a tela não trava) e baixa o modelo (~40 MB) na primeira vez.
  const FUNDO_LIB = 'https://cdn.jsdelivr.net/npm/@imgly/background-removal@1.5.5/+esm', FUNDO_LADO = 1024;
  let tirando = false;
  function textoProgresso(t) { const p = $('progressoRecorte'); p.textContent = t; p.hidden = !t; }
  async function paraBlob(canvas) { return new Promise((ok, erro) => canvas.toBlob((b) => (b ? ok(b) : erro(new Error('Não consegui preparar a foto.'))), 'image/png')); }
  function cortarNasBordas(img) { // tira a margem transparente em volta do produto: o desenho encaixa o produto pela caixa dele
    const k = document.createElement('canvas'); k.width = img.width; k.height = img.height; const c = k.getContext('2d', { willReadFrequently: true }); c.drawImage(img, 0, 0);
    const px = c.getImageData(0, 0, k.width, k.height).data; let x0 = k.width, y0 = k.height, x1 = -1, y1 = -1;
    for (let y = 0; y < k.height; y++) for (let x = 0; x < k.width; x++) if (px[(y * k.width + x) * 4 + 3] > 24) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    if (x1 < 0) return null; // nada sobrou: a IA não achou o produto
    const m = 3; x0 = Math.max(0, x0 - m); y0 = Math.max(0, y0 - m); x1 = Math.min(k.width - 1, x1 + m); y1 = Math.min(k.height - 1, y1 + m);
    const o = document.createElement('canvas'); o.width = x1 - x0 + 1; o.height = y1 - y0 + 1; o.getContext('2d').drawImage(k, x0, y0, o.width, o.height, 0, 0, o.width, o.height); return o; }
  $('tirarFundo').onclick = async () => {
    if (tirando) return; tirando = true; const botao = $('tirarFundo'), antes = botao.textContent; botao.disabled = true; textoProgresso('Preparando…');
    try {
      const origem = fotoPropria || fotoShopee, esc = Math.min(1, FUNDO_LADO / Math.max(origem.width, origem.height));
      const entrada = document.createElement('canvas'); entrada.width = Math.round(origem.width * esc); entrada.height = Math.round(origem.height * esc);
      entrada.getContext('2d').drawImage(origem, 0, 0, entrada.width, entrada.height);
      let blobEntrada; try { blobEntrada = await paraBlob(entrada); } catch (e) { throw new Error('Não consegui ler essa foto. Tente enviar a foto do produto pelo botão "Escolher outra foto…".'); }
      const lib = await import(FUNDO_LIB);
      const saida = await lib.removeBackground(blobEntrada, { model: 'isnet_quint8', output: { format: 'image/png' },
        progress: (chave, atual, total) => { const baixando = String(chave).startsWith('fetch'); textoProgresso(baixando ? 'Baixando o modelo (só na primeira vez, leva um pouco mais)…' : 'Removendo o fundo… pode levar alguns segundos'); } });
      const url = URL.createObjectURL(saida); const img = await carregar(url, false); URL.revokeObjectURL(url);
      const cortada = img && cortarNasBordas(img); if (!cortada) throw new Error('Não encontrei o produto nessa foto. Tente com outra foto.');
      textoProgresso('Salvando…'); const fd = new FormData(); fd.append('recorte', await paraBlob(cortada), 'recorte.png');
      const r = await fetch(D.urls.recorte, { method: 'POST', body: fd, headers: { 'X-CSRFToken': CSRF }, credentials: 'same-origin' }); const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.erro || 'Não consegui salvar o recorte.');
      recorte = await carregar(j.url, false); est.usarRecorte = true; montarVisual(); redesenhar(); agendarSalvar(); textoProgresso('');
      toast(FAMILIA(est.modelo) === 'premium' ? 'Pronto: o produto agora aparece sem fundo' : 'Pronto. O recorte aparece nos modelos ★');
    } catch (err) { textoProgresso(''); toast(err.message && !/fetch|import|network/i.test(err.message) ? err.message : 'Não consegui remover o fundo agora. Confira sua conexão e tente de novo.'); }
    finally { tirando = false; botao.disabled = false; if (!recorte) botao.textContent = antes; } };
  $('removerRecorte').onclick = async () => { const fd = new FormData(); fd.append('remover', '1');
    try { const r = await fetch(D.urls.recorte, { method: 'POST', body: fd, headers: { 'X-CSRFToken': CSRF }, credentials: 'same-origin' }); if (!r.ok) throw new Error('Não consegui apagar o recorte.');
      recorte = null; montarVisual(); redesenhar(); toast('Voltou para a foto inteira'); } catch (err) { toast(err.message); } };
  $('usarRecorte').onchange = (e) => { est.usarRecorte = e.target.checked; mudou(); };
  ['mostraNota', 'mostraDe', 'mostraArrasta'].forEach((k) => $(k).onchange = (e) => { est[k] = e.target.checked; mudou(); });
  $('arroba').oninput = (e) => { let v = e.target.value.trim().replace(/\s+/g, ''); if (v && !v.startsWith('@')) v = '@' + v; est.arroba = v; mudou(); };
  $('salvarPadrao').onclick = async () => { try { await postar(D.urls.padrao, { opcoes: { modelo: est.modelo, tema: est.tema, cor: est.cor, fonte: est.fonte, arroba: est.arroba, mostraNota: est.mostraNota, mostraDe: est.mostraDe, mostraArrasta: est.mostraArrasta } });
    toast('Padrão salvo para os próximos carrosséis'); } catch (e) { toast(e.message); } };
  $('legenda').oninput = (e) => { est.legenda = e.target.value; agendarSalvar(); }; $('hashtags').oninput = (e) => { est.hashtags = e.target.value; agendarSalvar(); };
  { const lg = $('legenda'), lab = lg.parentNode; lab.appendChild(comEmoji(lg)); }
  $('copiar').onclick = async () => { const txt = est.legenda + '\n\n' + est.hashtags; try { await navigator.clipboard.writeText(txt); toast('Legenda copiada'); } catch (e) { $('legenda').select(); toast('Selecione e copie a legenda'); } };

  // ---- baixar --------------------------------------------------------------------------
  const nomeArq = (i) => `carrossel-${D.id}-${String(i + 1).padStart(2, '0')}.png`;
  const pngDo = (i) => new Promise((ok) => { const aux = $('aux'); desenharEm(aux, i); aux.toBlob((b) => ok(b), 'image/png'); });
  function entregar(blob, nome) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = nome; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); }
  let insistiu = false; // 2º toque em "Baixar" com problema = baixar mesmo assim
  function podeBaixar() { if (avisos.some((a) => a.nivel === 'erro') && !insistiu) { insistiu = true; toast('Algum slide tem texto com problema (marcado com !). Toque de novo para baixar mesmo assim.'); return false; } insistiu = false; return true; }
  $('baixar').onclick = async () => { if (!podeBaixar()) return; entregar(await pngDo(atual), nomeArq(atual)); };
  $('baixarTodos').onclick = async () => { if (!podeBaixar()) return; const b = $('baixarTodos'); b.disabled = true; b.textContent = 'Preparando…';
    try { const zip = new window.JSZip(); for (let i = 0; i < roteiro().length; i++) zip.file(nomeArq(i), await pngDo(i));
      zip.file('legenda.txt', est.legenda + '\n\n' + est.hashtags + '\n\nSeu link de afiliado (para a bio): ' + (D.produto.link || '') + '\n');
      entregar(await zip.generateAsync({ type: 'blob' }), `carrossel-${D.id}.zip`); } finally { b.disabled = false; b.textContent = 'Baixar todos (ZIP)'; } };
  $('copiarLink').onclick = async () => { try { await navigator.clipboard.writeText(D.produto.link); toast('Link copiado'); } catch (e) { toast('Não deu para copiar: ' + D.produto.link); } };

  window.EDITOR = { get est() { return est; }, get avisos() { return avisos; }, auditar, salvarAgora };
  montarTudo(); status('Salvo');
})();
