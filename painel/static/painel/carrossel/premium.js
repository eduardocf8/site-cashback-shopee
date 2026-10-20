/* Modelos premium do Appfiliado (protótipo).
 * Inspirados em carrosséis de marcas grandes (Sephora, Glossier, Primally Pure, Facetheory,
 * Honest Greens, Kate Farms): o produto aparece recortado, sem o fundo da foto, sobre um fundo
 * pensado para ele. Quando o recorte não é confiável, o mesmo slide usa a foto inteira num cartão.
 * Dados extras em d: recorte (imagem sem fundo ou null) e det ([x, y, raio] do detalhe, 0..1).
 * Tipos de slide: capa, vantagens, detalhe, anotado, preco, cta. */
(function () {
  const C = window.Carrossel, U = C.util;
  const { W, H, M, G, rr, bloco, pilula, estrelas, brl, sobre, razao, temDesconto, seta } = U;
  const DM = '"DM Sans"', SERIF = '"Instrument Serif"', SORA = '"Sora"', MAN = '"Manrope"';
  const hex = (h) => { const n = parseInt(h.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; };
  const mix = (a, b, p) => { const x = hex(a), y = hex(b); return '#' + [0, 1, 2].map((k) => Math.round(x[k] * p + y[k] * (1 - p)).toString(16).padStart(2, '0')).join(''); };
  const garante = (cor, fundo, alvo, min) => { let q = 1; const c0 = cor; while (razao(cor, fundo) < (min || 4.6) && q > 0) { q -= 0.1; cor = mix(c0, alvo, Math.max(q, 0)); } return cor; };
  const sem = (fn) => { const s = G.ignorarArc; G.ignorarArc = true; try { fn(); } finally { G.ignorarArc = s; } };
  const decor = (fn) => { const s = G.ignorarTexto; G.ignorarTexto = true; try { fn(); } finally { G.ignorarTexto = s; } };
  const reg = (c, x, y, w, h, tag) => { if (G.forma) G.forma(c, x, y, w, h, tag); };
  const texto = (c, txt, x, y, font, cor, al, esp) => { c.font = font; c.fillStyle = cor; c.textAlign = al || 'left'; c.textBaseline = 'alphabetic'; c.letterSpacing = esp || '0px'; c.fillText(txt, x, y); c.letterSpacing = '0px'; };
  const larg = (c, txt, font, esp) => { c.font = font; c.letterSpacing = esp || '0px'; const w = c.measureText(txt).width; c.letterSpacing = '0px'; return w; };
  const encaixar = (c, txt, l, tam, peso, fam, min) => { let k = tam; c.font = `${peso} ${k}px ${fam}`; while (c.measureText(txt).width > l && k > (min || 30)) { k -= 3; c.font = `${peso} ${k}px ${fam}`; } return k; };
  const num = (v) => String(v).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  const vendidos = (v) => (v >= 1000 ? (v / 1000).toFixed(1).replace('.0', '').replace('.', ',') + ' mil' : num(v)) + ' vendidos';
  const rotulo = (c, txt, x, y, cor, al) => texto(c, String(txt).toUpperCase(), x, y, `800 24px ${DM}`, cor, al || 'left', '5px');

  Object.assign(C.FONTES, { serifa: { titulo: SERIF, peso: 400, corpo: DM, alta: false, escala: 1.28, lh: 1.0 }, geometrica: { titulo: SORA, peso: 800, corpo: DM, alta: false, escala: 0.84, lh: 1.08 } });

  // ---- o produto -------------------------------------------------------------------------
  /** Desenha o produto dentro da caixa. Recortado: solto, com sombra no chão. Sem recorte: cartão
   *  branco com a foto inteira. Retorna o retângulo ocupado (para ancorar rótulos, zoom e selos). */
  function produto(c, d, x, y, w, h, o) {
    o = o || {};
    if (d.recorte) {
      const im = d.recorte, s = Math.min(w / im.width, h / im.height) * (o.escala || 1), iw = im.width * s, ih = im.height * s;
      const al = o.al || { x: 0.5, y: 1 }, bx = x + (w - iw) * al.x, by = y + (h - ih) * al.y;
      if (o.chao !== false && !o.rot) { // sombra de contato no "chão"
        const g = c.createRadialGradient(bx + iw / 2, by + ih, 0, bx + iw / 2, by + ih, iw * 0.55); g.addColorStop(0, `rgba(0,0,0,${o.sombra || 0.28})`); g.addColorStop(1, 'rgba(0,0,0,0)');
        c.save(); c.fillStyle = g; c.beginPath(); c.ellipse(bx + iw / 2, by + ih - 4, iw * 0.55, Math.max(18, ih * 0.05), 0, 0, Math.PI * 2); c.fill(); c.restore();
      }
      c.save(); if (o.rot) { c.translate(bx + iw / 2, by + ih / 2); c.rotate(o.rot); c.translate(-(bx + iw / 2), -(by + ih / 2)); }
      c.shadowColor = `rgba(0,0,0,${o.sombraProj == null ? 0.22 : o.sombraProj})`; c.shadowBlur = 44; c.shadowOffsetY = 26; c.drawImage(im, bx, by, iw, ih);
      reg(c, bx, by, iw, ih, o.tag || 'foto'); c.restore();
      return { x: bx, y: by, w: iw, h: ih, s, recorte: true, rot: o.rot || 0 };
    }
    const lado = Math.min(w, h) * (o.escala || 1), al = o.al || { x: 0.5, y: 1 }, bx = x + (w - lado) * al.x, by = y + (h - lado) * al.y;
    c.save(); if (o.rot) { c.translate(bx + lado / 2, by + lado / 2); c.rotate(o.rot); c.translate(-(bx + lado / 2), -(by + lado / 2)); }
    c.shadowColor = 'rgba(0,0,0,0.2)'; c.shadowBlur = 40; c.shadowOffsetY = 20; c.fillStyle = '#FFFFFF'; rr(c, bx, by, lado, lado, 40, 'int'); c.fill(); c.shadowColor = 'transparent';
    c.save(); rr(c, bx + 14, by + 14, lado - 28, lado - 28, 28, 'int'); c.clip(); const im = d.img, s = Math.max((lado - 28) / im.width, (lado - 28) / im.height);
    c.drawImage(im, bx + 14 + (lado - 28 - im.width * s) / 2, by + 14 + (lado - 28 - im.height * s) / 2, im.width * s, im.height * s); c.restore();
    reg(c, bx, by, lado, lado, o.tag || 'foto'); c.restore();
    return { x: bx, y: by, w: lado, h: lado, s: 0, recorte: false, rot: o.rot || 0 };
  }

  /** Círculo com o detalhe ampliado (como a Sephora faz com a escova do rímel). */
  function zoom(c, d, cx, cy, R, o) {
    o = o || {}; const src = d.recorte || d.img, det = d.recorte && d.det ? d.det : [0.5, 0.5, 0.2];
    const sx = det[0] * src.width, sy = det[1] * src.height, sr = det[2] * Math.max(src.width, src.height);
    reg(c, cx - R - 10, cy - R - 10, 2 * R + 20, 2 * R + 20, 'foto2');
    sem(() => { c.save(); c.shadowColor = 'rgba(0,0,0,0.22)'; c.shadowBlur = 30; c.shadowOffsetY = 14; c.fillStyle = o.borda || '#FFFFFF'; c.beginPath(); c.arc(cx, cy, R + 10, 0, Math.PI * 2); c.fill(); c.restore();
      c.save(); c.beginPath(); c.arc(cx, cy, R, 0, Math.PI * 2); c.clip(); c.fillStyle = o.fundo || '#FFFFFF'; c.beginPath(); c.arc(cx, cy, R, 0, Math.PI * 2); c.fill();
      c.drawImage(src, sx - sr, sy - sr, 2 * sr, 2 * sr, cx - R, cy - R, 2 * R, 2 * R); c.restore(); });
    return { sx: det[0], sy: det[1] };
  }
  /** Ponto da caixa do produto que corresponde ao centro do detalhe ampliado. */
  const pontoDetalhe = (d, b) => { const det = d.recorte && d.det ? d.det : [0.5, 0.5]; return [b.x + det[0] * b.w, b.y + det[1] * b.h]; };

  /** Ponto da borda do produto numa altura y, vindo da esquerda ou da direita (para os rótulos). */
  function bordaNaLinha(d, b, y, lado) {
    if (!d.recorte) return [lado < 0 ? b.x : b.x + b.w, Math.max(b.y + 20, Math.min(b.y + b.h - 20, y))];
    if (!d._alfa) { const k = document.createElement('canvas'); k.width = d.recorte.width; k.height = d.recorte.height; const kc = k.getContext('2d'); kc.drawImage(d.recorte, 0, 0); d._alfa = kc.getImageData(0, 0, k.width, k.height).data; }
    const iw = d.recorte.width, ih = d.recorte.height, A = (sx, sy) => d._alfa[(sy * iw + sx) * 4 + 3];
    for (let dy = 0; dy < ih / 2; dy += 4) for (const sgn of [1, -1]) {
      const sy = Math.round((y - b.y) / b.h * ih) + sgn * dy; if (sy < 0 || sy >= ih) continue;
      if (lado < 0) { for (let sx = 0; sx < iw; sx += 2) if (A(sx, sy) > 140) return [b.x + (sx + 6) / iw * b.w, b.y + sy / ih * b.h]; }
      else { for (let sx = iw - 1; sx >= 0; sx -= 2) if (A(sx, sy) > 140) return [b.x + (sx - 6) / iw * b.w, b.y + sy / ih * b.h]; }
    }
    return [b.x + b.w / 2, b.y + b.h / 2];
  }

  // ---- peças -------------------------------------------------------------------------------
  function check(c, x, y, r, fundo, cor) { sem(() => { c.fillStyle = fundo; c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill(); });
    c.strokeStyle = cor; c.lineWidth = r * 0.22; c.lineCap = 'round'; c.lineJoin = 'round'; c.beginPath(); c.moveTo(x - r * 0.42, y + r * 0.02); c.lineTo(x - r * 0.1, y + r * 0.34); c.lineTo(x + r * 0.45, y - r * 0.3); c.stroke(); }
  /** Selo redondo com texto correndo em volta (Lolavie/Ulta). */
  function seloCircular(c, cx, cy, R, volta, meio, fundo, cor) {
    reg(c, cx - R, cy - R, 2 * R, 2 * R, 'selo');
    sem(() => { c.fillStyle = fundo; c.beginPath(); c.arc(cx, cy, R, 0, Math.PI * 2); c.fill(); c.strokeStyle = cor; c.lineWidth = 2; c.beginPath(); c.arc(cx, cy, R * 0.66, 0, Math.PI * 2); c.stroke(); });
    const t = (volta.toUpperCase() + ' • ').repeat(3), tam = R * 0.17; c.font = `800 ${tam}px ${DM}`;
    const passo = (Math.PI * 2) / t.length;
    decor(() => { for (let i = 0; i < t.length; i++) { c.save(); c.translate(cx, cy); c.rotate(-Math.PI / 2 + i * passo); c.translate(0, -R * 0.82); c.fillStyle = cor; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(t[i], 0, 0); c.restore(); } });
    const k = encaixar(c, meio, R * 1.1, R * 0.5, 800, DM, 18); texto(c, meio, cx, cy + k * 0.36, `800 ${k}px ${DM}`, cor, 'center');
  }
  /** Etiqueta de preço inclinada com furinho (Honest Greens). */
  function etiqueta(c, cx, cy, w, h, rot, fundo, cor, cima, preco) {
    c.save(); c.translate(cx, cy); c.rotate(rot);
    c.shadowColor = 'rgba(0,0,0,0.18)'; c.shadowBlur = 24; c.shadowOffsetY = 12; c.fillStyle = fundo;
    c.beginPath(); c.moveTo(-w / 2 + 40, -h / 2); c.lineTo(w / 2, -h / 2); c.lineTo(w / 2, h / 2); c.lineTo(-w / 2 + 40, h / 2); c.lineTo(-w / 2, 0); c.closePath(); c.fill(); c.shadowColor = 'transparent';
    reg(c, -w / 2, -h / 2, w, h, 'cartao');
    sem(() => { c.fillStyle = mix(fundo, '#000000', 0.7); c.beginPath(); c.arc(-w / 2 + 34, 0, 9, 0, Math.PI * 2); c.fill(); });
    if (cima) { const kt = encaixar(c, cima.toUpperCase(), w - 90, Math.round(h * 0.16), 800, DM, 16); texto(c, cima.toUpperCase(), 14, -h / 2 + kt + 18, `800 ${kt}px ${DM}`, cor, "center", "3px"); }
    const k = encaixar(c, preco, w - 110, h * 0.5, 800, MAN, 30); texto(c, preco, 14, (cima ? h * 0.3 : k * 0.36), `800 ${k}px ${MAN}`, cor, 'center');
    c.restore();
  }
  /** Moldura padrão premium: perfil, contagem e "Arrasta". */
  function moldura(c, d, i, n, ultimo, cor) {
    texto(c, d.arroba.slice(0, 28), M, 122, `700 26px ${DM}`, cor, 'left');
    texto(c, String(i + 1).padStart(2, '0') + ' / ' + String(n).padStart(2, '0'), W - M, 122, `700 26px ${DM}`, cor, 'right', '2px');
    if (!ultimo) { texto(c, 'ARRASTA', M, 1296, `700 22px ${DM}`, cor, 'left', '5px'); seta(c, M + 150, 1290, 40, cor, 4); }
  }
  /** Bloco de preço reutilizável: "de" riscado, preço grande, economia. Retorna a altura. */
  function blocoPreco(c, d, x, y, l, p, fam, peso) {
    const desc = temDesconto(d); let yy = y;
    if (desc) { const f = `500 52px ${DM}`; texto(c, 'de ' + brl(d.de), x, yy + 44, f, p.soft, 'left'); const w = larg(c, 'de ' + brl(d.de), f); c.strokeStyle = p.risco; c.lineWidth = 4; c.beginPath(); c.moveTo(x + larg(c, 'de ', f) - 4, yy + 26); c.lineTo(x + w + 4, yy + 26); c.stroke(); yy += 74; }
    const k = encaixar(c, brl(d.por), l, 200, peso || 800, fam || MAN, 80); texto(c, brl(d.por), x, yy + k * 0.82, `${peso || 800} ${k}px ${fam || MAN}`, p.ink, 'left'); yy += k * 0.82 + 24;
    if (desc) { const tx = 'Você economiza ' + brl(d.de - d.por) + '  (-' + d.desconto + '%)', k2 = encaixar(c, tx, l, 34, 600, DM, 22); texto(c, tx, x, yy + 40, `600 ${k2}px ${DM}`, p.forte, 'left'); yy += 60; }
    return yy - y;
  }
  function provaLinha(c, d, x, y, p) {
    if (!(d.nota > 0)) return 0; estrelas(c, x, y, 40, p.estrela, Math.round(d.nota));
    texto(c, d.nota.toFixed(1).replace('.', ','), x + 5 * 46 + 16, y + 34, `800 34px ${DM}`, p.ink, 'left');
    if (d.vendas > 0) texto(c, '· ' + vendidos(d.vendas), x + 5 * 46 + 16 + larg(c, d.nota.toFixed(1), `800 34px ${DM}`) + 14, y + 34, `500 30px ${DM}`, p.soft, 'left');
    return 50;
  }
  function passosCta(c, s, x, y, l, p, fam) {
    let yy = y; (s.passos || []).slice(0, 3).forEach((ps, k) => { texto(c, String(k + 1).padStart(2, '0'), x, yy + 34, `800 32px ${DM}`, p.forte, 'left'); const o = bloco(c, ps, { fonte: fam, x: x + 66, y: yy, larg: l - 66, alt: 96, max: 36, min: 26, peso: 500, cor: p.ink }); yy += Math.max(o.h, 46) + 20; });
    return yy - y;
  }

  // ======================================================================================
  // 1) VITRINE (Sephora / Away / Kate Farms): estúdio claro com luz no centro, produto solto
  //    com sombra de chão, títulos em Manrope. Limpo e "de loja".
  // ======================================================================================
  const FV = { titulo: MAN, peso: 800, corpo: DM, alta: false, escala: 1, lh: 1.04 };
  const palV = (t) => { const bg = mix(t.a, '#FFFFFF', 0.08); return { bg, luz: '#FFFFFF', ink: t.ink, soft: garante(mix(t.ink, bg, 0.7), bg, t.ink, 5.2), forte: garante(t.a, bg, t.ink, 5.2), risco: t.a, estrela: '#F2B01E', marca: mix(t.acc, bg, 0.6), botao: t.a, onBotao: sobre(t.a, t) }; };
  function fundoV(c, p) { c.fillStyle = p.bg; c.fillRect(0, 0, W, H); const g = c.createRadialGradient(W / 2, 640, 40, W / 2, 640, 760); g.addColorStop(0, 'rgba(255,255,255,0.85)'); g.addColorStop(1, 'rgba(255,255,255,0)'); c.fillStyle = g; c.fillRect(0, 0, W, H); }
  C.registrar('vitrine', { nome: 'Vitrine', premium: true, decor: false, fundo: (tipo, t) => palV(t).bg,
    moldura(c, f, t, d, i, n, ultimo) { G.fixo = true; try { const p = palV(t); fundoV(c, p); moldura(c, d, i, n, ultimo, p.ink); } finally { G.fixo = false; } },
    slides: {
      capa(c, s, t, f, d) { const p = palV(t);
        rotulo(c, s.selo || 'Achado da semana', W / 2, 228, p.forte, 'center');
        const o = bloco(c, s.titulo, { fonte: (f || FV), titulo: true, centro: true, x: M, y: 262, larg: W - 2 * M, alt: 250, max: 92, min: 52, cor: p.ink, marca: p.marca, corMarca: p.ink });
        const top = 262 + o.h + 40, b = produto(c, d, 170, top, W - 340, 1150 - top, { al: { x: 0.5, y: 1 } });
        if (temDesconto(d)) seloCircular(c, Math.min(W - M - 92, b.x + b.w + 30), Math.max(top + 92, b.y + 40), 92, 'Oferta', '-' + d.desconto + '%', p.botao, p.onBotao);
      },
      vantagens(c, s, t, f, d) { const p = palV(t);
        rotulo(c, s.rotulo || 'Por que vale a pena', M, 228, p.forte);
        const o = bloco(c, s.titulo, { fonte: (f || FV), titulo: true, x: M, y: 262, larg: W - 2 * M, alt: 220, max: 80, min: 48, cor: p.ink, marca: p.marca, corMarca: p.ink });
        let y = 262 + o.h + 56; const l = 520;
        (s.itens || []).slice(0, 4).forEach((it) => { check(c, M + 26, y + 26, 26, p.botao, p.onBotao); const q = bloco(c, it, { fonte: (f || FV), x: M + 74, y: y + 2, larg: l - 74, alt: 120, max: 40, min: 28, peso: 600, cor: p.ink }); y += Math.max(q.h, 56) + 34; });
        { const tp = Math.min(Math.max(y - 30, 262 + o.h + 30), 1180 - 340); produto(c, d, tp < y - 30 ? 680 : 220, tp, (tp < y - 30 ? W - 680 : W - 220) - 40, 1180 - tp, { al: { x: 1, y: 1 } }); }
      },
      detalhe(c, s, t, f, d) { const p = palV(t);
        rotulo(c, s.rotulo || 'De perto', M, 228, p.forte);
        const o = bloco(c, s.titulo, { fonte: (f || FV), titulo: true, x: M, y: 262, larg: W - 2 * M, alt: 190, max: 76, min: 46, cor: p.ink, marca: p.marca, corMarca: p.ink });
        const top = 262 + o.h + 30; let yt = top;
        if (s.texto) { const q = bloco(c, s.texto, { fonte: (f || FV), x: M, y: top, larg: W - 2 * M, alt: 110, max: 36, min: 28, peso: 500, cor: p.soft }); yt += q.h + 30; }
        const b = produto(c, d, M, yt, 560, 1180 - yt, { al: { x: 0, y: 1 } });
        const R = 190, cx = W - M - R - 10, cy = Math.max(yt + R + 20, Math.min(1180 - R - 10, b.y + b.h * 0.42));
        const [px, py] = pontoDetalhe(d, b); c.strokeStyle = p.ink; c.lineWidth = 3; c.setLineDash([2, 10]); c.lineCap = 'round'; c.beginPath(); c.moveTo(px, py); c.lineTo(cx - R * 0.94, cy + R * 0.3); c.stroke(); c.setLineDash([]);
        sem(() => { c.fillStyle = p.ink; c.beginPath(); c.arc(px, py, 8, 0, Math.PI * 2); c.fill(); });
        zoom(c, d, cx, cy, R, { fundo: p.bg });
      },
      anotado(c, s, t, f, d) { anotadoGenerico(c, s, d, palV(t), (f || FV), 'Repare nos detalhes'); },
      numeros(c, s, t, f, d) { numerosGenerico(c, s, d, palV(t), (f || FV), { fam: f ? f.titulo : MAN, peso: f ? f.peso : 800 }, 'Em números'); },
      preco(c, s, t, f, d) { const p = palV(t);
        const b = produto(c, d, 170, 180, W - 340, 500, { al: { x: 0.5, y: 1 } });
        const y0 = Math.max(b.y + b.h + 50, 720); rotulo(c, temDesconto(d) ? 'Preço de hoje' : 'Por apenas', M, y0, p.forte);
        const h = blocoPreco(c, d, M, y0 + 20, W - 2 * M, p); provaLinha(c, d, M, y0 + 20 + h + 20, p);
        texto(c, 'Preço visto hoje. Pode mudar a qualquer momento.', M, 1196, `500 24px ${DM}`, p.soft, 'left');
      },
      cta(c, s, t, f, d) { const p = palV(t);
        const o = bloco(c, s.titulo, { fonte: (f || FV), titulo: true, centro: true, x: M, y: 220, larg: W - 2 * M, alt: 200, max: 96, min: 52, cor: p.ink, marca: p.marca, corMarca: p.ink });
        const b = produto(c, d, 240, 220 + o.h + 30, W - 480, 470, { al: { x: 0.5, y: 1 } });
        const y = b.y + b.h + 60; const pw = larg(c, s.botao || 'LINK NA BIO', `700 36px ${DM}`) + 96;
        pilula(c, (W - pw) / 2, y, s.botao || 'LINK NA BIO', { fundo: p.botao, cor: p.onBotao, tam: 36, pad: 48 });
        if ((s.passos || []).length) { const tx = s.passos.join('  ·  '), kq = encaixar(c, tx, W - 2 * M, 30, 500, DM, 18); if (larg(c, tx, `500 ${kq}px ${DM}`) <= W - 2 * M) texto(c, tx, W / 2, y + 140, `500 ${kq}px ${DM}`, p.soft, 'center'); else s.passos.slice(0, 2).forEach((ps, k) => { const k2 = encaixar(c, ps, W - 2 * M, 30, 500, DM, 18); texto(c, ps, W / 2, y + 130 + k * 44, `500 ${k2}px ${DM}`, p.soft, 'center'); }); }
      },
    } });

  /** Slide "anotado" (Primally Pure): rótulos com linha fina apontando para a borda do produto. */
  /** Slide "anotado" (estilo Kate Farms): até 4 qualidades com check, em duas colunas, e o
   *  produto inteiro embaixo. Não aponta para partes da foto, então não depende de onde elas estão. */
  function anotadoGenerico(c, s, d, p, FT, padrao) {
    rotulo(c, s.rotulo || padrao, W / 2, 228, p.forte, 'center');
    const o = bloco(c, s.titulo, { fonte: FT, titulo: true, centro: true, x: M, y: 262, larg: W - 2 * M, alt: 170, max: 72, min: 44, cor: p.ink, marca: p.marca, corMarca: p.corMarca || p.ink });
    const rs = (s.rotulos || []).slice(0, 4), cw = (W - 2 * M - 40) / 2; let y = 262 + o.h + 46;
    for (let k = 0; k < rs.length; k += 2) {
      let h = 0;
      [0, 1].forEach((j) => { const r = rs[k + j]; if (!r) return; const x = M + j * (cw + 40);
        check(c, x + 22, y + 22, 22, p.botao, p.onBotao);
        const q = bloco(c, r, { fonte: FT, x: x + 60, y: y + 2, larg: cw - 60, alt: 84, max: 32, min: 24, peso: 700, cor: p.ink }); h = Math.max(h, q.h, 46); });
      y += h + 26;
    }
    const top = Math.min(y + 20, 1170 - 320);
    produto(c, d, 150, top, W - 300, 1170 - top, { al: { x: 0.5, y: 1 } });
  }
  /** Slide "Em números": 2 ou 3 dados grandes (valor + legenda) e o produto ao lado. */
  function numerosGenerico(c, s, d, p, FT, NUM, padrao) {
    rotulo(c, s.rotulo || padrao, M, 228, p.forte);
    const o = bloco(c, s.titulo, { fonte: FT, titulo: true, x: M, y: 262, larg: W - 2 * M, alt: 190, max: 76, min: 44, cor: p.ink, marca: p.marca, corMarca: p.corMarca || p.ink });
    const ns = (s.numeros || []).filter((n) => n && n.valor).slice(0, 3), y0 = 262 + o.h + 56, livre = 1180 - y0;
    const lh = Math.min(260, livre / Math.max(1, ns.length)), col = 520;
    ns.forEach((n, k) => { const y = y0 + k * lh, kv = encaixar(c, n.valor, col, Math.min(140, lh * 0.55), NUM.peso, NUM.fam, 40);
      texto(c, n.valor, M, y + kv * 0.82, `${NUM.peso} ${kv}px ${NUM.fam}`, p.forte, 'left');
      if (n.legenda) bloco(c, n.legenda, { fonte: FT, x: M, y: y + kv * 1.04 + 8, larg: col, alt: Math.max(36, lh - kv * 1.04 - 34), max: 32, min: 22, peso: 500, cor: p.soft });
      if (k < ns.length - 1) { c.strokeStyle = p.linha || 'rgba(0,0,0,0.14)'; c.lineWidth = 2; c.beginPath(); c.moveTo(M, y + lh - 16); c.lineTo(M + col, y + lh - 16); c.stroke(); } });
    produto(c, d, M + col + 30, y0 - 20, W - (M + col + 30) - 36, 1180 - (y0 - 20), { al: { x: 1, y: 1 } });
  }

  // ======================================================================================
  // 2) ANOTADO (Primally Pure): pedra quente, serifa fina, o produto com rótulos apontando
  //    para ele em quase todos os slides. Elegante e explicativo.
  // ======================================================================================
  const FA = { titulo: SERIF, peso: 400, corpo: DM, alta: false, escala: 1.3, lh: 1.0 };
  const palA = (t) => { const bg = '#ECE6DC'; return { bg, ink: '#2A241D', soft: garante('#6A5F52', bg, '#2A241D', 5.4), forte: garante(t.a, bg, '#2A241D', 5.6), risco: t.a, estrela: '#B8862B', marca: mix(t.acc, bg, 0.45), botao: '#2A241D', onBotao: '#FFFFFF' }; };
  C.registrar('anotado', { nome: 'Anotado', premium: true, decor: false, fundo: (tipo, t) => palA(t).bg,
    moldura(c, f, t, d, i, n, ultimo) { G.fixo = true; try { const p = palA(t); c.fillStyle = p.bg; c.fillRect(0, 0, W, H);
      const g = c.createLinearGradient(0, 0, 0, H); g.addColorStop(0, 'rgba(255,255,255,0.35)'); g.addColorStop(1, 'rgba(120,100,80,0.10)'); c.fillStyle = g; c.fillRect(0, 0, W, H); moldura(c, d, i, n, ultimo, p.ink); } finally { G.fixo = false; } },
    slides: {
      capa(c, s, t, f, d) { const p = palA(t);
        rotulo(c, s.selo || 'Achado da semana', W / 2, 228, p.forte, 'center');
        const o = bloco(c, s.titulo, { fonte: (f || FA), titulo: true, centro: true, x: M, y: 258, larg: W - 2 * M, alt: 300, max: 104, min: 56, cor: p.ink, marca: p.marca, corMarca: p.ink });
        const top = 258 + o.h + 40, b = produto(c, d, 200, top, W - 400, 1150 - top, { al: { x: 0.5, y: 1 } });
        if (temDesconto(d)) seloCircular(c, Math.min(W - M - 88, b.x + b.w + 20), Math.max(top + 90, b.y + 60), 88, 'Achado', '-' + d.desconto + '%', p.botao, p.onBotao);
      },
      anotado(c, s, t, f, d) { anotadoGenerico(c, s, d, palA(t), (f || FA), 'O que ele tem'); },
      numeros(c, s, t, f, d) { numerosGenerico(c, s, d, palA(t), (f || FA), { fam: f ? f.titulo : SERIF, peso: f ? f.peso : 400 }, 'Em números'); },
      vantagens(c, s, t, f, d) { const p = palA(t);
        rotulo(c, s.rotulo || 'Na prática', M, 228, p.forte);
        const o = bloco(c, s.titulo, { fonte: (f || FA), titulo: true, x: M, y: 258, larg: W - 2 * M, alt: 260, max: 96, min: 52, cor: p.ink, marca: p.marca, corMarca: p.ink });
        let y = 258 + o.h + 50; const l = 560;
        (s.itens || []).slice(0, 4).forEach((it, k) => { texto(c, String(k + 1).padStart(2, '0'), M, y + 40, `400 54px ${SERIF}`, p.forte, 'left');
          const q = bloco(c, it, { fonte: (f || FA), x: M + 84, y: y + 6, larg: l - 84, alt: 110, max: 38, min: 28, peso: 500, cor: p.ink }); c.strokeStyle = mix(p.ink, p.bg, 0.25); c.lineWidth = 1.5; const yl = y + Math.max(q.h, 60) + 18; c.beginPath(); c.moveTo(M, yl); c.lineTo(M + l, yl); c.stroke(); y = yl + 22; });
        { const tp = Math.min(Math.max(y - 20, 258 + o.h + 40), 1180 - 340); produto(c, d, tp < y - 20 ? 680 : 220, tp, (tp < y - 20 ? W - 680 : W - 220) - 40, 1180 - tp, { al: { x: 1, y: 1 } }); }
      },
      detalhe(c, s, t, f, d) { const p = palA(t);
        rotulo(c, s.rotulo || 'De perto', W / 2, 228, p.forte, 'center');
        const R = 300, cx = W / 2, cy = 640; const z = zoom(c, d, cx, cy, R, { fundo: p.bg, borda: '#FFFFFF' }); void z;
        const ot = bloco(c, s.titulo, { fonte: (f || FA), titulo: true, centro: true, x: M, y: cy + R + 50, larg: W - 2 * M, alt: s.texto ? 130 : 200, max: 72, min: 40, cor: p.ink, marca: p.marca, corMarca: p.ink });
        if (s.texto) bloco(c, s.texto, { fonte: (f || FA), centro: true, x: 140, y: cy + R + 50 + ot.h + 14, larg: W - 280, alt: 1196 - (cy + R + 50 + ot.h + 14), max: 32, min: 24, peso: 500, cor: p.soft });
      },
      preco(c, s, t, f, d) { const p = palA(t);
        const b = produto(c, d, M, 190, 420, 560, { al: { x: 0.5, y: 1 } });
        rotulo(c, 'Preço de hoje', 560, 300, p.forte);
        const h = blocoPreco(c, d, 560, 320, W - M - 560, p, SERIF, 400); void h; provaLinha(c, d, M, Math.max(b.y + b.h + 70, 820), p);
        if (d.nota > 0) bloco(c, s.prova || 'Quem comprou recomenda: nota alta e muita gente levando.', { fonte: (f || FA), titulo: true, x: M, y: Math.max(b.y + b.h + 70, 820) + 80, larg: W - 2 * M, alt: 200, max: 60, min: 40, cor: p.ink, marca: p.marca, corMarca: p.ink });
        texto(c, 'Preço visto hoje. Pode mudar a qualquer momento.', M, 1196, `500 24px ${DM}`, p.soft, 'left');
      },
      cta(c, s, t, f, d) { const p = palA(t);
        const o = bloco(c, s.titulo, { fonte: (f || FA), titulo: true, x: M, y: 230, larg: 460, alt: 360, max: 120, min: 60, cor: p.ink, marca: p.marca, corMarca: p.ink });
        let y = 230 + o.h + 40; y += passosCta(c, s, M, y, 440, p, (f || FA)) + 20;
        pilula(c, M, y, s.botao || 'LINK NA BIO', { fundo: p.botao, cor: p.onBotao, tam: 34, pad: 44 });
        produto(c, d, 560, 480, W - 560 - 40, 700, { al: { x: 1, y: 1 } });
      },
    } });

  // ======================================================================================
  // 3) ETIQUETA (Honest Greens / Lolavie): creme, manchas orgânicas na cor do tema, serifa
  //    elegante, etiqueta de preço inclinada e selo redondo com texto em volta.
  // ======================================================================================
  const FE = { titulo: SERIF, peso: 400, corpo: DM, alta: false, escala: 1.25, lh: 1.0 };
  const palE = (t) => { const bg = '#F4EEE1'; return { bg, ink: '#23201B', soft: garante('#6E665A', bg, '#23201B'), forte: garante(t.a, bg, '#23201B', 5.2), risco: t.a, estrela: '#D49A1E', marca: mix(t.acc, bg, 0.5), mancha: mix(t.a, bg, 0.85), mancha2: mix(t.acc, bg, 0.45), manchaClara: mix(t.a, bg, 0.16), botao: t.a, onBotao: sobre(t.a, t), tag: t.acc, onTag: sobre(t.acc, t) }; };
  function mancha(c, cx, cy, r, cor, semente) { // forma orgânica (blob) feita com curvas
    c.fillStyle = cor; c.beginPath(); const n = 7; const pts = [];
    for (let k = 0; k < n; k++) { const a = k / n * Math.PI * 2, q = r * (0.78 + 0.22 * Math.sin(semente * 3.1 + k * 1.7)); pts.push([cx + Math.cos(a) * q, cy + Math.sin(a) * q]); }
    for (let k = 0; k < n; k++) { const [x0, y0] = pts[k], [x1, y1] = pts[(k + 1) % n], mx = (x0 + x1) / 2, my = (y0 + y1) / 2; if (k === 0) c.moveTo(mx, my); else c.quadraticCurveTo(x0, y0, mx, my); }
    const [x0, y0] = pts[0], [x1, y1] = pts[1]; c.quadraticCurveTo(x0, y0, (x0 + x1) / 2, (y0 + y1) / 2); c.closePath(); c.fill();
  }
  C.registrar('etiqueta', { nome: 'Etiqueta', premium: true, decor: false, fundo: (tipo, t) => palE(t).bg,
    moldura(c, f, t, d, i, n, ultimo) { G.fixo = true; try { const p = palE(t); c.fillStyle = p.bg; c.fillRect(0, 0, W, H);
      const cantos = [[[W + 70, 560, 230], [W - 120, 1400, 250]], [[-90, 700, 220], [W + 40, 1380, 240]]][i % 2];
      cantos.forEach(([x, y, r], k) => mancha(c, x, y, r, k ? p.mancha2 : p.manchaClara, i + k)); moldura(c, d, i, n, ultimo, p.ink); } finally { G.fixo = false; } },
    slides: {
      capa(c, s, t, f, d) { const p = palE(t);
        rotulo(c, s.selo || 'Achado da semana', M, 228, p.forte);
        const o = bloco(c, s.titulo, { fonte: (f || FE), titulo: true, x: M, y: 258, larg: W - 2 * M - 40, alt: 300, max: 110, min: 58, cor: p.ink, marca: p.marca, corMarca: p.ink });
        const top = 258 + o.h + 30; sem(() => mancha(c, W / 2 + 40, top + (1150 - top) * 0.55, (1150 - top) * 0.46, p.mancha, 3));
        const b = produto(c, d, 190, top, W - 340, 1150 - top, { al: { x: 0.5, y: 1 } });
        etiqueta(c, M + 175, Math.min(1100, b.y + b.h - 80), 350, 160, -0.08, p.tag, p.onTag, temDesconto(d) ? '-' + d.desconto + '% hoje' : 'hoje', brl(d.por));
      },
      vantagens(c, s, t, f, d) { const p = palE(t);
        rotulo(c, s.rotulo || 'O que vem com ele', M, 228, p.forte);
        const o = bloco(c, s.titulo, { fonte: (f || FE), titulo: true, x: M, y: 258, larg: W - 2 * M, alt: 230, max: 96, min: 52, cor: p.ink, marca: p.marca, corMarca: p.ink });
        // chips como os ingredientes da Honest Greens
        let x = M, y = 258 + o.h + 34; const cores = [p.botao, p.tag, p.ink, mix(p.botao, '#000000', 0.7)];
        (s.itens || []).slice(0, 5).forEach((it, k) => { const fnt = `700 30px ${DM}`; let tx = it; while (larg(c, tx, fnt) > W - 2 * M - 60 && tx.length > 4) tx = tx.slice(0, -2); const w = larg(c, tx, fnt) + 52;
          if (x + w > W - M) { x = M; y += 76; } const bgc = cores[k % cores.length]; c.fillStyle = bgc; rr(c, x, y, w, 60, 30, 'pilula'); c.fill(); texto(c, tx, x + 26, y + 41, fnt, sobre(bgc, { ink: '#23201B' }), 'left'); x += w + 14; });
        const top = y + 110; produto(c, d, 160, top, W - 320, 1170 - top, { al: { x: 0.5, y: 1 } });
      },
      detalhe(c, s, t, f, d) { const p = palE(t);
        const R = 250, cx = W / 2 + 120, cy = 560; zoom(c, d, cx, cy, R, { fundo: p.bg });
        seloCircular(c, M + 110, 400, 110, s.selo || 'Detalhe que importa', '✦', p.botao, p.onBotao);
        bloco(c, s.titulo, { fonte: (f || FE), titulo: true, x: M, y: 880, larg: W - 2 * M, alt: 190, max: 84, min: 48, cor: p.ink, marca: p.marca, corMarca: p.ink });
        if (s.texto) bloco(c, s.texto, { fonte: (f || FE), x: M, y: 1080, larg: W - 2 * M, alt: 100, max: 34, min: 26, peso: 500, cor: p.soft });
      },
      anotado(c, s, t, f, d) { anotadoGenerico(c, s, d, palE(t), (f || FE), 'Repare'); },
      numeros(c, s, t, f, d) { numerosGenerico(c, s, d, palE(t), (f || FE), { fam: f ? f.titulo : SERIF, peso: f ? f.peso : 400 }, 'Em números'); },
      preco(c, s, t, f, d) { const p = palE(t);
        rotulo(c, 'Oferta de hoje', M, 228, p.forte);
        const b = produto(c, d, 420, 250, W - 420 - 50, 600, { al: { x: 0.5, y: 1 } });
        etiqueta(c, 290, Math.min(780, b.y + b.h - 80), 420, 190, -0.07, p.tag, p.onTag, temDesconto(d) ? 'de ' + brl(d.de) : 'por apenas', brl(d.por));
        let y = Math.max(b.y + b.h, 840) + 50; if (temDesconto(d)) { texto(c, 'Você economiza ' + brl(d.de - d.por), M, y + 40, `600 40px ${DM}`, p.ink, 'left'); y += 70; }
        provaLinha(c, d, M, y + 20, p);
        if (temDesconto(d)) seloCircular(c, W - M - 100, 1060, 100, 'Desconto', '-' + d.desconto + '%', p.botao, p.onBotao);
        texto(c, 'Preço visto hoje. Pode mudar.', M, 1196, `500 24px ${DM}`, p.soft, 'left');
      },
      cta(c, s, t, f, d) { const p = palE(t);
        const o = bloco(c, s.titulo, { fonte: (f || FE), titulo: true, x: M, y: 240, larg: W - 2 * M, alt: 240, max: 120, min: 60, cor: p.ink, marca: p.marca, corMarca: p.ink });
        let y = 240 + o.h + 40; y += passosCta(c, s, M, y, 560, p, (f || FE)) + 24;
        pilula(c, M, y, s.botao || 'LINK NA BIO', { fundo: p.botao, cor: p.onBotao, tam: 34, pad: 44 });
        produto(c, d, 480, 560, W - 480 - 40, 620, { al: { x: 1, y: 1 } });
      },
    } });

  // ======================================================================================
  // 4) FICHA (Facetheory / Kate Farms): fundo na cor forte, produto grande inclinado saindo
  //    pela borda, lista com linha e pontos, letra Sora.
  // ======================================================================================
  const FF = { titulo: SORA, peso: 800, corpo: DM, alta: false, escala: 0.84, lh: 1.08 };
  const palF = (t) => { const bg = mix(t.a, '#111111', razao(t.a, '#FFFFFF') >= 7 ? 0.82 : 0.66); return { bg, ink: '#FFFFFF', soft: garante('#D9D9D9', bg, '#FFFFFF', 6.2), forte: razao(bg, t.acc) >= 5.6 ? t.acc : '#FFFFFF', risco: t.acc, estrela: t.acc, marca: t.acc, corMarca: sobre(t.acc, t), botao: t.acc, onBotao: sobre(t.acc, t), linha: 'rgba(255,255,255,0.45)' }; };
  C.registrar('ficha', { nome: 'Ficha', premium: true, decor: false, fundo: (tipo, t) => palF(t).bg,
    moldura(c, f, t, d, i, n, ultimo) { G.fixo = true; try { const p = palF(t); c.fillStyle = p.bg; c.fillRect(0, 0, W, H);
      const g = c.createRadialGradient(W * 0.8, 520, 20, W * 0.8, 520, 700); g.addColorStop(0, 'rgba(255,255,255,0.16)'); g.addColorStop(1, 'rgba(255,255,255,0)'); c.fillStyle = g; c.fillRect(0, 0, W, H); moldura(c, d, i, n, ultimo, '#FFFFFF'); } finally { G.fixo = false; } },
    slides: {
      capa(c, s, t, f, d) { const p = palF(t);
        rotulo(c, s.selo || 'Achado da semana', M, 228, p.forte);
        bloco(c, s.titulo, { fonte: (f || FF), titulo: true, x: M, y: 262, larg: 460, alt: 520, max: 100, min: 52, cor: p.ink, marca: p.marca, corMarca: p.corMarca });
        const b = produto(c, d, 590, 300, 470, 760, { al: { x: 0.5, y: 0.5 }, rot: 0.1, tag: 'ponte', sombraProj: 0.45, chao: false });
        if (temDesconto(d)) { texto(c, '-' + d.desconto + '%', M, 1000, `800 140px ${SORA}`, p.forte, 'left'); texto(c, 'de ' + brl(d.de) + ' por ' + brl(d.por), M, 1062, `600 32px ${DM}`, p.soft, 'left'); }
        else { const kp = encaixar(c, brl(d.por), 460, 110, 800, SORA, 50); texto(c, brl(d.por), M, 1040, `800 ${kp}px ${SORA}`, p.forte, 'left'); }
        void b;
      },
      vantagens(c, s, t, f, d) { const p = palF(t);
        rotulo(c, s.rotulo || 'Feito para', M, 228, p.forte);
        const o = bloco(c, s.titulo, { fonte: (f || FF), titulo: true, x: M, y: 262, larg: 560, alt: 300, max: 80, min: 46, cor: p.ink, marca: p.marca, corMarca: p.corMarca });
        let y = 262 + o.h + 60; const ys = [];
        (s.itens || []).slice(0, 5).forEach((it) => { ys.push(y + 24); const q = bloco(c, it, { fonte: (f || FF), x: M + 56, y, larg: 440, alt: 100, max: 40, min: 28, peso: 700, cor: p.ink }); y += Math.max(q.h, 52) + 44; });
        if (ys.length) { c.strokeStyle = p.linha; c.lineWidth = 3; c.beginPath(); c.moveTo(M + 12, ys[0]); c.lineTo(M + 12, ys[ys.length - 1]); c.stroke(); sem(() => ys.forEach((yy) => { c.fillStyle = p.forte; c.beginPath(); c.arc(M + 12, yy, 12, 0, Math.PI * 2); c.fill(); })); }
        produto(c, d, 620, 340, 430, 780, { al: { x: 0.5, y: 0.5 }, rot: -0.08, tag: 'ponte', sombraProj: 0.45, chao: false });
      },
      detalhe(c, s, t, f, d) { const p = palF(t);
        rotulo(c, s.rotulo || 'Olha esse detalhe', M, 228, p.forte);
        const o = bloco(c, s.titulo, { fonte: (f || FF), titulo: true, x: M, y: 262, larg: W - 2 * M, alt: 220, max: 76, min: 44, cor: p.ink, marca: p.marca, corMarca: p.corMarca });
        const R = 260, cy = Math.max(262 + o.h + 40 + R, 640); zoom(c, d, W / 2, cy, R, { fundo: mix(p.bg, '#FFFFFF', 0.9), borda: p.forte });
        if (s.texto) bloco(c, s.texto, { fonte: (f || FF), centro: true, x: 120, y: cy + R + 40, larg: W - 240, alt: 120, max: 36, min: 26, peso: 500, cor: p.soft });
      },
      anotado(c, s, t, f, d) { anotadoGenerico(c, s, d, Object.assign({}, palF(t), { ink: '#FFFFFF', bg: palF(t).bg }), (f || FF), 'Em detalhes'); },
      numeros(c, s, t, f, d) { numerosGenerico(c, s, d, Object.assign({}, palF(t), { linha: 'rgba(255,255,255,0.25)' }), (f || FF), { fam: f ? f.titulo : SORA, peso: f ? f.peso : 800 }, 'Em números'); },
      preco(c, s, t, f, d) { const p = palF(t);
        rotulo(c, 'Preço de hoje', M, 228, p.forte);
        const h = blocoPreco(c, d, M, 260, 600, p, SORA, 800); provaLinha(c, d, M, 260 + h + 30, p);
        const yb = 260 + h + 110; produto(c, d, 440, yb, 620, 1180 - yb, { al: { x: 0.5, y: 0.5 }, rot: 0.08, tag: 'ponte', sombraProj: 0.45, chao: false });
        texto(c, 'Preço visto hoje. Pode mudar.', M, 1196, `500 24px ${DM}`, p.soft, 'left');
      },
      cta(c, s, t, f, d) { const p = palF(t);
        const o = bloco(c, s.titulo, { fonte: (f || FF), titulo: true, x: M, y: 250, larg: 500, alt: 330, max: 110, min: 56, cor: p.ink, marca: p.marca, corMarca: p.corMarca });
        let y = 250 + o.h + 50; y += passosCta(c, s, M, y, 480, p, (f || FF)) + 24;
        pilula(c, M, y, s.botao || 'LINK NA BIO', { fundo: p.botao, cor: p.onBotao, tam: 34, pad: 44 });
        produto(c, d, 600, 560, 440, 600, { al: { x: 0.5, y: 0.5 }, rot: -0.08, tag: 'ponte', sombraProj: 0.45, chao: false });
      },
    } });
  // ======================================================================================
  // SEM FOTO (Premium): a pessoa pode tirar a foto de qualquer slide. O texto do slide é
  // reorganizado em blocos empilhados, na posição (topo, meio, base) e no alinhamento
  // (esquerda, centro) que ela escolher. Cada bloco é medido antes num canvas à parte.
  // ======================================================================================
  let rascunho = null;
  function medir(fn) {
    if (!rascunho) { rascunho = document.createElement('canvas'); rascunho.width = W; rascunho.height = H; }
    const k = rascunho.getContext('2d'), salvo = { forma: G.forma, bloco: G.bloco, decor: G.decor };
    G.forma = G.bloco = G.decor = null; // a medição não entra na auditoria
    try { k.clearRect(0, 0, W, H); return fn(k, 0); } finally { Object.assign(G, salvo); }
  }
  function semFotoGenerico(c, s, d, p, FT, NUM) {
    const centro = s.alinhar === 'centro', xa = centro ? W / 2 : M, al = centro ? 'center' : 'left', L = W - 2 * M;
    const blocos = [];
    const rot = (txt) => blocos.push((k, y) => { rotulo(k, txt, xa, y + 22, p.forte, al); return 30; });
    const tit = (txt, max, min, alt) => blocos.push((k, y) => bloco(k, txt, { fonte: FT, titulo: true, centro, x: M, y, larg: L, alt, max, min, cor: p.ink, marca: p.marca, corMarca: p.corMarca || p.ink }).h);
    const linha = (txt, fonte, cor) => blocos.push((k, y) => { const tam = parseFloat(fonte.match(/(\d+)px/)[1]), kk = encaixar(k, txt, L, tam, fonte.split(' ')[0], fonte.replace(/^\S+ \d+px /, ''), 20);
      texto(k, txt, xa, y + kk * 0.82, fonte.replace(/\d+px/, kk + 'px'), cor, al); return kk * 1.1; });
    const lista = (itens) => (itens || []).filter(Boolean).slice(0, 5).forEach((it) => blocos.push((k, y) => {
      const kk = encaixar(k, it, L - 70, 42, 700, DM, 26), w = larg(k, it, `700 ${kk}px ${DM}`), x0 = centro ? (W - (w + 64)) / 2 : M;
      check(k, x0 + 22, y + kk * 0.5, 22, p.botao, p.onBotao); texto(k, it, x0 + 64, y + kk * 0.86, `700 ${kk}px ${DM}`, p.ink, 'left'); return Math.max(kk * 1.15, 50); }));
    const numeros = (ns) => (ns || []).filter((n) => n && n.valor).slice(0, 3).forEach((n) => blocos.push((k, y) => {
      const kv = encaixar(k, n.valor, L, 150, NUM.peso, NUM.fam, 50); texto(k, n.valor, xa, y + kv * 0.82, `${NUM.peso} ${kv}px ${NUM.fam}`, p.forte, al);
      let h = kv * 1.02; if (n.legenda) { const kl = encaixar(k, n.legenda, L, 34, 500, DM, 22); texto(k, n.legenda, xa, y + h + kl, `500 ${kl}px ${DM}`, p.soft, al); h += kl * 1.5; } return h; }));
    const preco = () => blocos.push((k, y) => { const desc = temDesconto(d); let yy = y;
      if (desc) { const f = `500 52px ${DM}`, tx = 'de ' + brl(d.de), w = larg(k, tx, f), x0 = centro ? (W - w) / 2 : M; texto(k, tx, x0, yy + 44, f, p.soft, 'left');
        k.strokeStyle = p.risco; k.lineWidth = 4; k.beginPath(); k.moveTo(x0 + larg(k, 'de ', f) - 4, yy + 26); k.lineTo(x0 + w + 4, yy + 26); k.stroke(); yy += 74; }
      const kp = encaixar(k, brl(d.por), L, 210, NUM.peso, NUM.fam, 80); texto(k, brl(d.por), xa, yy + kp * 0.82, `${NUM.peso} ${kp}px ${NUM.fam}`, p.ink, al); yy += kp * 0.82 + 24;
      if (desc) { const tx = 'Você economiza ' + brl(d.de - d.por) + '  (-' + d.desconto + '%)', k2 = encaixar(k, tx, L, 36, 600, DM, 22); texto(k, tx, xa, yy + 40, `600 ${k2}px ${DM}`, p.forte, al); yy += 60; }
      return yy - y; });
    const prova = () => { if (!(d.nota > 0)) return; blocos.push((k, y) => { const nt = d.nota.toFixed(1).replace('.', ','), extra = d.vendas > 0 ? '  ·  ' + vendidos(d.vendas) : '';
      const wt = larg(k, nt + extra, `700 32px ${DM}`), w = 5 * 46 + 16 + wt, x0 = centro ? (W - w) / 2 : M;
      estrelas(k, x0, y, 40, p.estrela, Math.round(d.nota)); texto(k, nt + extra, x0 + 5 * 46 + 16, y + 34, `700 32px ${DM}`, p.ink, 'left'); return 50; }); };
    const passos = (ps) => (ps || []).slice(0, 3).forEach((ps1, i) => blocos.push((k, y) => { const tx = String(i + 1).padStart(2, '0') + '   ' + ps1, kk = encaixar(k, tx, L, 38, 500, DM, 24);
      texto(k, tx, xa, y + kk * 0.86, `500 ${kk}px ${DM}`, p.ink, al); return kk * 1.3; }));
    const botao = (txt) => blocos.push((k, y) => { const w = larg(k, txt, `700 36px ${DM}`) + 96; pilula(k, centro ? (W - w) / 2 : M, y, txt, { fundo: p.botao, cor: p.onBotao, tam: 36, pad: 48 }); return 66; });
    const espaco = (h) => blocos.push(() => h);
    switch (s.tipo) {
      case 'capa': rot(s.selo || 'Achado da semana'); espaco(18); tit(s.titulo, 140, 64, 560); espaco(44);
        if (temDesconto(d)) { linha('-' + d.desconto + '%', `${NUM.peso} 150px ${NUM.fam}`, p.forte); linha('de ' + brl(d.de) + '  por ' + brl(d.por), `600 40px ${DM}`, p.ink); }
        else linha('por ' + brl(d.por), `${NUM.peso} 110px ${NUM.fam}`, p.forte); break;
      case 'vantagens': case 'anotado': rot(s.rotulo || (s.tipo === 'vantagens' ? 'Por que vale a pena' : 'Em detalhes')); espaco(18); tit(s.titulo, 104, 52, 340); espaco(44); lista(s.tipo === 'vantagens' ? s.itens : s.rotulos); break;
      case 'numeros': rot(s.rotulo || 'Em números'); espaco(18); tit(s.titulo, 96, 48, 260); espaco(40); numeros(s.numeros); break;
      case 'preco': rot(temDesconto(d) ? 'Preço de hoje' : 'Por apenas'); espaco(16); preco(); espaco(20); prova(); break;
      case 'cta': tit(s.titulo, 150, 64, 380); espaco(44); passos(s.passos); espaco(30); botao(s.botao || 'LINK NA BIO'); break;
      default: tit(s.titulo || '', 110, 52, 400);
    }
    // mede e encaixa na área útil (entre o topo e o rodapé fixos), juntando os espaços se faltar lugar
    const topo = 196, base = s.tipo === 'preco' ? 1150 : 1180, alturas = blocos.map((b) => medir(b)), soma = alturas.reduce((a, b) => a + b, 0);
    const gap = Math.max(10, Math.min(26, (base - topo - soma) / Math.max(1, blocos.length - 1)));
    const total = soma + gap * (blocos.length - 1), pos = s.posicao || 'meio';
    let y = pos === 'topo' ? topo + 30 : pos === 'base' ? base - total : topo + (base - topo - total) / 2;
    y = Math.max(topo, Math.min(y, base - total)); blocos.forEach((b, i) => { b(c, y); y += alturas[i] + gap; });
    if (s.tipo === 'preco') texto(c, 'Preço visto hoje. Pode mudar a qualquer momento.', xa, 1196, `500 24px ${DM}`, p.soft, al);
  }
  [['vitrine', palV, FV, MAN, 800], ['anotado', palA, FA, SERIF, 400], ['etiqueta', palE, FE, SERIF, 400], ['ficha', palF, FF, SORA, 800]].forEach(([nome, pal, FX, fam, peso]) => {
    const m = C.MODELOS[nome];
    Object.keys(m.slides).forEach((tipo) => { const orig = m.slides[tipo];
      m.slides[tipo] = function (c, s, t, f, d, img, info) { if (!s.semFoto) return orig.call(this, c, s, t, f, d, img, info);
        semFotoGenerico(c, s, d, pal(t), f || FX, { fam: f ? f.titulo : fam, peso: f ? f.peso : peso }); }; });
  });
})();
