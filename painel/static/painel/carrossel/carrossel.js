/* Renderizador de carrosséis do Appfiliado (protótipo).
 * Um slide é desenhado num <canvas> 1080x1350 (4:5, o melhor formato do feed do Instagram).
 * A mesma função serve para a prévia no painel e para baixar o PNG, então o que a
 * pessoa vê é exatamente o que ela posta. */
(function (global) {
  const W = 1080, H = 1350, M = 76; // M = margem

  const FONTES = {
    moderna:  { titulo: '"DM Sans"', peso: 800, corpo: '"DM Sans"', alta: false, escala: 1, lh: 1.04 },
    impacto:  { titulo: '"Bebas Neue"', peso: 400, corpo: '"DM Sans"', alta: true, escala: 1.34, lh: 1.1 },
    elegante: { titulo: '"Playfair Display"', peso: 900, corpo: '"DM Sans"', alta: false, escala: 0.92, lh: 1.08 },
  };
  // a = fundo forte, b = fundo claro (papel), acc = cor de destaque, ink = texto sobre o claro
  const TEMAS = {
    verde:   { a: '#1F3A2E', b: '#F6F3EA', acc: '#F2C230', ink: '#1D2A23' },
    laranja: { a: '#E8541E', b: '#FFF3EA', acc: '#FFD23F', ink: '#2A1408' },
    rosa:    { a: '#D6336C', b: '#FFF0F5', acc: '#FFE066', ink: '#3A0F20' },
    azul:    { a: '#2F6FDE', b: '#EEF4FF', acc: '#FFD43B', ink: '#0F1F3F' },
    preto:   { a: '#141414', b: '#F5F1E8', acc: '#D8B44A', ink: '#141414' },
  };

  const lum = (hex) => { const n = parseInt(hex.slice(1), 16), f = (c) => { c /= 255; return c <= .03928 ? c / 12.92 : Math.pow((c + .055) / 1.055, 2.4); };
    return .2126 * f(n >> 16) + .7152 * f((n >> 8) & 255) + .0722 * f(n & 255); };
  const razao = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  const sobre = (fundo, t) => razao(fundo, '#FFFFFF') >= razao(fundo, t.ink) ? '#FFFFFF' : t.ink; // a cor de texto que mais contrasta
  const rgba = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };
  const temDesconto = (d) => d.desconto >= 5 && d.de > d.por;
  const brl = (v) => 'R$ ' + v.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');

  const G = {}; // ganchos da auditoria (ver carrossel-auditoria.js); em produção ficam vazios
  const fixo = (fn) => { G.fixo = true; fn(); G.fixo = false; };
  const cabe = (c, txt, larg) => { if (c.measureText(txt).width <= larg) return txt; let u = txt; while (u.length > 3 && c.measureText(u + '…').width > larg) u = u.slice(0, -1); return u + '…'; };
  function rr(c, x, y, w, h, r, tag) { if (G.forma) G.forma(c, x, y, w, h, tag || 'forma'); c.beginPath(); c.roundRect(x, y, w, h, r); }

  // ---- texto com quebra de linha e *destaque* (marca-texto) ----------------------------
  function palavras(txt) {
    let d = false; const out = [];
    txt.trim().split(/\s+/).forEach((p) => { const inicio = p.startsWith('*'); if (inicio) d = true; const t = p.replace(/\*/g, '');
      if (d && !inicio && out.length && out[out.length - 1].d && (out[out.length - 1].t + ' ' + t).length <= 18) out[out.length - 1].t += ' ' + t; // palavras do mesmo destaque viram uma faixa só
      else out.push({ t, d }); if (p.endsWith('*') && p.length > 0) d = false; });
    return out;
  }
  function partes(c, p, larg) { // palavra mais larga que a linha: parte nos hífens e, se ainda for larga, por letras
    if (c.measureText(p.t).width + (p.d ? 28 : 0) <= larg) return [p];
    const out = []; (p.t.split(/(?<=-)/)).forEach((pc) => { let resto = pc;
      while (c.measureText(resto).width > larg * 0.96 && resto.length > 2) { let k = resto.length - 1; while (k > 1 && c.measureText(resto.slice(0, k) + '-').width > larg * 0.96) k--; out.push(resto.slice(0, k) + '-'); resto = resto.slice(k); }
      out.push(resto); });
    return out.map((t, i) => ({ t, d: p.d, cola: i > 0 }));
  }
  function linhas(c, txt, larg) {
    const ws = palavras(txt).flatMap((p) => partes(c, p, larg)), out = []; let atual = [], w = 0; const esp = c.measureText(' ').width;
    ws.forEach((p) => { const tw = c.measureText(p.t).width, pw = tw + (p.d ? 28 : 0), sep = atual.length && !p.cola ? esp : 0;
      if (atual.length && w + sep + pw > larg) { out.push({ ws: atual, w }); atual = []; w = 0; }
      w += (atual.length && !p.cola ? esp : 0) + pw; atual.push({ ...p, pw, tw }); });
    if (atual.length) out.push({ ws: atual, w }); return out;
  }
  /* Escreve o texto no retângulo (x, y, larg, alt): reduz a fonte até caber. Retorna a altura usada. */
  function bloco(c, txt, o) {
    const f = o.fonte, tit = o.titulo, fam = tit ? f.titulo : f.corpo, peso = tit ? f.peso : (o.peso || 500);
    const esc = tit ? f.escala : 1, lh = o.lh || (tit ? f.lh : 1.32);
    if (tit && f.alta) txt = txt.toUpperCase();
    let tam = (o.max || 100) * esc, lin;
    const min = (o.min || 30) * esc;
    for (;;) { c.font = `${peso} ${tam}px ${fam}`; lin = linhas(c, txt, o.larg);
      if ((lin.length * tam * lh <= (o.alt || 9999) && lin.every((l) => l.w <= o.larg + 1) && !lin.some((l) => l.ws.some((q) => q.cola))) || tam <= min) break; tam -= 3; } // só quebra palavra se nem no mínimo couber
    if (o.alt && lin.length * tam * lh > o.alt + 2) { // não coube nem no tamanho mínimo: corta no fim com "…"
      const ws = txt.split(/\s+/); while (ws.length > 1 && lin.length * tam * lh > o.alt + 2) { ws.pop(); txt = ws.join(' ').replace(/[*\s]+$/, '') + '…'; lin = linhas(c, txt, o.larg); }
      while (lin.length * tam * lh > o.alt + 2 && tam > 24) { tam -= 3; c.font = `${peso} ${tam}px ${fam}`; lin = linhas(c, txt, o.larg); } // palavra única: encolhe até caber
    }
    if (G.bloco) G.bloco({ txt, x: o.x, y: o.y, larg: o.larg, alt: o.alt || 9999, tam, min, lh, lin, centro: o.centro });
    c.textBaseline = 'alphabetic'; c.textAlign = 'left';
    lin.forEach((l, i) => {
      const base = o.y + tam * 0.82 + i * tam * lh; let x = o.x + (o.centro ? (o.larg - l.w) / 2 : 0);
      const esp = c.measureText(' ').width;
      l.ws.forEach((p) => {
        if (p.d) { // marca-texto atrás da palavra; emenda com a próxima se ela também for marcada
          const prox = l.ws[l.ws.indexOf(p) + 1], junta = prox && prox.d && !prox.cola ? esp + 1 : 0;
          c.save(); c.fillStyle = o.marca; c.translate(x, base - tam * 0.28); c.rotate(-0.012);
          rr(c, 0, -tam * 0.36, p.pw + junta, tam * 0.72, tam * 0.12, 'int'); c.fill(); c.restore(); }
        if (o.contorno) { c.save(); c.strokeStyle = o.contorno; c.lineWidth = tam * 0.09; c.lineJoin = 'round'; c.strokeText(p.t, x + (p.d ? 14 : 0), base); c.restore(); }
        c.fillStyle = p.d ? o.corMarca || o.cor : o.cor; G.fundoMarca = p.d ? o.marca : null; c.fillText(p.t, x + (p.d ? 14 : 0), base); G.fundoMarca = null; x += p.pw + (l.ws[l.ws.indexOf(p) + 1] && l.ws[l.ws.indexOf(p) + 1].cola ? 0 : esp); });
    });
    return { h: lin.length * tam * lh, tam, n: lin.length };
  }

  // ---- peças ----------------------------------------------------------------------------
  function pilula(c, x, y, txt, o) { // retorna a largura
    c.font = `700 ${o.tam || 30}px "DM Sans"`; const pad = o.pad || 28, w = c.measureText(txt).width + pad * 2, h = (o.tam || 30) + 30;
    c.fillStyle = o.fundo; rr(c, x, y, w, h, h / 2, 'pilula'); c.fill();
    if (o.borda) { c.strokeStyle = o.borda; c.lineWidth = 3; rr(c, x, y, w, h, h / 2, 'int'); c.stroke(); }
    c.fillStyle = o.cor; c.textBaseline = 'middle'; c.textAlign = 'left'; c.fillText(txt, x + pad, y + h / 2 + 2); return w;
  }
  function selo(c, cx, cy, r, txt, fundo, cor, rot) { // estrela de oferta
    if (G.forma) G.forma(c, cx - r, cy - r, 2 * r, 2 * r, 'selo');
    c.save(); c.translate(cx, cy); c.rotate(rot || 0); c.fillStyle = fundo; c.beginPath();
    for (let i = 0; i < 28; i++) { const a = i * Math.PI / 14, rr_ = i % 2 ? r * 0.86 : r; c.lineTo(Math.cos(a) * rr_, Math.sin(a) * rr_); }
    c.closePath(); c.fill(); c.fillStyle = cor; c.textAlign = 'center'; c.textBaseline = 'middle';
    c.font = `800 ${r * 0.52}px "DM Sans"`; c.fillText(txt, 0, 4); c.restore();
  }
  function estrelas(c, x, y, tam, cor, cheias) {
    for (let k = 0; k < 5; k++) { c.fillStyle = k < (cheias == null ? 5 : cheias) ? cor : rgba('#888888', 0.35); c.beginPath();
      for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? tam * 0.2 : tam * 0.5; c.lineTo(x + k * tam * 1.15 + tam / 2 + Math.cos(a) * r, y + tam / 2 + Math.sin(a) * r); }
      c.closePath(); c.fill(); }
  }
  function pontos(c, x, y, col, lin, gap, r, cor) { if (G.decor) G.decor(c, x - gap / 2, y - gap / 2, col * gap, lin * gap); c.fillStyle = cor; for (let i = 0; i < col; i++) for (let j = 0; j < lin; j++) { c.beginPath(); c.arc(x + i * gap, y + j * gap, r, 0, 7); c.fill(); } }
  function seta(c, x, y, tam, cor, esp) { c.strokeStyle = cor; c.lineWidth = esp || 7; c.lineCap = 'round'; c.lineJoin = 'round';
    c.beginPath(); c.moveTo(x, y); c.lineTo(x + tam, y); c.moveTo(x + tam * 0.62, y - tam * 0.34); c.lineTo(x + tam, y); c.lineTo(x + tam * 0.62, y + tam * 0.34); c.stroke(); }
  function foto(c, img, x, y, w, h, r) { c.save(); rr(c, x, y, w, h, r, 'int'); c.clip();
    const s = Math.max(w / img.width, h / img.height), iw = img.width * s, ih = img.height * s; c.drawImage(img, x + (w - iw) / 2, y + (h - ih) / 2, iw, ih); c.restore(); }
  /* Cartão-adesivo: foto com borda grossa e sombra dura na cor de destaque. */
  function adesivo(c, img, x, y, w, h, t, rot) { c.save(); c.translate(x + w / 2, y + h / 2); c.rotate(rot || 0); c.translate(-w / 2, -h / 2);
    c.fillStyle = t.ink; rr(c, 18, 22, w, h, 46, 'int'); c.fill();
    c.fillStyle = '#fff'; rr(c, 0, 0, w, h, 46, 'foto'); c.fill(); foto(c, img, 14, 14, w - 28, h - 28, 34);
    c.strokeStyle = t.ink; c.lineWidth = 7; rr(c, 0, 0, w, h, 46, 'int'); c.stroke(); c.restore(); }

  // ---- estrutura comum a todos os slides -----------------------------------------------
  function moldura(c, fundo, t, d, i, n, ultimo, decor) { G.fixo = true; try {
    c.fillStyle = fundo; c.fillRect(0, 0, W, H); const cor = sobre(fundo, t), suave = rgba(cor, 0.9);
    // textura sutil de pontos no canto
    if (decor) pontos(c, decor[0], decor[1], 6, 4, 46, 3.2, rgba(cor, fundo === t.acc ? 0.2 : 0.13));
    // topo: avatar + @ e contador
    const sobreAcc = fundo === t.acc; c.fillStyle = sobreAcc ? t.ink : t.acc; c.beginPath(); c.arc(M + 34, 112, 34, 0, 7); c.fill();
    c.fillStyle = sobreAcc ? t.acc : t.ink; c.font = '800 36px "DM Sans"'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText((d.arroba.replace('@', '')[0] || 'A').toUpperCase(), M + 34, 115);
    c.font = '700 28px "DM Sans"'; const txt = String(i + 1).padStart(2, '0') + ' / ' + String(n).padStart(2, '0'); const w = c.measureText(txt).width + 44;
    c.fillStyle = cor; c.font = '700 33px "DM Sans"'; c.textAlign = 'left'; c.fillText(cabe(c, d.arroba, W - 2 * M - 86 - w - 30), M + 86, 114);
    c.font = '700 28px "DM Sans"';
    c.strokeStyle = rgba(cor, 0.35); c.lineWidth = 3; rr(c, W - M - w, 82, w, 60, 30, 'pilula'); c.stroke();
    c.fillStyle = cor; c.textAlign = 'center'; c.fillText(txt, W - M - w / 2, 114);
    // rodapé: arrasta + pontinhos
    if (!ultimo) { c.fillStyle = suave; c.font = '700 30px "DM Sans"'; c.textAlign = 'left'; c.textBaseline = 'middle'; c.fillText('Arrasta', M, H - 92); seta(c, M + 138, H - 92, 54, suave, 6); }
    for (let k = 0; k < n; k++) { c.fillStyle = k === i ? t.acc : rgba(cor, 0.28); if (fundo === t.acc) c.fillStyle = k === i ? t.ink : rgba(t.ink, 0.28);
      rr(c, W - M - (n - k) * 30 + (k === i ? -16 : 0), H - 102, k === i ? 34 : 14, 14, 7, 'int'); c.fill(); }
    return cor; } finally { G.fixo = false; }
  }

  // ---- os tipos de slide ----------------------------------------------------------------
  const SLIDES = {
    capa(c, s, t, f, d, img) {
      const cor = sobre(t.a, t);
      pilula(c, M, 196, s.selo || 'ACHADO DA SEMANA', { fundo: t.acc, cor: t.ink, tam: 30 });
      adesivo(c, img, 232, 285, 640, 640, t, -0.045);
      if (temDesconto(d)) selo(c, 842, 372, 124, '-' + d.desconto + '%', t.acc, t.ink, 0.2);
      bloco(c, s.titulo, { fonte: f, titulo: true, x: M, y: 1012, larg: W - 2 * M, alt: 180, max: 112, min: 64, cor, marca: t.acc, corMarca: t.ink });
    },
    texto(c, s, t, f, d) {
      // mede o bloco (título + texto) para posicionar; com "arte", o texto sobe e a ilustração ocupa o resto
      const medir = (txt, o) => { const sv = G.bloco; G.bloco = null; const k = document.createElement('canvas').getContext('2d'); const r = bloco(k, txt, Object.assign({}, o, { marca: '#000', cor: '#000' })); G.bloco = sv; return r.h; };
      const arteImg = s.arte && global.Carrossel && global.Carrossel.util && global.Carrossel.util.IMGS_ARTE && global.Carrossel.util.IMGS_ARTE[s.arte];
      const arteFn = s.arte && global.Carrossel && global.Carrossel.util && global.Carrossel.util.arte;
      const o1 = { fonte: f, titulo: true, x: M, larg: W - 2 * M, alt: arteFn ? 330 : 560, max: arteImg ? 80 : arteFn ? 100 : 138, min: arteFn ? 64 : 84 }, o2 = { fonte: f, x: M, larg: W - 2 * M - 80, alt: arteFn ? 130 : 300, max: arteFn ? 40 : 46, min: 32, peso: 500 };
      const h1 = medir(s.titulo, Object.assign({ y: 0 }, o1)), h2 = s.texto ? medir(s.texto, Object.assign({ y: 0 }, o2)) : 0, total = 16 + 54 + h1 + (s.texto ? 56 + h2 : 0);
      let y0 = Math.max(220, Math.min(560, 190 + (1010 - total) / 2)), tamArte = 0;
      if (arteFn) { y0 = 215; const livre = 1190 - (y0 + total + 36); tamArte = Math.min(720, livre); if (tamArte < 300) { tamArte = 0; y0 = Math.max(220, Math.min(560, 190 + (1010 - total) / 2)); } }
      c.fillStyle = t.acc; rr(c, M, y0, 150, 16, 8, 'int'); c.fill();
      const r = bloco(c, s.titulo, Object.assign({ y: y0 + 54, cor: t.ink, marca: t.acc, corMarca: t.ink }, o1));
      if (s.texto) bloco(c, s.texto, Object.assign({ y: y0 + 54 + r.h + 56, cor: rgba(t.ink, 0.72), marca: t.acc }, o2));
      if (tamArte) { const topo = y0 + total + 36; arteFn(c, s.arte, W / 2, topo + (1190 - topo) / 2, tamArte, t); }
    },
    produto(c, s, t, f, d, img) {
      adesivo(c, img, 160, 210, 760, 600, t, 0.03);
      c.fillStyle = razao(t.a, t.acc) >= 3 ? t.acc : sobre(t.a, t); c.font = '800 30px "DM Sans"'; c.textAlign = 'left'; c.textBaseline = 'alphabetic'; c.fillText((s.rotulo || 'CONHEÇA').toUpperCase(), M, 925);
      bloco(c, s.titulo, { fonte: f, titulo: true, x: M, y: 950, larg: W - 2 * M, alt: 170, max: 82, min: 48, cor: sobre(t.a, t), marca: t.acc, corMarca: t.ink });
      let x = M; c.font = '700 28px "DM Sans"'; // uma fileira só: as etiquetas que não couberem ficam de fora
      (s.chips || []).slice(0, 4).forEach((ch) => { ch = cabe(c, ch, 420); const w = c.measureText(ch).width + 52; if (x + w > W - M) return;
        x += pilula(c, x, 1130, ch, { fundo: 'rgba(0,0,0,0)', borda: rgba(sobre(t.a, t), 0.65), cor: sobre(t.a, t), tam: 28, pad: 26 }) + 14; });
    },
    preco(c, s, t, f, d) {
      const desc = temDesconto(d); c.textAlign = 'left'; c.textBaseline = 'alphabetic';
      const yRot = desc ? 610 : 540, yBloco = desc ? 770 : 700;
      if (desc) {
        c.fillStyle = rgba(t.ink, 0.78); c.font = '700 38px "DM Sans"'; c.fillText('ANTES', M, 370);
        c.font = '700 84px "DM Sans"'; const de = brl(d.de); c.fillStyle = rgba(t.ink, 0.72); c.fillText(de, M, 470); const w = c.measureText(de).width;
        c.strokeStyle = t.a === '#141414' ? t.acc : t.a; c.lineWidth = 9; c.lineCap = 'round'; c.beginPath(); c.moveTo(M - 8, 440); c.lineTo(M + w + 8, 432); c.stroke();
      }
      c.fillStyle = t.ink; c.font = '700 38px "DM Sans"'; c.textAlign = 'left'; c.textBaseline = 'alphabetic'; c.fillText(desc ? 'AGORA' : 'POR APENAS', M, yRot);
      c.save(); c.translate(W / 2 + 10, yBloco); c.rotate(-0.035); c.fillStyle = t.acc; rr(c, -W / 2 + M + 8, -112, W - 2 * M - 16, 230, 34, 'cartao'); c.fill(); c.strokeStyle = t.ink; c.lineWidth = 7; rr(c, -W / 2 + M + 8, -112, W - 2 * M - 16, 230, 34, 'int'); c.stroke();
      c.fillStyle = t.ink; c.textAlign = 'center'; c.textBaseline = 'middle'; let tam = 190; c.font = `800 ${tam}px "DM Sans"`; while (c.measureText(brl(d.por)).width > W - 2 * M - 100) { tam -= 4; c.font = `800 ${tam}px "DM Sans"`; }
      c.fillText(brl(d.por), 0, 12); c.restore();
      if (desc) { selo(c, W - 176, 520, 112, '-' + d.desconto + '%', t.a, sobre(t.a, t), 0.22);
        pilula(c, M, 985, 'Você economiza ' + brl(d.de - d.por), { fundo: t.a, cor: sobre(t.a, t), tam: 40, pad: 38 }); }
      c.fillStyle = rgba(t.ink, 0.78); c.font = '500 28px "DM Sans"'; c.textAlign = 'left'; c.textBaseline = 'alphabetic'; c.fillText('Preço visto hoje. Valores podem mudar a qualquer momento.', M, desc ? 1150 : 960);
    },
    prova(c, s, t, f, d) {
      const cor = sobre(t.a, t), itens = []; if (d.nota > 0) itens.push('nota'); if (d.vendas > 0) itens.push('vendas');
      const gap = 36, bw = itens.length === 2 ? (W - 2 * M - gap) / 2 : W - 2 * M;
      bloco(c, s.titulo, { fonte: f, titulo: true, x: M, y: 230, larg: W - 2 * M, alt: 260, max: 96, min: 60, cor, marca: t.acc, corMarca: t.ink });
      itens.forEach((it, k) => {
        const x = M + k * (bw + gap), txt = it === 'nota' ? d.nota.toFixed(1).replace('.', ',') : '+' + d.vendas.toLocaleString('pt-BR'), rot = it === 'nota' ? 'nota média' : (d.vendas === 1 ? 'vendido' : 'vendidos');
        c.fillStyle = t.b; rr(c, x, 560, bw, 520, 44, 'cartao'); c.fill();
        c.fillStyle = t.ink; c.textAlign = 'center'; c.textBaseline = 'alphabetic'; let tam = 150; c.font = `800 ${tam}px "DM Sans"`; while (c.measureText(txt).width > bw - 50) { tam -= 4; c.font = `800 ${tam}px "DM Sans"`; }
        c.fillText(txt, x + bw / 2, 790); c.font = '700 40px "DM Sans"'; c.fillStyle = rgba(t.ink, 0.72); c.fillText(rot, x + bw / 2, 860);
        if (it === 'nota') estrelas(c, x + bw / 2 - 5 * 40 * 1.15 / 2 + 3, 905, 40, razao(t.b, t.acc) >= 1.6 ? t.acc : '#F5B301', Math.round(d.nota));
        else { c.fillStyle = t.acc; rr(c, x + bw / 2 - 60, 920, 120, 14, 7, 'int'); c.fill(); }
      });
      c.fillStyle = cor; c.font = '700 38px "DM Sans"'; c.textAlign = 'left'; c.textBaseline = 'alphabetic'; c.fillText(cabe(c, s.texto || 'Quem comprou, aprovou.', W - 2 * M), M, 1170);
    },
    cta(c, s, t, f, d) {
      const cor = t.ink;
      bloco(c, s.titulo, { fonte: f, titulo: true, x: M, y: 250, larg: W - 2 * M, alt: 300, max: 190, min: 100, cor, marca: '#FFFFFF', corMarca: cor });
      c.save(); c.translate(W / 2, 700); c.rotate(-0.02); c.fillStyle = t.ink; rr(c, -W / 2 + M, -86, W - 2 * M, 172, 86, 'botao'); c.fill();
      c.fillStyle = t.acc; c.font = '800 78px "DM Sans"'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(s.botao || 'LINK NA BIO', -34, 6); seta(c, 218, 4, 78, t.acc, 10); c.restore();
      (s.passos || []).forEach((p, k) => { const y = 910 + k * 132; c.fillStyle = t.ink; c.beginPath(); c.arc(M + 40, y + 36, 40, 0, 7); c.fill(); c.fillStyle = t.acc; c.font = '800 44px "DM Sans"'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(k + 1, M + 40, y + 40);
        bloco(c, p, { fonte: f, x: M + 110, y: y, larg: W - 2 * M - 110, alt: 90, max: 42, min: 32, cor: t.ink, peso: 700, lh: 1.2 }); });
    },
    final(c, s, t, f, d) {
      c.fillStyle = t.acc; c.beginPath(); c.arc(W / 2, 330, 110, 0, 7); c.fill(); c.fillStyle = t.ink; c.font = '800 120px "DM Sans"'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText((d.arroba.replace('@', '')[0] || 'A').toUpperCase(), W / 2, 342);
      c.fillStyle = sobre(t.a, t); c.font = '800 48px "DM Sans"'; c.fillText(cabe(c, d.arroba, W - 2 * M), W / 2, 500);
      bloco(c, s.titulo, { fonte: f, titulo: true, x: M, y: 570, larg: W - 2 * M, alt: 310, max: 118, min: 64, cor: sobre(t.a, t), centro: true, marca: t.acc, corMarca: t.ink });
      // ícones de salvar e enviar
      const y = 930; c.strokeStyle = t.acc; c.lineWidth = 8; c.lineJoin = 'round';
      c.beginPath(); c.moveTo(W / 2 - 170, y); c.lineTo(W / 2 - 100, y); c.lineTo(W / 2 - 100, y + 96); c.lineTo(W / 2 - 135, y + 68); c.lineTo(W / 2 - 170, y + 96); c.closePath(); c.stroke();
      c.beginPath(); c.moveTo(W / 2 + 60, y + 48); c.lineTo(W / 2 + 170, y); c.lineTo(W / 2 + 130, y + 96); c.lineTo(W / 2 + 108, y + 62); c.closePath(); c.stroke();
      bloco(c, s.texto, { fonte: f, x: M + 40, y: 1066, larg: W - 2 * M - 80, alt: 120, max: 40, min: 30, cor: sobre(t.a, t), peso: 600, centro: true });
      if (d.marca) fixo(() => { c.fillStyle = sobre(t.a, t); c.font = '500 24px "DM Sans"'; c.textAlign = 'center'; c.fillText('Feito com Appfiliado', W / 2, H - 52); });
    },
  };
  const FUNDO = { capa: 'a', texto: 'b', produto: 'a', preco: 'b', prova: 'a', cta: 'acc', final: 'a' };
  const MODELOS = {};
  MODELOS.destaque = { nome: 'Destaque', premium: false, decor: true, slides: SLIDES, fundo: (tipo, t) => ({ a: t.a, b: t.b, acc: t.acc })[FUNDO[tipo]],
    moldura: (c, fundo, t, d, i, n, ultimo, decor) => moldura(c, fundo, t, d, i, n, ultimo, decor) };

  /* Ensaio: desenha o slide num canvas de rascunho só para medir onde ficam os textos, e escolhe
   * um canto sem texto para os pontinhos decorativos (se não houver, fica sem). */
  const CANTOS = [[W - 330, 196], [W - 330, H - 330]];
  function cantoLivre(t, f, s, dados, cor, slides) {
    const k = document.createElement('canvas'); k.width = W; k.height = H; const c = k.getContext('2d'), caixas = [];
    const salvo = { forma: G.forma, bloco: G.bloco, decor: G.decor, fixo: G.fixo }; G.forma = G.bloco = G.decor = null; G.fixo = false;
    c.fillText = function (txt, x, y) { const m = c.measureText(String(txt)), w = m.width, x0 = c.textAlign === 'center' ? x - w / 2 : c.textAlign === 'right' ? x - w : x, tr = c.getTransform();
      [[x0, y - m.actualBoundingBoxAscent], [x0 + w, y + m.actualBoundingBoxDescent]].forEach(() => 0);
      const pts = [[x0, y - m.actualBoundingBoxAscent], [x0 + w, y + m.actualBoundingBoxDescent]].map(([a, b]) => [tr.a * a + tr.c * b + tr.e, tr.b * a + tr.d * b + tr.f]);
      caixas.push({ x: Math.min(pts[0][0], pts[1][0]), y: Math.min(pts[0][1], pts[1][1]), w: Math.abs(pts[1][0] - pts[0][0]), h: Math.abs(pts[1][1] - pts[0][1]) }); };
    try { slides[s.tipo](c, s, t, f, dados, dados.img); } finally { G.forma = salvo.forma; G.bloco = salvo.bloco; G.decor = salvo.decor; G.fixo = salvo.fixo; }
    return CANTOS.find(([x, y]) => { const x0 = x - 23, y0 = y - 23, x1 = x0 + 6 * 46, y1 = y0 + 4 * 46; // mesma caixa que pontos() desenha
      return caixas.every((q) => q.x > x1 + 14 || q.x + q.w < x0 - 14 || q.y > y1 + 14 || q.y + q.h < y0 - 14); }) || null;
  }

  function desenhar(canvas, roteiro, i, dados, op) {
    const t = TEMAS[op.tema], f = FONTES[op.fonte]; let s = roteiro[i], modelo = MODELOS[op.modelo || 'destaque'];
    if (s.tipo === 'prova' && !(dados.nota > 0 || dados.vendas > 0)) s = Object.assign({}, s, { tipo: 'texto' });
    // Tipo de slide que o modelo ainda não tem: usa o slide do Destaque inteiro (fundo e moldura
    // dele também), para as cores do texto combinarem com o fundo em que ele foi pensado.
    if (!modelo.slides[s.tipo]) modelo = MODELOS.destaque;
    const slides = Object.assign({}, MODELOS.destaque.slides, modelo.slides);
    canvas.width = W; canvas.height = H; const c = canvas.getContext('2d'), cor = modelo.fundo(s.tipo, t);
    const decor = modelo.decor ? cantoLivre(t, f, s, dados, cor, slides) : null;
    if (G.antes) G.antes(c, i, s, cor);
    modelo.moldura(c, cor, t, dados, i, roteiro.length, i === roteiro.length - 1 || !!dados.semArrasta, decor, s);
    c.save(); slides[s.tipo](c, s, t, f, dados, dados.img, { i, n: roteiro.length, op }); c.restore();
    if (G.depois) return G.depois(c, i, s);
  }
  const util = { W, H, M, G, TEMAS, FONTES, rr, bloco, pilula, selo, estrelas, pontos, seta, foto, cabe, brl, rgba, sobre, razao, lum, fixo, temDesconto, linhas };
  global.Carrossel = { desenhar, TEMAS, FONTES, MODELOS, W, H, M, G, util, registrar: (nome, def) => { MODELOS[nome] = def; }, _cantoLivre: cantoLivre };
})(window);
