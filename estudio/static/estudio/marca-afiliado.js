/* Estúdio Instagram (painel do afiliado): o desenho dos slides.
 * Mesma estrutura do desenho do Appfiliado (marca-appfiliado.js), que o editor conhece: topo, área com
 * o bloco de conteúdo e rodapé. As cores vêm do tema do post (as mesmas do gerador de carrosséis) ou
 * da "Minha marca" do afiliado (Premium), e cada slide calcula o próprio contraste. */
(function () {
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const marcar = (s) => esc(s).replace(/\*([^*]+)\*/g, '<em>$1</em>').replace(/R\$ /g, 'R$$&nbsp;');
  const urlOk = (u) => /^(\/(?!\/)|https:\/\/)[^\s'"()<>\\]*$/.test(u || '');

  // ---- cores ---------------------------------------------------------------------------------
  const hex = (h) => { const n = parseInt(String(h).slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; };
  const mix = (a, b, p) => { const x = hex(a), y = hex(b); return '#' + [0, 1, 2].map((k) => Math.round(x[k] * p + y[k] * (1 - p)).toString(16).padStart(2, '0')).join(''); };
  const rgba = (h, o) => { const [r, g, b] = hex(h); return `rgba(${r},${g},${b},${o})`; };
  const lum = (h) => { const [r, g, b] = hex(h).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const contraste = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const PADRAO = { a: '#1F3A2E', b: '#F6F3EA', acc: '#F2C230', ink: '#1D2A23' };
  const paleta = (cfg, tema) => (cfg.temas || {})[tema] || (cfg.temas || {}).verde || PADRAO;
  const sobre = (fundo, t) => (contraste(fundo, t.ink) >= 4.5 ? t.ink : contraste(fundo, '#FFFFFF') >= contraste(fundo, '#111111') ? '#FFFFFF' : '#111111');
  const gradiente = (a) => `radial-gradient(120% 90% at 88% 6%, ${mix(a, '#FFFFFF', 0.86)} 0%, ${a} 46%, ${mix(a, '#000000', 0.8)} 100%)`;

  // ---- fontes ----------------------------------------------------------------------------------
  const FONTES = {
    moderna: { fam: 'AfDM', peso: 800, k: 1, caixa: 'none', lh: 1.04 },
    geometrica: { fam: 'AfSora', peso: 800, k: 0.86, caixa: 'none', lh: 1.08 },
    impacto: { fam: 'AfBebas', peso: 400, k: 1.3, caixa: 'uppercase', lh: 1.0 },
    elegante: { fam: 'AfPlayfair', peso: 900, k: 0.94, caixa: 'none', lh: 1.06 },
    serifa: { fam: 'AfInstrument', peso: 400, k: 1.22, caixa: 'none', lh: 1.0 },
    suave: { fam: 'AfManrope', peso: 800, k: 0.95, caixa: 'none', lh: 1.06 },
  };
  const fonteDe = (cfg, tema) => FONTES[tema === 'marca' && cfg.marca_afiliado ? cfg.marca_afiliado.fonte : 'moderna'] || FONTES.moderna;

  function base(formato) {
    if (formato === 'story') return { w: 864, h: 1536, escala: 1.25 };
    if (formato === 'retrato') return { w: 1080, h: 1350, escala: 1 };
    return { w: 1080, h: 1080, escala: 1 };
  }

  // ---- fundos ----------------------------------------------------------------------------------
  function arcos(cx, cy, r0, n, passo, cor, larg) {
    let s = ''; for (let i = 0; i < n; i++) s += `<circle cx="${cx}" cy="${cy}" r="${r0 + i * passo}" fill="none" stroke="${cor}" stroke-width="${larg}"/>`; return s;
  }
  const mancha = (cx, cy, r, cor, op) => `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${cor}" opacity="${op}"/>`;
  const ARTES = {
    circulos: (l, a, c) => { const k = Math.min(l, a) / 1080; return `<circle cx="${l - 70 * k}" cy="${a - 90 * k}" r="${450 * k}" fill="none" stroke="${c.linha}" stroke-width="${3 * k}"/><circle cx="${l - 80 * k}" cy="${a - 100 * k}" r="${280 * k}" fill="none" stroke="${c.linha}" stroke-width="${3 * k}"/>`; },
    canto: (l, a, c) => { const k = Math.min(l, a) / 1080; return `<circle cx="${80 * k}" cy="${80 * k}" r="${500 * k}" fill="none" stroke="${c.linha}" stroke-width="${3 * k}"/>` + arcos(l * 0.98, a * 0.95, Math.min(l, a) * 0.16, 3, Math.min(l, a) * 0.05, c.linha, 3 * k); },
    manchas: (l, a, c) => { const m = Math.min(l, a); return mancha(l * 0.04, a * 0.06, m * 0.30, c.mancha, c.op) + mancha(l * 0.98, a * 0.92, m * 0.34, c.mancha, c.op) + arcos(l * 0.97, a * 0.10, m * 0.17, 4, m * 0.024, c.linha, 3); },
    ondas: (l, a, c) => { const m = Math.min(l, a); return arcos(-l * 0.10, a * 1.05, m * 0.28, 7, m * 0.045, c.linha, 3) + arcos(l * 1.10, -a * 0.05, m * 0.28, 7, m * 0.045, c.linha, 3); },
    moldura: (l, a, c) => { const r = Math.min(l, a) * 0.26; return mancha(0, 0, r, c.mancha, c.op) + mancha(l, 0, r * 0.8, c.mancha, c.op) + mancha(0, a, r * 0.85, c.mancha, c.op) + mancha(l, a, r, c.mancha, c.op); },
    halo: (l, a, c) => { const m = Math.min(l, a); return arcos(l * 0.5, a * 0.5, m * 0.30, 6, m * 0.055, c.linha, 3) + mancha(l * 0.5, a * 0.5, m * 0.26, c.mancha, c.op * 0.6); },
  };
  // Devolve o HTML do fundo e a cor "de base" (a que decide o contraste do texto).
  function fundo(f, l, a, t) {
    t = t || PADRAO; f = f || {};
    if (f.modo === 'imagem' && urlOk(f.imagem)) {
      const veu = Math.min(Math.max(+f.veu || 0, 0), 0.85);
      return { base: veu >= 0.3 ? '#151515' : '#F4F4F4', html: `<div class="fundo" style="background:#111 url('${esc(f.imagem)}') center/cover no-repeat"></div>` + (veu ? `<div class="fundo" style="background:rgba(12,12,12,${veu})"></div>` : '') };
    }
    if (f.modo === 'arte' && ARTES[f.arte]) {
      const escuro = f.tom !== 'claro', cor = escuro ? t.a : t.b, linha = sobre(cor, t);
      const c = { linha: rgba(linha, escuro ? 0.12 : 0.10), mancha: escuro ? mix(t.a, '#FFFFFF', 0.82) : mix(t.a, t.b, 0.10), op: escuro ? 0.55 : 0.7 };
      return { base: cor, html: `<div class="fundo" style="background:${escuro ? gradiente(t.a) : t.b}"><svg width="${l}" height="${a}" viewBox="0 0 ${l} ${a}">${ARTES[f.arte](l, a, c)}</svg></div>` };
    }
    const cores = { tema: t.a, claro: t.b, destaque: t.acc, branco: '#FFFFFF', escuro: mix(t.ink, '#000000', 0.85) };
    const nome = cores[f.cor] ? f.cor : 'tema';
    return { base: cores[nome], html: `<div class="fundo" style="background:${nome === 'tema' ? gradiente(t.a) : cores[nome]}"></div>` };
  }
  // Variáveis de cor do slide, a partir da cor de base do fundo.
  function variaveis(baseCor, t, fonte) {
    // "escuro" = o texto é claro (num laranja forte o texto pode ser escuro, e aí o destaque vira marca-texto)
    const fg = sobre(baseCor, t), escuro = lum(fg) > 0.5;
    const pilula = contraste(t.acc, baseCor) >= 1.6 ? t.acc : (escuro ? '#FFFFFF' : t.a);
    const emCor = escuro ? (contraste(t.acc, baseCor) >= 2.6 ? t.acc : fg) : (contraste(t.a, baseCor) >= 3 && contraste(t.acc, baseCor) < 1.6 ? t.a : fg);
    const marcador = !escuro && contraste(t.acc, baseCor) >= 1.25 ? t.acc : 'transparent';
    return [`--fg:${fg}`, `--suave:${escuro ? rgba(fg, 0.78) : mix(fg, baseCor, 0.74)}`, `--linha:${rgba(fg, escuro ? 0.16 : 0.14)}`,
      `--cartao:${escuro ? rgba('#FFFFFF', 0.08) : '#FFFFFF'}`, `--pilula:${pilula}`, `--pilula-fg:${sobre(pilula, t)}`,
      `--em:${emCor}`, `--marcador:${marcador}`, `--a:${t.a}`, `--a-fg:${sobre(t.a, t)}`, `--tf:${fonte.fam}`, `--tw:${fonte.peso}`,
      `--tk:${fonte.k}`, `--tt:${fonte.caixa}`, `--tlh:${fonte.lh}`].join(';');
  }

  // ---- peças -----------------------------------------------------------------------------------
  const arroba = (cfg) => { const a = ((cfg.marca_afiliado || {}).arroba || '').replace(/^@/, ''); return a ? '@' + a : ''; };
  // Topo da capa e da chamada final: o logo (Premium) ou o @. O @ só vai para o topo quando não
  // há rodapé (story ou slide único), para não aparecer duas vezes.
  function marca(cfg, ctx) {
    const m = cfg.marca_afiliado || {};
    if (cfg.premium && m.logo) return `<div class="marca"><img src="${esc(m.logo)}" alt=""></div>`;
    const a = arroba(cfg), semRodape = ctx.formato === 'story' || ctx.total < 2;
    return a && semRodape ? `<div class="marca"><span class="arroba">${esc(a)}</span></div>` : '';
  }
  const seta = '<span class="seta">Arraste <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span>';
  function rodape(ctx, cfg, ultimo) {
    if (ctx.formato === 'story' || ctx.total < 2) return '';
    const esquerda = arroba(cfg) || `${ctx.i + 1}/${ctx.total}`;
    return `<div class="rodape" data-decor><span class="pagina">${esc(esquerda)}</span>${ultimo ? '<span>Salve para ver depois</span>' : seta}</div>`;
  }
  const p = (txt, cls) => txt ? `<p class="${cls || 'texto'}">${marcar(txt)}</p>` : '';
  const chapeu = (s) => s.chapeu ? `<p class="chapeu">${esc(s.chapeu)}</p>` : '';
  const foto = (s, cls, extra) => urlOk(s.foto) ? `<div class="foto ${cls || ''}${s.sem_fundo ? ' sem-fundo' : ''}"><div class="foto-img" style="background-image:url('${esc(s.foto)}')"></div>${extra || ''}</div>` : '';
  const desconto = (s) => s.desconto ? `<span class="desconto">${esc(s.desconto)}</span>` : '';

  const TIPOS = {
    capa(s, ctx, cfg) {
      const topo = marca(cfg, ctx) ? `<div class="topo">${marca(cfg, ctx)}</div>` : '';
      const comFoto = urlOk(s.foto);
      return { topo, pe: rodape(ctx, cfg), extra: comFoto ? 'com-foto' : '',
        bloco: `${foto(s, 'foto-capa', desconto(s))}${chapeu(s)}<h1>${marcar(s.titulo)}</h1>${p(s.texto)}${!comFoto && s.desconto ? `<div class="selos">${desconto(s)}</div>` : ''}` };
    },
    produto(s, ctx, cfg) {
      const selo = s.selo ? `<span class="selo-foto">${esc(s.selo)}</span>` : '';
      return { topo: '', pe: rodape(ctx, cfg), bloco: `${chapeu(s)}<h2>${marcar(s.titulo)}</h2>${foto(s, 'foto-produto', selo)}${p(s.texto)}` };
    },
    preco(s, ctx, cfg) {
      return { topo: '', pe: rodape(ctx, cfg), bloco: `${chapeu(s)}<h2>${marcar(s.titulo)}</h2><div class="preco-caixa">`
        + `${s.de ? `<p class="de">de <s>${marcar(s.de)}</s></p>` : ''}<p class="por">${s.de ? '<span>por</span>' : ''}${marcar(s.preco)}</p>${desconto(s)}</div>${p(s.nota, 'texto nota')}` };
    },
    lista(s, ctx, cfg) {
      const itens = (s.itens || []).map((it, k) => {
        const m = s.numerada ? `<span class="n">${k + 1}</span>` : '<span class="ok"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></span>';
        return `<li>${m}<div><b>${esc(it.titulo)}</b>${it.texto ? `<span>${esc(it.texto)}</span>` : ''}</div></li>`;
      }).join('');
      return { topo: '', pe: rodape(ctx, cfg), bloco: `${chapeu(s)}<h2>${marcar(s.titulo)}</h2>${p(s.texto)}<ul class="lista${(s.itens || []).length <= 3 ? ' folgada' : ''}">${itens}</ul>` };
    },
    texto(s, ctx, cfg) {
      return { topo: '', pe: rodape(ctx, cfg), bloco: `${chapeu(s)}<h2>${marcar(s.titulo)}</h2>${p(s.texto)}${s.destaque ? `<div class="caixa-destaque">${marcar(s.destaque)}</div>` : ''}` };
    },
    cupom(s, ctx, cfg) {
      return { topo: '', pe: rodape(ctx, cfg), bloco: `${chapeu(s)}<h2>${marcar(s.titulo)}</h2>`
        + `<div class="cupom"><small>Código</small><b>${esc(s.codigo || 'CUPOM')}</b></div>${p(s.texto)}${p(s.nota, 'texto nota')}` };
    },
    cta(s, ctx, cfg) {
      const topo = marca(cfg, ctx) ? `<div class="topo">${marca(cfg, ctx)}</div>` : '';
      return { topo, pe: rodape(ctx, cfg, true),
        bloco: `<h1 class="menor">${marcar(s.titulo)}</h1>${p(s.texto)}${s.botao ? `<div class="selos"><span class="selo">${esc(s.botao)} ↗</span></div>` : ''}` };
    },
  };

  const ehCapa = (s, ctx) => ctx.formato !== 'story' && (s.capa === true || (s.capa === undefined && ctx.i === 0));

  function render(s, ctx, cfg) {
    const b = base(ctx.formato), t = paleta(cfg, ctx.tema), f = fundo(s.fundo, b.w, b.h, t);
    const tipo = TIPOS[s.tipo] ? s.tipo : 'capa';
    // a arte "halo" tem os círculos no meio: o texto vai para o centro dela, a não ser que a pessoa escolha outro lugar
    const halo = s.fundo && s.fundo.modo === 'arte' && s.fundo.arte === 'halo';
    const a = Object.assign(halo ? { alinhar: 'centro', posicao: 'meio' } : {}, s.ajustes || {});
    const partes = TIPOS[tipo](s, ctx, cfg, b);
    const cls = ['af', 'slide', `t-${tipo}`, `f-${ctx.formato}`, lum(sobre(f.base, t)) > 0.5 ? 'escuro' : '', ctx.formato === 'story' ? 'story' : '', partes.extra || '',
      ehCapa(s, ctx) ? 'capa-grade' : '', a.posicao ? `v-${a.posicao}` : '', a.alinhar ? `al-${a.alinhar}` : ''].filter(Boolean).join(' ');
    return `<section class="${cls}" style="width:${b.w}px;height:${b.h}px;${variaveis(f.base, t, fonteDe(cfg, ctx.tema))}">${f.html}${partes.topo}<div class="area"><div class="bloco b-${tipo}">${partes.bloco}</div></div>${partes.pe}</section>`;
  }

  function novo(tipo) {
    const c = (cor) => ({ modo: 'cor', cor });
    return ({
      capa: { tipo, chapeu: 'Achado do dia', titulo: 'O achado que *resolve* o seu dia', texto: '', foto: '', desconto: '', fundo: c('tema') },
      produto: { tipo, chapeu: 'Por que vale a pena', titulo: 'O que ele tem de bom', texto: 'Um texto curto sobre o produto.', foto: '', selo: '', fundo: c('claro') },
      preco: { tipo, chapeu: 'Preço de hoje', titulo: 'Quanto está agora', de: '', preco: 'R$ 0,00', desconto: '', nota: 'Preço visto hoje. Pode mudar a qualquer momento.', fundo: c('tema') },
      lista: { tipo, chapeu: 'Achados', titulo: 'Título da lista', texto: '', numerada: true, itens: [{ titulo: 'Primeiro item', texto: 'Explicação curta.' }, { titulo: 'Segundo item', texto: 'Explicação curta.' }], fundo: c('claro') },
      texto: { tipo, chapeu: 'Dica', titulo: 'Título da dica', texto: 'Um texto curto que explica a ideia.', destaque: '', fundo: c('claro') },
      cupom: { tipo, chapeu: 'Cupom', titulo: 'Cupom de desconto na Shopee', codigo: 'CUPOM10', texto: 'Use no carrinho antes de pagar.', nota: 'Vale enquanto durar.', fundo: c('destaque') },
      cta: { tipo, titulo: 'Gostou? O link está *na bio.*', texto: 'Salve este post para não perder.', botao: 'Link na bio', fundo: { modo: 'arte', arte: 'canto', tom: 'escuro' } },
    })[tipo];
  }

  // Valores do produto da Shopee nos slides de um modelo (foto, preço e desconto).
  const brl = (v) => 'R$ ' + Number(v || 0).toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  function comProduto(slides, produto) {
    if (!produto || !produto.nome) return slides;
    const desc = produto.desconto ? `-${produto.desconto}%` : '';
    slides.forEach((s) => {
      if ((s.tipo === 'capa' || s.tipo === 'produto') && !s.foto && produto.imagem) s.foto = produto.imagem;
      if (s.tipo === 'capa' && s.desconto !== undefined) s.desconto = desc;
      if (s.tipo === 'preco') { s.preco = brl(produto.preco); s.de = produto.de ? brl(produto.de) : ''; s.desconto = desc; }
    });
    return slides;
  }

  function avisos(s) {
    if (s.tipo === 'produto' && !urlOk(s.foto)) return ['Este slide está sem foto. Escolha a foto do produto no campo "Foto".'];
    return [];
  }
  // A amostra de cor dos botões de fundo, no tema do post.
  function amostra(cor, tema, cfg) {
    const t = paleta(cfg, tema);
    return ({ tema: gradiente(t.a), claro: t.b, destaque: t.acc, branco: '#FFFFFF', escuro: mix(t.ink, '#000000', 0.85) })[cor] || t.a;
  }

  function css(cfg) {
    const F = cfg.fontes;
    return `
@font-face { font-family: AfDM; font-weight: 500; src: url(${F.dm500}); }
@font-face { font-family: AfDM; font-weight: 800; src: url(${F.dm800}); }
@font-face { font-family: AfSora; font-weight: 800; src: url(${F.sora}); }
@font-face { font-family: AfBebas; font-weight: 400; src: url(${F.bebas}); }
@font-face { font-family: AfPlayfair; font-weight: 900; src: url(${F.playfair}); }
@font-face { font-family: AfInstrument; font-weight: 400; src: url(${F.instrument}); }
@font-face { font-family: AfManrope; font-weight: 800; src: url(${F.manrope}); }
@font-face { font-family: AfMono; font-weight: 700; src: url(${F.mono}); }
.af, .af * { box-sizing: border-box; margin: 0; padding: 0; }
.af { font-family: AfDM, sans-serif; font-weight: 500; color: var(--fg); position: relative; overflow: hidden; display: flex; flex-direction: column;
  padding: 72px 84px 64px; -webkit-font-smoothing: antialiased; text-align: left; line-height: normal; }
.af > * { position: relative; }
.af > .fundo { position: absolute; inset: 0; }
.af > .fundo svg { position: absolute; inset: 0; display: block; }
.af.f-quadrado.capa-grade { padding-left: 200px; padding-right: 200px; }
.af.f-retrato.capa-grade { padding: 175px 200px; }
.af .topo { display: flex; justify-content: space-between; align-items: center; flex: none; }
.af .area { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.af .bloco { position: relative; }
.af .b-capa, .af .b-cta { margin: auto 0; }
.af .b-capa { padding-bottom: 30px; }
.af .b-produto { flex: 1; min-height: 0; display: flex; flex-direction: column; padding: 10px 0 34px; }
.af .b-lista { flex: 1; display: flex; flex-direction: column; padding-bottom: 40px; }
.af .b-preco, .af .b-texto, .af .b-cupom { margin: auto 0; padding-bottom: 30px; }
.af.v-topo .bloco { flex: none; margin: 0 0 auto; }
.af.v-meio .bloco { flex: none; margin: auto 0; }
.af.v-base .bloco { flex: none; margin: auto 0 0; }
.af.v-topo .topo + .area .bloco { margin-top: 40px; }
.af.al-centro .bloco { text-align: center; }
.af.al-centro .selos, .af.al-centro .preco-caixa { justify-content: center; }
.af.al-centro .texto, .af.al-centro .cupom { margin-left: auto; margin-right: auto; }
.af.al-centro .lista li { text-align: left; }
.af .marca { display: flex; align-items: center; }
.af .marca img { height: 84px; max-width: 360px; object-fit: contain; display: block; }
.af .arroba { font-weight: 800; font-size: 30px; letter-spacing: -.01em; border: 2px solid var(--linha); border-radius: 999px; padding: 10px 26px; }
.af .chapeu { font-size: 26px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; color: var(--em); }
.af h1, .af h2 { font-family: var(--tf), AfDM, sans-serif; font-weight: var(--tw); text-transform: var(--tt); line-height: var(--tlh); }
.af h1 { letter-spacing: -.03em; font-size: calc(80px * var(--tk)); margin-top: 18px; }
.af.capa-grade h1 { font-size: calc(70px * var(--tk)); }
.af.com-foto h1 { font-size: calc(62px * var(--tk)); }
.af.capa-grade.com-foto h1 { font-size: calc(54px * var(--tk)); }
.af h1.menor { font-size: calc(66px * var(--tk)); line-height: calc(var(--tlh) + .03); }
.af h2 { letter-spacing: -.025em; font-size: calc(54px * var(--tk)); margin-top: 14px; }
.af em { font-style: normal; color: var(--em); background: linear-gradient(transparent 60%, var(--marcador) 60%, var(--marcador) 92%, transparent 92%); }
.af .texto { font-size: 32px; line-height: 1.36; color: var(--suave); margin-top: 20px; max-width: 900px; }
.af .texto.nota { font-size: 27px; margin-top: 22px; }
.af .rodape { flex: none; display: flex; align-items: center; justify-content: space-between; font-size: 28px; font-weight: 800; }
.af .rodape .pagina { opacity: .7; }
.af .seta { display: inline-flex; align-items: center; gap: 12px; }
.af .selos { display: flex; gap: 18px; margin-top: 40px; flex-wrap: wrap; }
.af .selo { display: inline-flex; align-items: center; gap: 12px; background: var(--pilula); color: var(--pilula-fg); font-weight: 800; border-radius: 999px; padding: 18px 36px; font-size: 34px; }
.af .foto { position: relative; background: #FFFFFF; border-radius: 36px; box-shadow: 0 24px 60px rgba(0,0,0,.16); overflow: visible; }
.af .foto-img { position: absolute; inset: 18px; background: center/contain no-repeat; border-radius: 22px; }
/* a foto da Shopee é quadrada: na capa, o cartão também é */
/* produto solto (foto sem fundo): sem o cartão, com sombra no próprio produto */
.af .foto.sem-fundo { background: none; box-shadow: none; }
.af .foto.sem-fundo .foto-img { inset: 0; border-radius: 0; filter: drop-shadow(0 26px 26px rgba(0,0,0,.28)); }
.af .foto.sem-fundo .desconto { right: 0; top: 0; }
.af .foto-capa { --lado: 560px; width: min(100%, var(--lado)); height: var(--lado); margin-bottom: 34px; }
.af.f-quadrado .foto-capa { --lado: 420px; }
.af.capa-grade .foto-capa { --lado: 470px; }
.af.f-quadrado.capa-grade .foto-capa { --lado: 380px; }
.af.al-centro .foto-capa { margin-left: auto; margin-right: auto; }
.af .foto-produto { flex: 1; min-height: 300px; margin: 34px 0 6px; }
.af .desconto { position: absolute; right: -18px; top: -18px; background: var(--pilula); color: var(--pilula-fg); font-weight: 800; font-size: 40px;
  border-radius: 999px; padding: 18px 26px; box-shadow: 0 10px 24px rgba(0,0,0,.18); letter-spacing: -.01em; }
.af .selos .desconto, .af .preco-caixa .desconto { position: static; box-shadow: none; }
.af .selo-foto { position: absolute; left: 24px; bottom: 24px; background: var(--a); color: var(--a-fg); font-weight: 800; font-size: 28px; border-radius: 999px; padding: 12px 24px; }
.af .preco-caixa { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 26px; margin-top: 40px; }
.af .preco-caixa .de { width: 100%; font-size: 40px; color: var(--suave); }
.af .preco-caixa .de s { text-decoration-thickness: 4px; }
.af .preco-caixa .por { font-family: var(--tf), AfDM, sans-serif; font-weight: var(--tw); font-size: calc(132px * var(--tk)); letter-spacing: -.04em; line-height: 1; white-space: nowrap; }
.af .preco-caixa .por span { display: block; font-family: AfDM, sans-serif; font-weight: 800; font-size: 30px; letter-spacing: .14em; text-transform: uppercase; color: var(--em); margin-bottom: 8px; }
.af .preco-caixa .desconto { font-size: 44px; padding: 16px 28px; }
.af .caixa-destaque { margin-top: 36px; border-left: 10px solid var(--pilula); background: var(--cartao); border-radius: 0 26px 26px 0; padding: 28px 32px; font-size: 34px; line-height: 1.35; font-weight: 800; }
.af .cupom { margin-top: 40px; border: 5px dashed var(--fg); border-radius: 30px; padding: 30px 40px; display: inline-flex; flex-direction: column; gap: 6px; max-width: 100%; }
.af .cupom small { font-size: 26px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; opacity: .8; }
.af .cupom b { font-family: AfMono, monospace; font-weight: 700; font-size: 84px; letter-spacing: .04em; line-height: 1.05; word-break: break-all; }
.af .lista { list-style: none; display: grid; gap: 16px; margin: auto 0; padding-top: 28px; }
.af .lista li { display: flex; gap: 24px; align-items: flex-start; background: var(--cartao); border: 2px solid var(--linha); border-radius: 28px; padding: 22px 30px; }
.af .lista .n { flex: none; width: 56px; height: 56px; border-radius: 50%; background: var(--pilula); color: var(--pilula-fg); font-weight: 800; font-size: 30px; display: grid; place-items: center; }
.af .lista .ok { flex: none; width: 52px; height: 52px; border-radius: 50%; background: var(--pilula); display: grid; place-items: center; margin-top: 4px; }
.af .lista .ok svg { width: 30px; height: 30px; fill: none; stroke: var(--pilula-fg); stroke-width: 3.2; stroke-linecap: round; stroke-linejoin: round; }
.af .lista b { display: block; font-size: 36px; font-weight: 800; letter-spacing: -.01em; line-height: 1.15; }
.af .lista div > span { display: block; font-size: 29px; line-height: 1.32; color: var(--suave); margin-top: 6px; }
.af .lista.folgada { gap: 22px; }
.af .lista.folgada li { padding: 30px 34px; }
.af .lista.folgada b { font-size: 40px; }
.af .lista.folgada div > span { font-size: 31px; }
/* stories: desenhados em 864x1536 e ampliados 1,25x; 200 px aqui = 250 px na imagem */
.af.story { justify-content: center; padding: 200px 56px 240px; }
.af.story .b-produto { flex: none; margin: auto 0; }
.af.story .foto-capa { --lado: 600px; }
.af.story .foto-produto { flex: none; width: 100%; height: auto; aspect-ratio: 1; min-height: 0; }
.af.story h1 { font-size: calc(88px * var(--tk)); }
.af.story.com-foto h1 { font-size: calc(68px * var(--tk)); }
.af.story h1.menor { font-size: calc(72px * var(--tk)); }
.af.story h2 { font-size: calc(60px * var(--tk)); }
.af.story .texto { font-size: 35px; }
.af.story .b-lista { flex: none; margin: auto 0; }
.af.story .lista { gap: 22px; padding-top: 36px; margin: 0; }
.af.story .lista li { padding: 32px 34px; border-radius: 32px; }
.af.story .preco-caixa .por { font-size: calc(120px * var(--tk)); }
`;
  }

  window.EstudioMarcas = window.EstudioMarcas || {};
  window.EstudioMarcas.afiliado = { base, render, novo, css, ehCapa, fundo, margem: null, nomesIcones: {},
    artes: Object.keys(ARTES), avisos, amostra, comProduto, paleta };
})();
