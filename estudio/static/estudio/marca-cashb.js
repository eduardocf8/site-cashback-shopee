/* Estúdio de posts: o desenho dos slides da cash-b.
 * Segue o BRAND.md e os componentes de marketing/instagram/carrossel_base.py: Familjen Grotesk no
 * texto, JetBrains Mono em todo número de dinheiro ou percentual, roxo para marca e ação, verde
 * para dinheiro, âmbar só para o grifo (no máximo um por slide). Os slides são desenhados com
 * 432 px de largura e ampliados 2,5x, a mesma escala dos carrosséis publicados (420 -> 1080). */
(function () {
  const BRAND = '#6d28d9', BRAND_LIGHT = '#a78bfa', BRAND_DARK = '#4c1d95', PAPER = '#f8fafc', PAPER_2 = '#f1eefb', INK = '#111827',
    LINE = '#e0dcef', SUCCESS = '#059669', HIGHLIGHT = '#f59e0b', MUTED = '#6b7280';
  const GRADIENTE = `linear-gradient(165deg, ${BRAND_DARK} 0%, ${BRAND} 55%, ${BRAND_LIGHT} 100%)`;
  const CORES = { roxo: GRADIENTE, claro: PAPER, lilas: PAPER_2, escuro: INK, branco: '#FFFFFF' };
  const ESCUROS = { roxo: true, escuro: true };

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const marcar = (s) => esc(s).replace(/\*([^*]+)\*/g, '<em>$1</em>').replace(/cash-b/g, '<span class="nw">cash-b</span>')
    .replace(/R\$ /g, 'R$$&nbsp;').replace(/e-mail/g, 'e&#8209;mail');

  function base(formato) {
    if (formato === 'story') return { w: 432, h: 768, escala: 2.5 };
    if (formato === 'quadrado') return { w: 432, h: 432, escala: 2.5 };
    return { w: 432, h: 540, escala: 2.5 };
  }

  // ---- fundos: a família de marketing/gerar_fundos_marca.py ---------------------------------
  const mancha = (cx, cy, r, op) => `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${BRAND_LIGHT}" opacity="${op}"/>`;
  function arcos(cx, cy, r0, n, passo, op) {
    let s = ''; for (let i = 0; i < n; i++) s += `<circle cx="${cx}" cy="${cy}" r="${r0 + i * passo}" fill="none" stroke="${BRAND_LIGHT}" stroke-width="1" opacity="${op}"/>`; return s;
  }
  const ARTES = {
    manchas: (l, a, o) => { const m = Math.min(l, a); return mancha(l * .04, a * .06, m * .30, o(.22)) + mancha(l * .98, a * .92, m * .34, o(.22)) + arcos(l * .97, a * .10, m * .17, 4, 10.4, o(.30)); },
    ondas: (l, a, o) => { const m = Math.min(l, a); return arcos(-l * .10, a * 1.05, m * .28, 7, m * .045, o(.30)) + arcos(l * 1.10, -a * .05, m * .28, 7, m * .045, o(.30)); },
    canto: (l, a, o) => { const m = Math.min(l, a); return mancha(l * .02, a * 1.02, m * .52, o(.20)) + mancha(l * .16, a * .92, m * .26, o(.16)) + arcos(l * .97, a * .10, m * .17, 4, 10.4, o(.30)); },
    moldura: (l, a, o) => { const r = Math.min(l, a) * .26; return mancha(0, 0, r, o(.22)) + mancha(l, 0, r * .8, o(.22)) + mancha(0, a, r * .85, o(.22)) + mancha(l, a, r, o(.22)); },
    diagonal: (l, a, o) => { const d = Math.max(l, a); return `<ellipse cx="${l * .5}" cy="${a * .5}" rx="${d * .85}" ry="${d * .16}" fill="${BRAND_LIGHT}" opacity="${o(.16)}" transform="rotate(-24 ${l * .5} ${a * .5})"/>`
      + `<ellipse cx="${l * .62}" cy="${a * .66}" rx="${d * .70}" ry="${d * .10}" fill="${BRAND_LIGHT}" opacity="${o(.12)}" transform="rotate(-24 ${l * .62} ${a * .66})"/>` + arcos(l * .02, a * .04, Math.min(l, a) * .14, 4, 10.4, o(.30)); },
    halo: (l, a, o) => { const m = Math.min(l, a); return arcos(l * .5, a * .5, m * .30, 6, m * .055, o(.22)) + mancha(l * .5, a * .5, m * .26, o(.10)); },
  };
  // no claro a mancha precisa de mais tinta para existir (mesma regra do gerador original)
  const MAIS_TINTA = { 0.22: 0.30, 0.20: 0.28, 0.16: 0.24, 0.30: 0.38 };
  function fundo(f, l, a) {
    f = f || {};
    if (f.modo === 'imagem' && f.imagem) {
      const veu = Math.min(Math.max(+f.veu || 0, 0), 0.85);
      return { escuro: veu >= 0.3, html: `<div class="fundo" style="background:#111 url('${esc(f.imagem)}') center/cover no-repeat"></div>` + (veu ? `<div class="fundo" style="background:rgba(17,24,39,${veu})"></div>` : '') };
    }
    if (f.modo === 'arte' && ARTES[f.arte]) {
      const claro = f.tom === 'claro', o = (x) => claro ? (MAIS_TINTA[x] || x) : x;
      const bg = claro ? PAPER : `linear-gradient(135deg, ${BRAND_DARK}, ${BRAND})`;
      return { escuro: !claro, html: `<div class="fundo" style="background:${bg}"><svg width="${l}" height="${a}" viewBox="0 0 ${l} ${a}">${ARTES[f.arte](l, a, o)}</svg></div>` };
    }
    const cor = CORES[f.cor] ? f.cor : 'claro';
    return { escuro: !!ESCUROS[cor], roxo: cor === 'roxo', html: `<div class="fundo" style="background:${CORES[cor]}"></div>` };
  }

  // ---- peças -------------------------------------------------------------------------------
  const tag = (s) => s.chapeu ? `<span class="tag">${esc(s.chapeu)}</span>` : '';
  const p = (txt, cls) => txt ? `<div class="${cls || 'sub'}">${marcar(txt)}</div>` : '';
  const check = '<svg viewBox="0 0 24 24" fill="none"><path d="M4 12.5l5 5L20 6" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  function moldura(ctx, ultimo) {
    if (ctx.formato === 'story' || ctx.total < 2) return '';
    const pct = ((ctx.i + 1) / ctx.total) * 100;
    const setinha = ultimo ? '' : '<div class="seta" data-decor><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M9 6l6 6-6 6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg></div>';
    return `${setinha}<div class="progresso" data-decor><div class="trilho"><div style="width:${pct}%"></div></div><span>${ctx.i + 1}/${ctx.total}</span></div>`;
  }

  const TIPOS = {
    capa: (s) => `${tag(s)}<h1>${marcar(s.titulo)}</h1>${p(s.texto)}${s.selo ? `<div class="pilulas"><span class="pilula">${marcar(s.selo)}</span></div>` : ''}`,
    texto: (s) => `${tag(s)}<h2>${marcar(s.titulo)}</h2>${p(s.texto)}${s.destaque ? `<div class="destaque">${marcar(s.destaque)}</div>` : ''}`,
    lista(s) {
      const itens = (s.itens || []).map((it, k) => s.numerada
        ? `<div class="item"><div class="linha"><span class="num">${String(k + 1).padStart(2, '0')}</span><b>${marcar(it.titulo)}</b></div>${it.texto ? `<div class="desc recuo-num">${marcar(it.texto)}</div>` : ''}</div>`
        : `<div class="item"><div class="linha"><span class="ck">${check}</span><b>${marcar(it.titulo)}</b></div>${it.texto ? `<div class="desc recuo-ck">${marcar(it.texto)}</div>` : ''}</div>`).join('');
      return `${tag(s)}<h2>${marcar(s.titulo)}</h2>${p(s.texto)}<div class="itens">${itens}</div>`;
    },
    valores(s) {
      const linhas = (s.linhas || []).map((x) => `<div class="valor"><span>${marcar(x.rotulo)}${x.detalhe ? `<small>${marcar(x.detalhe)}</small>` : ''}</span><b>${esc(x.valor)}</b></div>`).join('');
      return `${tag(s)}<h2>${marcar(s.titulo)}</h2><div class="valores">${linhas}</div>${p(s.nota, 'nota')}`;
    },
    numero(s) {
      const pares = (s.pares || []).map((x) => `<div class="gigante"><b>${esc(x.valor)}</b><span>${marcar(x.legenda)}</span></div>`).join('');
      return `${tag(s)}${s.titulo ? `<h2>${marcar(s.titulo)}</h2>` : ''}<div class="gigantes">${pares}</div>${p(s.texto)}`;
    },
    comparacao(s) {
      const casos = (s.itens || []).map((x) => `<div class="caso"><span>${marcar(x.titulo)}</span><b>${marcar(x.texto)}</b></div>`).join('');
      return `${tag(s)}<h2>${marcar(s.titulo)}</h2><div class="casos">${casos}</div>`;
    },
    cta: (s) => `<div class="centro"><h1>${marcar(s.titulo)}</h1>${p(s.texto)}${s.botao ? `<div class="cta"><span>${marcar(s.botao)}</span></div>` : ''}</div>`,
  };

  const ehCapa = (s, ctx) => ctx.formato !== 'story' && (s.capa === true || (s.capa === undefined && ctx.i === 0));

  function render(s, ctx) {
    const b = base(ctx.formato), f = fundo(s.fundo, b.w, b.h);
    const tipo = TIPOS[s.tipo] ? s.tipo : 'capa';
    const a = s.ajustes || {};
    const cls = ['ec', 'slide', `t-${tipo}`, `f-${ctx.formato}`, f.escuro ? 'escuro' : '', f.roxo ? 'roxo' : '', ctx.formato === 'story' ? 'story' : '',
      ehCapa(s, ctx) ? 'capa-grade' : '', a.posicao ? `v-${a.posicao}` : '', a.alinhar ? `al-${a.alinhar}` : ''].filter(Boolean).join(' ');
    const ultimo = ctx.i === ctx.total - 1;
    return `<section class="${cls}" style="width:${b.w}px;height:${b.h}px">${f.html}<div class="conteudo"><div class="bloco">${TIPOS[tipo](s)}</div></div>${moldura(ctx, ultimo)}</section>`;
  }

  // Avisos de marca que a checagem de margens não pega.
  function avisos(s) {
    const txt = [s.titulo, s.texto, s.destaque, s.selo].concat((s.itens || []).map((i) => i.titulo + ' ' + i.texto)).join(' ');
    const lista = [];
    if ((txt.match(/\*[^*]+\*/g) || []).length > 1) lista.push('A cash-b usa o grifo no máximo uma vez por slide.');
    if (/cash-?b/i.test(txt) && /(Cash-B|CashB|CASH-B|Cash-b|cash b)/.test(txt)) lista.push('Escreva sempre "cash-b", minúsculo e com hífen.');
    if (/\bPIX\b/.test(txt)) lista.push('Escreva "Pix", não "PIX".');
    return lista;
  }

  function novo(tipo) {
    const f = (cor) => ({ modo: 'cor', cor });
    return ({
      capa: { tipo, chapeu: 'cash-b explica', titulo: 'Seu título com *destaque.*', texto: 'Uma frase curta que puxa para o próximo slide.', selo: '', fundo: f('claro') },
      texto: { tipo, chapeu: 'o problema', titulo: 'Título do slide', texto: 'Explicação em duas ou três linhas.', destaque: '', fundo: f('escuro') },
      lista: { tipo, chapeu: 'como funciona', titulo: '3 passos e pronto', texto: '', numerada: true, itens: [{ titulo: 'Encontre o produto', texto: 'Explicação curta.' }, { titulo: 'Compre normalmente', texto: 'Explicação curta.' }, { titulo: 'Receba cashback', texto: 'Explicação curta.' }], fundo: f('claro') },
      valores: { tipo, chapeu: 'na prática', titulo: 'Quanto volta para você', linhas: [{ rotulo: 'Compra de R$ 100', valor: 'R$ 3,00', detalhe: '' }, { rotulo: 'Compra de R$ 300', valor: 'R$ 9,00', detalhe: '' }], nota: '', fundo: f('claro') },
      numero: { tipo, chapeu: 'em números', titulo: '', pares: [{ valor: '3%', legenda: 'de cashback médio' }], texto: '', fundo: f('escuro') },
      comparacao: { tipo, chapeu: 'compare', titulo: 'Mesma compra, dois caminhos', itens: [{ titulo: 'Comprando direto na Shopee', texto: 'Nada volta para você.' }, { titulo: 'Comprando pela cash-b', texto: 'Parte da comissão volta via Pix.' }], fundo: f('claro') },
      cta: { tipo, titulo: 'Bora começar?', texto: '', botao: 'cash-b.com', fundo: f('roxo') },
    })[tipo];
  }

  function css(cfg) {
    const F = cfg.fontes;
    return `
@font-face { font-family: ECF; src: url(${F.familjen}) format("woff2"); font-weight: 400 700; }
@font-face { font-family: ECM; src: url(${F.mono}) format("woff2"); font-weight: 400 700; }
.ec, .ec * { box-sizing: border-box; margin: 0; padding: 0; }
.ec { font-family: ECF, sans-serif; color: ${INK}; position: relative; overflow: hidden; display: flex; flex-direction: column; text-align: left; line-height: normal; -webkit-font-smoothing: antialiased; }
.ec > .fundo { position: absolute; inset: 0; }
.ec > .fundo svg { position: absolute; inset: 0; display: block; }
.ec .conteudo { position: relative; flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 44px 36px 52px; }
.ec.f-retrato.capa-grade .conteudo { padding: 64px 70px 64px; }
.ec.f-quadrado.capa-grade .conteudo { padding: 44px 70px 52px; }
.ec.story .conteudo { padding: 100px 28px 120px; }
.ec.escuro { color: #fff; }
.ec .nw { white-space: nowrap; }
.ec .tag { display: block; font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: ${BRAND}; margin-bottom: 16px; }
.ec.escuro .tag { color: rgba(255,255,255,.6); }
.ec.roxo .tag { color: rgba(255,255,255,.75); }
.ec h1 { font-size: 32px; font-weight: 700; line-height: 1.16; letter-spacing: -.025em; }
.ec h2 { font-size: 26px; font-weight: 700; line-height: 1.16; letter-spacing: -.025em; }
.ec.story h1 { font-size: 36px; }
.ec.story h2 { font-size: 29px; }
.ec em { font-style: normal; background: linear-gradient(to top, ${HIGHLIGHT} 0 .32em, transparent .32em); padding: 0 .04em; -webkit-box-decoration-break: clone; box-decoration-break: clone; }
.ec.escuro em { background: ${HIGHLIGHT}; color: ${INK}; padding: 0 .1em; border-radius: 3px; }
.ec .sub { font-size: 14.5px; color: ${MUTED}; margin-top: 16px; line-height: 1.55; max-width: 330px; }
.ec.escuro .sub { color: rgba(255,255,255,.75); }
.ec.roxo .sub { color: rgba(255,255,255,.88); }
.ec.story .sub { font-size: 16px; }
.ec .pilulas { display: flex; gap: 10px; margin-top: 24px; flex-wrap: wrap; }
.ec .pilula { font-size: 11px; font-weight: 700; padding: 7px 14px; border-radius: 20px; background: ${PAPER_2}; color: ${BRAND_DARK}; white-space: nowrap; }
.ec.escuro .pilula { background: rgba(255,255,255,.10); color: ${BRAND_LIGHT}; }
.ec .destaque { margin-top: 18px; padding: 13px 16px; background: rgba(245,158,11,.14); border-left: 3px solid ${HIGHLIGHT}; border-radius: 6px; font-size: 13.5px; line-height: 1.5; }
.ec.escuro .destaque { background: rgba(245,158,11,.16); color: #fff; }
.ec .itens { margin-top: 12px; }
.ec .item { padding: 12px 0; border-bottom: 1px solid ${LINE}; }
.ec.escuro .item { border-color: rgba(255,255,255,.12); }
.ec .item .linha { display: flex; align-items: center; gap: 14px; }
.ec .item b { font-size: 14.5px; font-weight: 700; }
.ec .item .ck { flex: none; width: 18px; height: 18px; color: ${BRAND}; }
.ec.escuro .item .ck { color: ${BRAND_LIGHT}; }
.ec .item .ck svg { width: 18px; height: 18px; display: block; }
.ec .item .num { flex: none; min-width: 32px; font-family: ECM; font-size: 24px; font-weight: 700; color: ${BRAND}; line-height: 1; }
.ec.escuro .item .num { color: ${BRAND_LIGHT}; }
.ec .item .linha:has(.num) { gap: 16px; }
.ec .desc { font-size: 12.5px; color: ${MUTED}; margin-top: 4px; line-height: 1.45; }
.ec.escuro .desc { color: rgba(255,255,255,.62); }
.ec .recuo-ck { margin-left: 32px; }
.ec .recuo-num { margin-left: 48px; }
.ec .valores { margin-top: 14px; }
.ec .valor { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 0; border-bottom: 1px solid ${LINE}; }
.ec.escuro .valor { border-color: rgba(255,255,255,.12); }
.ec .valor > span { font-size: 14px; }
.ec.escuro .valor > span { color: rgba(255,255,255,.75); }
.ec .valor small { display: block; font-size: 11px; color: ${MUTED}; margin-top: 2px; }
.ec .valor b { font-family: ECM; font-size: 16px; font-weight: 700; color: ${SUCCESS}; white-space: nowrap; letter-spacing: -.02em; }
.ec.escuro .valor b { color: #fff; }
.ec .nota { font-size: 11px; color: ${MUTED}; margin-top: 16px; line-height: 1.45; }
.ec.escuro .nota { color: rgba(255,255,255,.5); }
.ec .gigantes { display: flex; flex-direction: column; gap: 22px; margin-top: 8px; }
.ec .gigante b { display: block; font-family: ECM; font-size: 56px; font-weight: 700; line-height: 1; letter-spacing: -.06em; color: ${BRAND}; }
.ec.escuro .gigante b { color: ${HIGHLIGHT}; }
.ec .gigante > span { display: block; font-size: 14px; color: ${MUTED}; margin-top: 12px; line-height: 1.5; max-width: 300px; }
.ec.escuro .gigante > span { color: rgba(255,255,255,.65); }
.ec .casos { margin-top: 12px; }
.ec .caso { padding: 13px 0; border-bottom: 1px solid ${LINE}; }
.ec.escuro .caso { border-color: rgba(255,255,255,.12); }
.ec .caso > span { display: block; font-size: 12.5px; color: ${MUTED}; line-height: 1.4; }
.ec.escuro .caso > span { color: rgba(255,255,255,.58); }
.ec .caso b { display: block; font-size: 15px; font-weight: 700; margin-top: 4px; line-height: 1.35; }
.ec.v-topo .conteudo { justify-content: flex-start; }
.ec.v-meio .conteudo { justify-content: center; }
.ec.v-base .conteudo { justify-content: flex-end; }
.ec.al-centro .bloco { text-align: center; }
.ec.al-centro .sub { margin-left: auto; margin-right: auto; }
.ec.al-centro .pilulas { justify-content: center; }
.ec.al-centro .item, .ec.al-centro .valor, .ec.al-centro .caso { text-align: left; }
.ec .centro { text-align: center; }
.ec.al-esquerda .centro { text-align: left; }
.ec.al-esquerda .cta { justify-content: flex-start; }
.ec .centro .sub { margin-left: auto; margin-right: auto; }
.ec .cta { display: flex; justify-content: center; margin-top: 28px; }
.ec .cta > span { display: inline-flex; align-items: center; padding: 13px 30px; background: ${PAPER}; color: ${BRAND_DARK}; font-weight: 700; font-size: 14.5px; border-radius: 28px; white-space: nowrap; }
.ec:not(.escuro) .cta > span { background: ${BRAND}; color: #fff; }
.ec .seta { position: absolute; right: 0; top: 0; bottom: 0; width: 48px; display: flex; align-items: center; justify-content: center;
  color: rgba(0,0,0,.25); background: linear-gradient(to right, transparent, rgba(0,0,0,.06)); }
.ec.escuro .seta { color: rgba(255,255,255,.4); background: linear-gradient(to right, transparent, rgba(255,255,255,.10)); }
.ec .progresso { position: absolute; bottom: 0; left: 0; right: 0; padding: 16px 28px 20px; display: flex; align-items: center; gap: 10px; }
.ec .progresso .trilho { flex: 1; height: 3px; background: rgba(0,0,0,.08); border-radius: 2px; overflow: hidden; }
.ec .progresso .trilho div { height: 100%; background: ${BRAND}; border-radius: 2px; }
.ec.escuro .progresso .trilho { background: rgba(255,255,255,.14); }
.ec.escuro .progresso .trilho div { background: #fff; }
.ec .progresso > span { font-family: ECM; font-size: 11px; color: rgba(0,0,0,.35); font-weight: 500; }
.ec.escuro .progresso > span { color: rgba(255,255,255,.45); }
`;
  }

  window.EstudioMarcas = window.EstudioMarcas || {};
  window.EstudioMarcas.cashb = { base, render, novo, css, avisos, ehCapa, fundo, margem: '.conteudo', nomesIcones: {}, artes: Object.keys(ARTES) };
})();
