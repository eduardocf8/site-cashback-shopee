/* Estúdio de posts: o desenho dos slides do Appfiliado.
 * Mesmo visual das artes de marketing/appfiliado/instagram/gerar_instagram.py (cores, DM Sans,
 * tamanhos), em HTML que o navegador transforma em PNG. O post do feed é desenhado no tamanho
 * final; o story é desenhado em 864x1536 e ampliado 1,25x, como no gerador original. */
(function () {
  const VERDE = '#1F3A2E', VERDE_2 = '#2D4B3D', VERDE_3 = '#17301F', CREME = '#F6F3EA', AMARELO = '#F2C230', TINTA = '#1D2A23', SUAVE = '#AFC1B5';
  const SIMBOLO = '<svg viewBox="3 8.25 36 36"><g fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"><circle cx="21" cy="26" r="9.5"/><path d="M30.5 16.5V36"/></g><circle cx="21" cy="26" r="3.6" fill="currentColor"/></svg>';
  const ICONES = {
    bot: 'M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z',
    site: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18',
    carrosseis: 'M7 5h10v14H7zM3 7v10M21 7v10',
    notas: 'M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7',
    radar: 'M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5M12 12l6-6M17 3v4h4',
    conversor: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
    resultados: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
    chave: 'M15 7a4 4 0 1 1-3.9 4.9L4 19v2h3v-2h2v-2h2l1.1-1.1A4 4 0 0 1 15 7zM16 9.5h.01',
    duvidas: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17h.01',
    planos: 'M4 7h16v12H4zM4 11h16M8 15h3',
    sobre: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v6M12 7.5h.01',
  };
  const NOMES_ICONES = { bot: 'Bot', site: 'Site', carrosseis: 'Carrosséis', notas: 'Notas', radar: 'Radar', conversor: 'Conversor',
    resultados: 'Resultados', chave: 'Chave', duvidas: 'Dúvidas', planos: 'Planos', sobre: 'Sobre' };
  const CORES = { verde: null, creme: CREME, amarelo: AMARELO, branco: '#FFFFFF', areia: '#E9E2D3' };
  const GRADIENTE = `radial-gradient(120% 90% at 88% 6%, ${VERDE_2} 0%, ${VERDE} 46%, ${VERDE_3} 100%)`;

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  // *trecho* vira destaque; "R$ 19,90" não quebra no espaço; e-mail não quebra no hífen
  const marcar = (s) => esc(s).replace(/\*([^*]+)\*/g, '<em>$1</em>').replace(/R\$ /g, 'R$$&nbsp;').replace(/e-mail/g, 'e&#8209;mail');

  function base(formato) {
    if (formato === 'story') return { w: 864, h: 1536, escala: 1.25 };
    if (formato === 'retrato') return { w: 1080, h: 1350, escala: 1 };
    return { w: 1080, h: 1080, escala: 1 };
  }

  // ---- fundos ------------------------------------------------------------------------------
  function arcos(cx, cy, r0, n, passo, cor, larg) {
    let s = ''; for (let i = 0; i < n; i++) s += `<circle cx="${cx}" cy="${cy}" r="${r0 + i * passo}" fill="none" stroke="${cor}" stroke-width="${larg}"/>`; return s;
  }
  const mancha = (cx, cy, r, cor, op) => `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${cor}" opacity="${op}"/>`;
  const ARTES = {
    // os dois círculos finos das capas (gerar_instagram.capa)
    circulos: (l, a, c) => { const k = Math.min(l, a) / 1080; return `<circle cx="${l - 70 * k}" cy="${a - 90 * k}" r="${450 * k}" fill="none" stroke="${c.linha}" stroke-width="${3 * k}"/><circle cx="${l - 80 * k}" cy="${a - 100 * k}" r="${280 * k}" fill="none" stroke="${c.linha}" stroke-width="${3 * k}"/>`; },
    // o círculo grande da chamada final (gerar_instagram.cta)
    canto: (l, a, c) => { const k = Math.min(l, a) / 1080; return `<circle cx="${80 * k}" cy="${80 * k}" r="${500 * k}" fill="none" stroke="${c.linha}" stroke-width="${3 * k}"/>` + arcos(l * 0.98, a * 0.95, Math.min(l, a) * 0.16, 3, Math.min(l, a) * 0.05, c.linha, 3 * k); },
    manchas: (l, a, c) => { const m = Math.min(l, a); return mancha(l * 0.04, a * 0.06, m * 0.30, c.mancha, c.op) + mancha(l * 0.98, a * 0.92, m * 0.34, c.mancha, c.op) + arcos(l * 0.97, a * 0.10, m * 0.17, 4, m * 0.024, c.linha, 3); },
    ondas: (l, a, c) => { const m = Math.min(l, a); return arcos(-l * 0.10, a * 1.05, m * 0.28, 7, m * 0.045, c.linha, 3) + arcos(l * 1.10, -a * 0.05, m * 0.28, 7, m * 0.045, c.linha, 3); },
    moldura: (l, a, c) => { const r = Math.min(l, a) * 0.26; return mancha(0, 0, r, c.mancha, c.op) + mancha(l, 0, r * 0.8, c.mancha, c.op) + mancha(0, a, r * 0.85, c.mancha, c.op) + mancha(l, a, r, c.mancha, c.op); },
    halo: (l, a, c) => { const m = Math.min(l, a); return arcos(l * 0.5, a * 0.5, m * 0.30, 6, m * 0.055, c.linha, 3) + mancha(l * 0.5, a * 0.5, m * 0.26, c.mancha, c.op * 0.6); },
  };
  function fundo(f, l, a) {
    f = f || {};
    if (f.modo === 'imagem' && f.imagem) {
      const veu = Math.min(Math.max(+f.veu || 0, 0), 0.85);
      return { escuro: veu >= 0.3, html: `<div class="fundo" style="background:#111 url('${esc(f.imagem)}') center/cover no-repeat"></div>` + (veu ? `<div class="fundo" style="background:rgba(15,25,19,${veu})"></div>` : '') };
    }
    if (f.modo === 'arte' && ARTES[f.arte]) {
      const escuro = f.tom !== 'claro';
      const c = escuro ? { linha: 'rgba(246,243,234,.10)', mancha: VERDE_2, op: 0.55 } : { linha: 'rgba(31,58,46,.10)', mancha: '#E6DFC9', op: 0.75 };
      return { escuro, html: `<div class="fundo" style="background:${escuro ? GRADIENTE : CREME}"><svg width="${l}" height="${a}" viewBox="0 0 ${l} ${a}">${ARTES[f.arte](l, a, c)}</svg></div>` };
    }
    const cor = CORES[f.cor] !== undefined ? f.cor : 'verde';
    return { escuro: cor === 'verde', html: `<div class="fundo" style="background:${cor === 'verde' ? GRADIENTE : CORES[cor]}"></div>` };
  }

  // ---- peças -------------------------------------------------------------------------------
  const marca = () => `<div class="marca"><span class="ic">${SIMBOLO}</span>Appfiliado</div>`;
  const icone = (nome) => ICONES[nome] ? `<div class="icone-grande"><svg viewBox="0 0 24 24"><path d="${ICONES[nome]}"/></svg></div>` : '';
  const seta = '<span class="seta">Arraste <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span>';
  function rodape(ctx, ultimo) {
    if (ctx.formato === 'story' || ctx.total < 2) return '';
    return `<div class="rodape" data-decor><span class="pagina">${ctx.i + 1}/${ctx.total}</span>${ultimo ? '<span>Salve para ver depois</span>' : seta}</div>`;
  }
  const p = (txt, cls) => txt ? `<p class="${cls || 'texto'}">${marcar(txt)}</p>` : '';
  const chapeu = (s) => s.chapeu ? `<p class="chapeu">${esc(s.chapeu)}</p>` : '';

  // Cada tipo devolve {topo, bloco, pe}: o bloco é o conteúdo que a "posição do texto" move.
  const TIPOS = {
    capa(s, ctx) {
      const topo = `<div class="topo">${s.logo === false ? '<span></span>' : marca()}${icone(s.icone)}</div>`;
      return { topo, bloco: `${chapeu(s)}<h1>${marcar(s.titulo)}</h1>${p(s.texto)}`, pe: rodape(ctx) };
    },
    tela(s, ctx, cfg, b) {
      const largura = ctx.formato === 'story' ? 640 : 620;
      const pr = (cfg.prints || {})[s.print] || { url: '', w: 840 };
      const contador = ctx.formato !== 'story' && ctx.total > 1 ? `<span class="chapeu contador" data-decor>${ctx.i + 1}/${ctx.total} →</span>` : '';
      return { topo: '', pe: '', bloco: `<div class="linha-topo">${chapeu(s)}${contador}</div><h2>${marcar(s.titulo)}</h2>${p(s.texto)}`
        + `<div class="celular" style="--cw:${largura}px"><div class="tela" style="height:${b.h}px"><div style="background-image:url('${esc(pr.url)}');background-position:0 -${Math.round((+s.recorte || 0) * (largura - 36) / pr.w)}px"></div></div></div>` };
    },
    lista(s, ctx) {
      const itens = (s.itens || []).map((it, k) => {
        const m = s.numerada ? `<span class="n">${k + 1}</span>` : '<span class="ok"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></span>';
        return `<li>${m}<div><b>${esc(it.titulo)}${it.premium ? '<em class="premium">Premium</em>' : ''}</b>${it.texto ? `<span>${esc(it.texto)}</span>` : ''}</div></li>`;
      }).join('');
      return { topo: '', pe: rodape(ctx), bloco: `${chapeu(s)}<h2>${marcar(s.titulo)}</h2>${p(s.texto)}<ul class="lista${(s.itens || []).length <= 4 ? ' folgada' : ''}">${itens}</ul>` };
    },
    numeros(s, ctx) {
      const cel = (s.pares || []).map((x) => `<div><b>${esc(x.valor)}</b><span>${esc(x.legenda)}</span></div>`).join('');
      return { topo: '', pe: rodape(ctx), bloco: `${chapeu(s)}<h2>${marcar(s.titulo)}</h2><div class="numeros">${cel}</div>` };
    },
    precos(s, ctx) {
      const cel = (s.linhas || []).map((x) => `<div><span>${esc(x.rotulo)}${x.detalhe ? `<br><small>${esc(x.detalhe)}</small>` : ''}</span><b>${marcar(x.valor)}</b></div>`).join('');
      return { topo: '', pe: rodape(ctx), bloco: `${chapeu(s)}<h2>${marcar(s.titulo)}</h2><div class="precos">${cel}</div>${p(s.nota, 'texto nota')}` };
    },
    cta(s, ctx) {
      const selos = (s.botao ? `<span class="selo">${esc(s.botao)} ↗</span>` : '') + (s.site ? `<span class="selo claro">${esc(s.site)}</span>` : '');
      return { topo: s.logo === false ? '' : `<div class="topo">${marca()}</div>`, pe: rodape(ctx, true),
        bloco: `<h1 class="menor">${marcar(s.titulo)}</h1>${p(s.texto)}${selos ? `<div class="selos">${selos}</div>` : ''}` };
    },
    conversa(s, ctx) {
      const b = (s.baloes || []).map((x) => `<div class="balao${x.meu ? ' meu' : ''}">${marcar(x.texto)}</div>`).join('');
      return { topo: '', pe: rodape(ctx), bloco: `${chapeu(s)}<h2>${marcar(s.titulo)}</h2><div class="baloes">${b}</div>` };
    },
  };

  // O slide usa as margens da capa (que cabem no recorte 3:4 da grade do perfil) quando foi
  // marcado como capa; sem marcação, só o primeiro slide do feed é capa.
  const ehCapa = (s, ctx) => ctx.formato !== 'story' && (s.capa === true || (s.capa === undefined && ctx.i === 0));

  function render(s, ctx, cfg) {
    const b = base(ctx.formato), f = fundo(s.fundo, b.w, b.h);
    const tipo = TIPOS[s.tipo] ? s.tipo : 'capa', a = s.ajustes || {};
    const partes = TIPOS[tipo](s, ctx, cfg, b);
    const cls = ['ea', 'slide', `t-${tipo}`, `f-${ctx.formato}`, f.escuro ? 'escuro' : '', ctx.formato === 'story' ? 'story' : '',
      ehCapa(s, ctx) ? 'capa-grade' : '', a.posicao ? `v-${a.posicao}` : '', a.alinhar ? `al-${a.alinhar}` : ''].filter(Boolean).join(' ');
    return `<section class="${cls}" style="width:${b.w}px;height:${b.h}px">${f.html}${partes.topo}<div class="area"><div class="bloco b-${tipo}">${partes.bloco}</div></div>${partes.pe}</section>`;
  }

  function novo(tipo) {
    const f = (cor) => ({ modo: 'cor', cor });
    return ({
      capa: { tipo, chapeu: 'Para afiliados da Shopee', titulo: 'Seu título com *destaque.*', texto: 'Um texto curto que explica a ideia.', icone: '', logo: true, fundo: { modo: 'arte', arte: 'circulos', tom: 'escuro' } },
      tela: { tipo, chapeu: 'Bot de WhatsApp', titulo: 'Título sobre a tela', texto: 'O que a pessoa vê nessa tela.', print: 'bot-ofertas', recorte: 0, fundo: f('creme') },
      lista: { tipo, chapeu: 'Chapéu', titulo: 'Título da lista', texto: '', numerada: false, itens: [{ titulo: 'Primeiro item', texto: 'Explicação curta.' }, { titulo: 'Segundo item', texto: 'Explicação curta.' }], fundo: f('creme') },
      numeros: { tipo, chapeu: 'Em números', titulo: 'Título', pares: [{ valor: '10', legenda: 'legenda' }, { valor: '30 mil', legenda: 'legenda' }], fundo: f('verde') },
      precos: { tipo, chapeu: 'Planos', titulo: 'Título', linhas: [{ rotulo: 'Plano', valor: 'R$ 19,90', detalhe: '' }], nota: '', fundo: f('verde') },
      cta: { tipo, titulo: 'Comece hoje a partir de *R$ 19,90/mês.*', texto: 'Uma frase que convida a clicar.', botao: 'Link na bio', site: 'appfiliado.com.br', logo: true, fundo: { modo: 'arte', arte: 'canto', tom: 'escuro' } },
      conversa: { tipo, chapeu: 'Dúvidas', titulo: 'A pergunta?', baloes: [{ texto: 'A pergunta da pessoa?', meu: true }, { texto: 'A resposta do Appfiliado.', meu: false }], fundo: f('areia') },
    })[tipo];
  }

  function css(cfg) {
    const F = cfg.fontes;
    return `
@font-face { font-family: EDM; font-weight: 500; src: url(${F.dm500}); }
@font-face { font-family: EDM; font-weight: 800; src: url(${F.dm800}); }
.ea, .ea * { box-sizing: border-box; margin: 0; padding: 0; }
.ea { font-family: EDM, sans-serif; font-weight: 500; color: ${TINTA}; position: relative; overflow: hidden; display: flex; flex-direction: column;
  padding: 72px 84px 64px; -webkit-font-smoothing: antialiased; text-align: left; line-height: normal; }
.ea > * { position: relative; }
.ea > .fundo { position: absolute; inset: 0; }
.ea > .fundo svg { position: absolute; inset: 0; display: block; }
.ea.f-quadrado.capa-grade { padding-left: 200px; padding-right: 200px; }
.ea.f-retrato.capa-grade { padding: 175px 200px; }
.ea.escuro { color: ${CREME}; }
.ea .topo { display: flex; justify-content: space-between; align-items: flex-start; }
.ea .linha-topo { display: flex; justify-content: space-between; align-items: center; }
.ea .area { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.ea .bloco { position: relative; }
.ea .b-capa { margin: auto 0; padding-bottom: 70px; }
.ea .b-cta { margin: auto 0; }
.ea .b-lista, .ea .b-numeros { flex: 1; display: flex; flex-direction: column; padding-bottom: 40px; }
.ea .b-precos, .ea .b-conversa { padding-bottom: 40px; }
.ea.v-topo .bloco { flex: none; margin: 0 0 auto; }
.ea.v-meio .bloco { flex: none; margin: auto 0; }
.ea.v-base .bloco { flex: none; margin: auto 0 0; }
.ea.v-topo .topo + .area .bloco { margin-top: 40px; }
.ea.v-topo .lista, .ea.v-meio .lista, .ea.v-base .lista, .ea.v-topo .numeros, .ea.v-meio .numeros, .ea.v-base .numeros { margin: 28px 0 0; }
.ea.al-centro .bloco { text-align: center; }
.ea.al-centro .selos { justify-content: center; }
.ea.al-centro .texto { margin-left: auto; margin-right: auto; }
.ea.al-centro .lista li { text-align: left; }
.ea.al-centro .linha-topo { justify-content: center; }
.ea .marca { display: flex; align-items: center; gap: 16px; font-weight: 800; font-size: 34px; letter-spacing: -.01em; }
.ea .marca .ic { width: 64px; height: 64px; border-radius: 18px; background: ${AMARELO}; color: ${VERDE}; display: grid; place-items: center; }
.ea .marca .ic svg { width: 46px; height: 46px; }
.ea .chapeu { font-size: 26px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; color: #8A6A00; }
.ea.escuro .chapeu { color: ${AMARELO}; }
.ea .contador { color: inherit; opacity: .45; letter-spacing: .04em; }
.ea h1 { font-weight: 800; letter-spacing: -.03em; line-height: 1.03; font-size: 80px; margin-top: 20px; }
.ea.capa-grade h1 { font-size: 74px; }
.ea h1.menor { font-size: 66px; line-height: 1.07; }
.ea h2 { font-weight: 800; letter-spacing: -.025em; line-height: 1.07; font-size: 54px; margin-top: 16px; }
.ea em { font-style: normal; background: linear-gradient(transparent 58%, ${AMARELO} 58%, ${AMARELO} 92%, transparent 92%); }
.ea.escuro em { background: none; color: ${AMARELO}; }
.ea .texto { font-size: 32px; line-height: 1.36; color: #4E5C53; margin-top: 22px; max-width: 900px; }
.ea .texto.nota { font-size: 29px; margin-top: 24px; }
.ea.escuro .texto { color: ${SUAVE}; }
.ea .rodape { flex: none; display: flex; align-items: center; justify-content: space-between; font-size: 28px; font-weight: 800; }
.ea .rodape .pagina { opacity: .55; }
.ea .seta { display: inline-flex; align-items: center; gap: 12px; }
.ea .selos { display: flex; gap: 18px; margin-top: 46px; flex-wrap: wrap; }
.ea .selo { display: inline-flex; align-items: center; gap: 12px; background: ${AMARELO}; color: ${VERDE}; font-weight: 800; border-radius: 999px; padding: 18px 34px; font-size: 32px; }
.ea .selo.claro { background: rgba(246,243,234,.12); color: ${CREME}; border: 2px solid rgba(246,243,234,.25); }
.ea:not(.escuro) .selo.claro { background: rgba(31,58,46,.08); color: ${VERDE}; border-color: rgba(31,58,46,.2); }
.ea .icone-grande { width: 150px; height: 150px; border-radius: 40px; background: ${VERDE}; color: ${AMARELO}; display: grid; place-items: center; }
.ea.escuro .icone-grande { background: rgba(246,243,234,.10); border: 3px solid rgba(246,243,234,.16); }
.ea .icone-grande svg { width: 86px; height: 86px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.ea .celular { position: relative; flex: none; margin: 40px auto 0; width: var(--cw); background: #101a14; border-radius: 64px; padding: 18px;
  box-shadow: 0 40px 90px rgba(23,48,31,.28), 0 0 0 3px rgba(23,48,31,.12); }
.ea .celular .tela { border-radius: 48px; overflow: hidden; background: #F6F3EA; padding-top: 78px; }
.ea .celular .tela div { height: 100%; background-repeat: no-repeat; background-size: 100% auto; }
.ea .celular::before { content: ""; position: absolute; top: 34px; left: 50%; width: 120px; height: 30px; margin-left: -60px; border-radius: 20px; background: #101a14; z-index: 2; }
.ea .lista { list-style: none; display: grid; gap: 16px; margin: auto 0; padding-top: 28px; }
.ea .lista li { display: flex; gap: 24px; align-items: flex-start; background: #fff; border: 2px solid #E6DFC9; border-radius: 28px; padding: 22px 30px; }
.ea.escuro .lista li { background: rgba(246,243,234,.07); border-color: rgba(246,243,234,.14); }
.ea .lista .n { flex: none; width: 56px; height: 56px; border-radius: 50%; background: ${AMARELO}; color: ${VERDE}; font-weight: 800; font-size: 30px; display: grid; place-items: center; }
.ea .lista .ok { flex: none; width: 52px; height: 52px; border-radius: 50%; background: ${VERDE}; display: grid; place-items: center; margin-top: 4px; }
.ea.escuro .lista .ok { background: ${AMARELO}; }
.ea .lista .ok svg { width: 30px; height: 30px; fill: none; stroke: ${AMARELO}; stroke-width: 3.2; stroke-linecap: round; stroke-linejoin: round; }
.ea.escuro .lista .ok svg { stroke: ${VERDE}; }
.ea .lista b { display: block; font-size: 36px; font-weight: 800; letter-spacing: -.01em; line-height: 1.15; }
.ea .lista div > span { display: block; font-size: 29px; line-height: 1.32; color: #5B675F; margin-top: 6px; }
.ea.escuro .lista div > span { color: ${SUAVE}; }
.ea .lista.folgada { gap: 20px; }
.ea .lista.folgada li { padding: 30px 34px; }
.ea .lista.folgada b { font-size: 40px; }
.ea .lista.folgada div > span { font-size: 31px; }
.ea .premium { font-style: normal; display: inline-block; font-size: 26px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; background: ${VERDE};
  color: ${AMARELO}; border-radius: 999px; padding: 6px 16px; margin-left: 12px; vertical-align: 6px; }
.ea.escuro .premium { background: ${AMARELO}; color: ${VERDE}; }
.ea .numeros { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: auto 0; }
.ea .numeros div { background: #fff; border: 2px solid #E6DFC9; border-radius: 28px; padding: 30px; }
.ea.escuro .numeros div { background: rgba(246,243,234,.07); border-color: rgba(246,243,234,.14); }
.ea .numeros b { display: block; font-size: 60px; font-weight: 800; letter-spacing: -.03em; line-height: 1; }
.ea.escuro .numeros b { color: ${AMARELO}; }
.ea .numeros span { display: block; font-size: 29px; color: #5B675F; margin-top: 12px; line-height: 1.3; }
.ea.escuro .numeros span { color: ${SUAVE}; }
.ea .precos { display: grid; gap: 12px; margin-top: 30px; }
.ea .precos div { display: flex; justify-content: space-between; align-items: baseline; gap: 20px; background: rgba(31,58,46,.05);
  border: 2px solid rgba(31,58,46,.12); border-radius: 24px; padding: 16px 30px; font-size: 32px; }
.ea.escuro .precos div { background: rgba(246,243,234,.07); border-color: rgba(246,243,234,.14); }
.ea .precos b { color: ${VERDE}; font-size: 36px; font-weight: 800; white-space: nowrap; }
.ea.escuro .precos b { color: ${AMARELO}; }
.ea .precos small { font-size: 26px; opacity: .75; }
.ea .baloes { display: grid; gap: 22px; margin-top: 46px; }
.ea .balao { background: #fff; color: ${TINTA}; border-radius: 30px 30px 30px 8px; padding: 28px 32px; font-size: 32px; line-height: 1.38; box-shadow: 0 16px 40px rgba(23,48,31,.10); max-width: 820px; }
.ea .balao.meu { background: #DCF8C6; border-radius: 30px 30px 8px 30px; margin-left: auto; }
/* stories: desenhados em 864x1536 e ampliados 1,25x; 200 px aqui = 250 px na imagem */
.ea.story { justify-content: center; padding: 200px 56px 240px; }
.ea.story.t-tela { justify-content: flex-start; }
.ea.story .b-capa { margin: auto 0; padding-bottom: 60px; }
.ea.story.v-topo .b-capa { margin: 40px 0 auto; }
.ea.story.v-base .b-capa { margin: auto 0 0; }
.ea.story h1 { font-size: 92px; }
.ea.story.t-capa h1 { font-size: 112px; line-height: 1.02; }
.ea.story.t-capa .texto { font-size: 38px; }
.ea.story h1.menor { font-size: 72px; }
.ea.story h2 { font-size: 62px; }
.ea.story .texto { font-size: 35px; }
.ea.story .lista { gap: 22px; padding-top: 36px; margin: 0; }
.ea.story .b-lista, .ea.story .b-numeros, .ea.story .b-precos, .ea.story .b-conversa { flex: none; margin: auto 0; }
.ea.story .lista li { padding: 32px 34px; border-radius: 32px; }
.ea.story .lista b { font-size: 40px; }
.ea.story .lista div > span { font-size: 31px; }
.ea.story .numeros { margin-top: 48px; }
.ea.story .numeros b { font-size: 66px; }
.ea.story .precos { gap: 16px; margin-top: 40px; }
.ea.story .precos div { padding: 24px 32px; font-size: 33px; }
.ea.story .precos b { font-size: 39px; }
`;
  }

  window.EstudioMarcas = window.EstudioMarcas || {};
  window.EstudioMarcas.appfiliado = { base, render, novo, css, ehCapa, fundo, margem: null, nomesIcones: NOMES_ICONES, artes: Object.keys(ARTES) };
})();
