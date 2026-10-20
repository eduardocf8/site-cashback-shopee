/* Modelos de carrossel do Appfiliado (protótipo).
 * Cada modelo é uma linguagem visual própria (tipografia, formas, fundo e composição), não só
 * outra cor. Todos usam o mesmo desenhista (carrossel.js) e passam pela mesma auditoria.
 * Por enquanto cada modelo tem capa, produto e preço; os demais tipos de slide caem no Destaque. */
(function () {
  const C = window.Carrossel, U = C.util;
  const { W, H, M, G, rr, bloco, pilula, selo, estrelas, seta, cabe, brl, rgba, sobre, razao, fixo, temDesconto } = U;
  const DM = '"DM Sans"', PF = '"Playfair Display"', BB = '"Bebas Neue"', MONO = '"JetBrains Mono"';
  const reg = (c, x, y, w, h, tag) => { if (G.forma) G.forma(c, x, y, w, h, tag); };
  const sem = (fn) => { const s = G.ignorarArc; G.ignorarArc = true; try { fn(); } finally { G.ignorarArc = s; } }; // círculos já registrados à mão
  const sombraTxt = (fn) => { G.ignorarTexto = true; try { fn(); } finally { G.ignorarTexto = false; } };
  const hex = (h) => { const n = parseInt(h.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; };
  const mix = (a, b, p) => { const x = hex(a), y = hex(b); return '#' + [0, 1, 2].map((k) => Math.round(x[k] * p + y[k] * (1 - p)).toString(16).padStart(2, '0')).join(''); };
  const F_SERIF = { titulo: PF, peso: 900, corpo: DM, alta: false, escala: 0.92, lh: 1.08 };
  const F_BEBAS = { titulo: BB, peso: 400, corpo: DM, alta: true, escala: 1.34, lh: 1.1 };

  /** Foto em "cover" dentro do retângulo, com zoom e ponto de foco (0..1). */
  function fotoZoom(c, img, x, y, w, h, r, zoom, fx, fy) {
    fy = (fy == null || fy === 0.5) ? 0.42 : fy; // recortes largos preservam um pouco mais o topo do produto
    c.save(); c.beginPath(); c.roundRect(x, y, w, h, r); c.clip();
    const s = Math.max(w / img.width, h / img.height) * (zoom || 1), iw = img.width * s, ih = img.height * s;
    const ox = Math.min(0, Math.max(w - iw, w / 2 - iw * (fx == null ? 0.5 : fx))), oy = Math.min(0, Math.max(h - ih, h / 2 - ih * (fy == null ? 0.5 : fy)));
    c.drawImage(img, x + ox, y + oy, iw, ih); c.restore();
  }
  const curto = (n, max) => { let out = ''; for (const w of (n || '').split(/\s+/)) { if ((out + ' ' + w).trim().length > max) break; out = (out + ' ' + w).trim(); } return out || (n || '').split(/\s+/)[0] || ''; };
  const texto = (c, txt, x, y, font, cor, al, esp) => { c.font = font; c.fillStyle = cor; c.textAlign = al || 'left'; c.textBaseline = 'alphabetic'; c.letterSpacing = esp || '0px'; c.fillText(txt, x, y); c.letterSpacing = '0px'; };
  const encaixar = (c, txt, larg, tam, peso, fam, min) => { let k = tam; c.font = `${peso} ${k}px ${fam}`; while (c.measureText(txt).width > larg && k > (min || 24)) { k -= 3; c.font = `${peso} ${k}px ${fam}`; } return k; };
  const burst = (c, cx, cy, R, pontas, fundo) => { c.fillStyle = fundo; c.beginPath(); for (let i = 0; i < pontas * 2; i++) { const a = i * Math.PI / pontas, r = i % 2 ? R * 0.9 : R; c.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r); } c.closePath(); c.fill(); };

  // ======================================================================================
  // 1) EDITORIAL (padrão): revista elegante, papel claro, letra com serifa, filetes finos
  // ======================================================================================
  const ac = (t) => (razao(t.b, t.a) >= 3 ? t.a : t.ink);
  C.registrar('editorial', { nome: 'Editorial', premium: false, decor: false, fundo: (tipo, t) => t.b,
    moldura(c, fundo, t, d, i, n, ultimo) { G.fixo = true; try {
      c.fillStyle = t.b; c.fillRect(0, 0, W, H);
      texto(c, d.arroba.toUpperCase().slice(0, 30), M, 120, `700 24px ${DM}`, t.ink, 'left', '5px');
      texto(c, 'Nº ' + String(i + 1).padStart(2, '0'), W - M, 122, `italic 800 36px ${PF}`, t.ink, 'right');
      c.fillStyle = t.ink; c.fillRect(M, 150, W - 2 * M, 4); c.fillRect(M, 160, W - 2 * M, 1.5);
      c.fillRect(M, 1240, W - 2 * M, 1.5);
      if (!ultimo) { texto(c, 'ARRASTA', M, 1292, `700 22px ${DM}`, t.ink, 'left', '5px'); seta(c, M + 190, 1286, 44, t.ink, 4); }
      texto(c, String(i + 1).padStart(2, '0') + ' / ' + String(n).padStart(2, '0'), W - M, 1296, `italic 800 32px ${PF}`, t.ink, 'right');
    } finally { G.fixo = false; } },
    slides: {
      capa(c, s, t, f, d, img) {
        const a = ac(t); texto(c, (s.selo || 'ACHADO DA SEMANA').toUpperCase(), M, 222, `800 26px ${DM}`, a, 'left', '6px');
        bloco(c, s.titulo, { fonte: F_SERIF, titulo: true, x: M, y: 250, larg: W - 2 * M, alt: 300, max: 118, min: 66, cor: t.ink, marca: mix(a, t.b, 0.4), corMarca: t.ink });
        const w = 560, h = 590, x = (W - w) / 2, y = 600, r = w / 2;
        sem(() => { c.save(); c.strokeStyle = t.ink; c.lineWidth = 3; c.beginPath(); c.moveTo(x - 14, y + h); c.lineTo(x - 14, y + r); c.arc(x + r, y + r, r + 14, Math.PI, 0); c.lineTo(x + w + 14, y + h); c.stroke(); c.restore(); });
        reg(c, x - 14, y - 14, w + 28, h + 14, 'foto');
        sem(() => { c.save(); c.beginPath(); c.moveTo(x, y + h); c.lineTo(x, y + r); c.arc(x + r, y + r, r, Math.PI, 0); c.lineTo(x + w, y + h); c.closePath(); c.clip();
        const sc = Math.max(w / img.width, h / img.height); c.drawImage(img, x + (w - img.width * sc) / 2, y + (h - img.height * sc) / 2, img.width * sc, img.height * sc); c.restore(); });
        const cx = x + w - 6, cy = y + h - 118, R = 104; reg(c, cx - R, cy - R, 2 * R, 2 * R, 'selo'); c.fillStyle = t.a; sem(() => { c.beginPath(); c.arc(cx, cy, R, 0, 7); c.fill(); });
        const cs = sobre(t.a, t); texto(c, 'POR', cx, cy - 26, `700 22px ${DM}`, cs, 'center', '5px'); const k = encaixar(c, brl(d.por), R * 1.7, 46, 800, DM); texto(c, brl(d.por), cx, cy + 24, `800 ${k}px ${DM}`, cs, 'center');
      },
      produto(c, s, t, f, d, img) {
        const a = ac(t); texto(c, (s.rotulo || 'CONHEÇA').toUpperCase(), M, 222, `800 26px ${DM}`, a, 'left', '6px');
        const x = M, y = 262, w = W - 2 * M, h = 590; c.strokeStyle = t.ink; c.lineWidth = 3; c.strokeRect(x - 14, y - 14, w + 28, h + 28); reg(c, x - 14, y - 14, w + 28, h + 28, 'foto');
        fotoZoom(c, img, x, y, w, h, 4, 1, 0.5, 0.5);
        bloco(c, s.titulo, { fonte: F_SERIF, titulo: true, x: M, y: 905, larg: W - 2 * M, alt: 150, max: 66, min: 40, cor: t.ink, marca: mix(a, t.b, 0.4), corMarca: t.ink });
        c.fillStyle = t.ink; c.fillRect(M, 1090, W - 2 * M, 1.5);
        c.font = `700 24px ${DM}`; c.letterSpacing = '3px'; const chips = cabe(c, (s.chips || []).join('   ·   ').toUpperCase(), W - 2 * M); c.letterSpacing = '0px';
        texto(c, chips, M, 1146, `700 24px ${DM}`, rgba(t.ink, 0.85), 'left', '3px');
      },
      preco(c, s, t, f, d) {
        const a = ac(t), desc = temDesconto(d);
        if (desc) { texto(c, 'de ' + brl(d.de), M, 380, `italic 700 62px ${PF}`, rgba(t.ink, 0.72), 'left'); c.font = `italic 700 62px ${PF}`; const w = c.measureText('de ' + brl(d.de)).width;
          c.strokeStyle = t.ink; c.lineWidth = 4; c.beginPath(); c.moveTo(M - 6, 358); c.lineTo(M + w + 6, 354); c.stroke();
          const cx = W - M - 112, cy = 370, R = 108; reg(c, cx - R, cy - R, 2 * R, 2 * R, 'selo'); c.strokeStyle = a; c.lineWidth = 8; sem(() => { c.beginPath(); c.arc(cx, cy, R, 0, 7); c.stroke(); });
          texto(c, '-' + d.desconto + '%', cx, cy + 20, `800 58px ${DM}`, t.ink, 'center'); }
        texto(c, desc ? 'AGORA POR APENAS' : 'POR APENAS', M, 640, `800 26px ${DM}`, a, 'left', '6px');
        const k = encaixar(c, brl(d.por), W - 2 * M, 250, 900, PF, 80); texto(c, brl(d.por), M, 640 + k * 0.92, `900 ${k}px ${PF}`, t.ink, 'left');
        c.fillStyle = t.ink; c.fillRect(M, 950, W - 2 * M, 1.5);
        if (desc) texto(c, 'Você economiza ' + brl(d.de - d.por), M, 1050, `italic 800 54px ${PF}`, t.ink, 'left');
        texto(c, 'Preço visto hoje. Valores podem mudar a qualquer momento.', M, desc ? 1135 : 1000, `500 26px ${DM}`, rgba(t.ink, 0.8), 'left');
      },
    } });

  // ======================================================================================
  // 2) PROMO (padrão): encarte de oferta, cor forte, letra de cartaz, faixas e explosões
  // ======================================================================================
  C.registrar('promo', { nome: 'Promo', premium: false, decor: false, fundo: (tipo, t) => t.a,
    moldura(c, fundo, t, d, i, n, ultimo) { G.fixo = true; try {
      const on = sobre(t.a, t); c.fillStyle = t.a; c.fillRect(0, 0, W, H);
      c.save(); c.strokeStyle = rgba(on, 0.07); c.lineWidth = 30; for (let k = -6; k < 20; k++) { c.beginPath(); c.moveTo(k * 110, H + 40); c.lineTo(k * 110 + 700, -40); c.stroke(); } c.restore();
      c.fillStyle = t.acc; c.fillRect(0, 64, W, 84); c.save(); c.beginPath(); c.rect(0, 64, W, 84); c.clip();
      c.font = `400 52px ${BB}`; let faixa = 'OFERTA'; while (c.measureText(faixa + '  //  IMPERDÍVEL').width < W - 2 * M) { faixa += '  //  IMPERDÍVEL'; if (c.measureText(faixa + '  //  OFERTA').width < W - 2 * M) faixa += '  //  OFERTA'; else break; }
      texto(c, faixa, W / 2, 125, `400 52px ${BB}`, t.ink, 'center'); c.restore();
      c.fillStyle = t.ink; c.fillRect(0, 1262, W, 88);
      if (!ultimo) texto(c, 'ARRASTA  >>>', M, 1322, `400 50px ${BB}`, t.acc, 'left');
      texto(c, d.arroba, W / 2 + 40, 1318, `700 26px ${DM}`, '#FFFFFF', 'center');
      texto(c, String(i + 1) + '/' + n, W - M, 1322, `400 50px ${BB}`, '#FFFFFF', 'right');
    } finally { G.fixo = false; } },
    slides: {
      capa(c, s, t, f, d, img) {
        const on = sobre(t.a, t);
        bloco(c, s.titulo, { fonte: F_BEBAS, titulo: true, x: M, y: 190, larg: W - 2 * M, alt: 270, max: 150, min: 84, cor: on, marca: t.acc, corMarca: t.ink, contorno: on === '#FFFFFF' ? 'rgba(0,0,0,0.28)' : null });
        const cx = W / 2, cy = 850, R = 360; reg(c, cx - R, cy - R, 2 * R, 2 * R, 'forma'); burst(c, cx, cy, R, 18, t.acc);
        const pr = 255, py = 835; reg(c, cx - pr, py - pr, 2 * pr, 2 * pr, 'foto'); sem(() => { c.fillStyle = '#FFFFFF'; c.beginPath(); c.arc(cx, py, pr, 0, 7); c.fill();
        c.save(); c.beginPath(); c.arc(cx, py, pr - 16, 0, 7); c.clip(); const sc = Math.max(2 * (pr - 16) / img.width, 2 * (pr - 16) / img.height); c.drawImage(img, cx - img.width * sc / 2, py - img.height * sc / 2, img.width * sc, img.height * sc); c.restore(); });
        if (temDesconto(d)) selo(c, W - 196, 560, 118, '-' + d.desconto + '%', t.ink, t.acc, 0.18);
        const txt = 'POR APENAS ' + brl(d.por); const k = encaixar(c, txt, 640, 76, 400, BB); const w = c.measureText(txt).width + 70;
        c.fillStyle = t.ink; rr(c, (W - w) / 2, 1112, w, 84, 14, 'pilula'); c.fill(); texto(c, txt, W / 2, 1112 + 62, `400 ${k}px ${BB}`, '#FFFFFF', 'center');
      },
      produto(c, s, t, f, d, img) {
        const on = sobre(t.a, t);
        bloco(c, s.titulo, { fonte: F_BEBAS, titulo: true, x: M, y: 190, larg: W - 2 * M, alt: 230, max: 118, min: 66, cor: on, marca: t.acc, corMarca: t.ink, contorno: on === '#FFFFFF' ? 'rgba(0,0,0,0.28)' : null });
        let x = M; c.font = `400 40px ${BB}`; (s.chips || []).slice(0, 3).forEach((ch) => { ch = cabe(c, ch.toUpperCase(), 280); const w = c.measureText(ch).width + 44; if (x + w > W - M) return;
          c.fillStyle = t.ink; rr(c, x, 446, w, 58, 29, 'pilula'); c.fill(); texto(c, ch, x + 22, 490, `400 40px ${BB}`, t.acc, 'left'); x += w + 14; });
        const cx = W / 2, cy = 870, R = 340; reg(c, cx - R, cy - R, 2 * R, 2 * R, 'forma'); burst(c, cx, cy, R, 16, t.acc);
        const w = 540, h = 540; c.save(); c.translate(cx, cy - 6); c.rotate(0.035); c.translate(-w / 2, -h / 2);
        c.fillStyle = t.ink; rr(c, 18, 20, w, h, 36, 'int'); c.fill(); c.fillStyle = '#FFFFFF'; rr(c, 0, 0, w, h, 36, 'foto'); c.fill(); fotoZoom(c, img, 12, 12, w - 24, h - 24, 26, 1, 0.5, 0.5); c.restore();
      },
      preco(c, s, t, f, d) {
        const on = sobre(t.a, t), desc = temDesconto(d);
        if (desc) { c.font = `400 120px ${BB}`; const de = 'DE ' + brl(d.de); texto(c, de, M, 330, `400 120px ${BB}`, rgba(on, 0.85), 'left'); const w = c.measureText(de).width; c.strokeStyle = t.ink; c.lineWidth = 12; c.lineCap = 'round'; c.beginPath(); c.moveTo(M - 10, 295); c.lineTo(M + w + 10, 280); c.stroke();
          selo(c, W - 200, 340, 140, '-' + d.desconto + '%', t.acc, t.ink, 0.18); }
        texto(c, 'POR APENAS', M, desc ? 470 : 360, `400 96px ${BB}`, razao(t.a, t.acc) >= 3 ? t.acc : on, 'left');
        const k = encaixar(c, brl(d.por), W - 2 * M - 20, 400, 400, BB, 120), by = (desc ? 470 : 360) + k * 0.86 + 40;
        sombraTxt(() => texto(c, brl(d.por), M + 12, by + 12, `400 ${k}px ${BB}`, t.ink, 'left')); texto(c, brl(d.por), M, by, `400 ${k}px ${BB}`, razao(t.a, t.acc) >= 3 ? t.acc : '#FFFFFF', 'left');
        if (desc) { c.save(); c.translate(W / 2, 1090); c.rotate(-0.03); c.fillStyle = t.ink; rr(c, -440, -62, 880, 124, 18, 'cartao'); c.fill(); texto(c, 'ECONOMIZE ' + brl(d.de - d.por), 0, 28, `400 84px ${BB}`, t.acc, 'center'); c.restore(); }
        else texto(c, 'Preço visto hoje. Valores podem mudar.', M, 1100, `600 28px ${DM}`, on, 'left');
      },
    } });

  // ======================================================================================
  // 3) NEON / VIDRO (premium): fundo escuro com brilho, cartões de vidro, números luminosos
  // ======================================================================================
  const vidro = (c, x, y, w, h, r, tag) => { c.fillStyle = 'rgba(255,255,255,0.07)'; rr(c, x, y, w, h, r, tag); c.fill(); c.strokeStyle = 'rgba(255,255,255,0.2)'; c.lineWidth = 2; rr(c, x, y, w, h, r, 'int'); c.stroke(); };
  const BR = '#FFFFFF', BR2 = 'rgba(255,255,255,0.86)';
  C.registrar('neon', { nome: 'Neon', premium: true, decor: false, fundo: () => '#0A0E14',
    moldura(c, fundo, t, d, i, n, ultimo) { G.fixo = true; try {
      c.fillStyle = '#0A0E14'; c.fillRect(0, 0, W, H);
      [[160, 240, 560, t.a, 0.6], [W - 100, H - 300, 620, mix(t.a, '#FFFFFF', 0.3), 0.38], [W - 200, 120, 360, t.a, 0.25]].forEach(([x, y, r, col, a]) => { const g = c.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, rgba(col, a)); g.addColorStop(1, rgba(col, 0)); c.fillStyle = g; c.fillRect(0, 0, W, H); });
      c.strokeStyle = 'rgba(255,255,255,0.35)'; c.lineWidth = 2.5; sem(() => { c.beginPath(); c.arc(M + 34, 112, 34, 0, 7); c.stroke(); });
      texto(c, (d.arroba.replace('@', '')[0] || 'A').toUpperCase(), M + 34, 124, `800 34px ${DM}`, BR, 'center');
      c.font = `700 31px ${DM}`; const w = c.measureText('00 / 00').width + 48; texto(c, cabe(c, d.arroba, W - 2 * M - 86 - w - 30), M + 86, 122, `700 31px ${DM}`, BR, 'left');
      const tx = String(i + 1).padStart(2, '0') + ' / ' + String(n).padStart(2, '0'); c.strokeStyle = 'rgba(255,255,255,0.3)'; c.lineWidth = 2.5; rr(c, W - M - w, 82, w, 60, 30, 'pilula'); c.stroke(); texto(c, tx, W - M - w / 2, 121, `700 28px ${DM}`, BR, 'center');
      const sw = (W - 2 * M - (n - 1) * 10) / n; for (let k = 0; k < n; k++) { c.fillStyle = k === i ? t.acc : 'rgba(255,255,255,0.22)'; if (k === i) { c.shadowColor = t.acc; c.shadowBlur = 18; } rr(c, M + k * (sw + 10), 1296, sw, 8, 4, 'int'); c.fill(); c.shadowBlur = 0; }
      if (!ultimo) texto(c, 'Arrasta  →', M, 1262, `700 28px ${DM}`, BR2, 'left');
    } finally { G.fixo = false; } },
    slides: {
      capa(c, s, t, f, d, img) {
        pilula(c, M, 186, s.selo || 'ACHADO DA SEMANA', { fundo: t.acc, cor: sobre(t.acc, t), tam: 28 });
        vidro(c, M, 272, W - 2 * M, 660, 52, 'foto'); fotoZoom(c, img, M + 18, 290, W - 2 * M - 36, 624, 38, 1, 0.5, 0.5);
        if (temDesconto(d)) { const cx = W - M - 70, cy = 290, R = 104; reg(c, cx - R, cy - R, 2 * R, 2 * R, 'selo'); c.save(); c.shadowColor = t.acc; c.shadowBlur = 36; c.fillStyle = '#0A0E14'; sem(() => { c.beginPath(); c.arc(cx, cy, R, 0, 7); c.fill(); c.strokeStyle = t.acc; c.lineWidth = 8; c.stroke(); }); c.restore();
          texto(c, '-' + d.desconto + '%', cx, cy + 20, `800 62px ${DM}`, BR, 'center'); }
        bloco(c, s.titulo, { fonte: f, titulo: true, x: M, y: 972, larg: W - 2 * M, alt: 200, max: 104, min: 60, cor: BR, marca: t.acc, corMarca: sobre(t.acc, t) });
      },
      produto(c, s, t, f, d, img) {
        vidro(c, M, 200, W - 2 * M, 640, 52, 'foto'); fotoZoom(c, img, M + 18, 218, W - 2 * M - 36, 604, 38, 1, 0.5, 0.5);
        texto(c, (s.rotulo || 'CONHEÇA').toUpperCase(), M, 910, `800 28px ${DM}`, t.acc, 'left', '4px');
        bloco(c, s.titulo, { fonte: f, titulo: true, x: M, y: 934, larg: W - 2 * M, alt: 160, max: 80, min: 46, cor: BR, marca: t.acc, corMarca: sobre(t.acc, t) });
        let x = M; c.font = `700 28px ${DM}`; (s.chips || []).slice(0, 4).forEach((ch) => { ch = cabe(c, ch, 400); const w = c.measureText(ch).width + 52; if (x + w > W - M) return; vidro(c, x, 1120, w, 62, 31, 'pilula'); texto(c, ch, x + 26, 1160, `700 28px ${DM}`, BR, 'left'); x += w + 14; });
      },
      preco(c, s, t, f, d) {
        const desc = temDesconto(d); vidro(c, M, 210, W - 2 * M, 900, 56, 'cartao');
        if (desc) { texto(c, 'ANTES', M + 56, 316, `700 28px ${DM}`, BR2, 'left', '4px'); texto(c, brl(d.de), M + 56, 402, `700 74px ${DM}`, 'rgba(255,255,255,0.78)', 'left'); c.font = `700 74px ${DM}`; const w = c.measureText(brl(d.de)).width; c.strokeStyle = t.acc; c.lineWidth = 6; c.beginPath(); c.moveTo(M + 50, 380); c.lineTo(M + 62 + w, 372); c.stroke(); }
        texto(c, desc ? 'AGORA' : 'POR APENAS', M + 56, desc ? 520 : 330, `700 28px ${DM}`, BR2, 'left', '4px');
        const k = encaixar(c, brl(d.por), W - 2 * M - 112, 210, 800, DM, 90), by = (desc ? 520 : 330) + k * 0.9 + 14;
        c.save(); c.shadowColor = t.acc; c.shadowBlur = 46; texto(c, brl(d.por), M + 56, by, `800 ${k}px ${DM}`, BR, 'left'); c.restore();
        if (desc) { const cx = W - M - 56 - 150, cy = 900, R = 130; reg(c, cx - R - 20, cy - R - 20, 2 * R + 40, 2 * R + 40, 'selo'); sem(() => { c.lineWidth = 30; c.strokeStyle = 'rgba(255,255,255,0.14)'; c.beginPath(); c.arc(cx, cy, R, 0, 7); c.stroke();
          c.save(); c.shadowColor = t.acc; c.shadowBlur = 28; c.strokeStyle = t.acc; c.lineCap = 'round'; c.beginPath(); c.arc(cx, cy, R, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.min(d.desconto, 100) / 100); c.stroke(); c.restore(); });
          texto(c, '-' + d.desconto + '%', cx, cy + 22, `800 66px ${DM}`, BR, 'center');
          texto(c, 'Você economiza', M + 56, 880, `600 34px ${DM}`, BR2, 'left'); texto(c, brl(d.de - d.por), M + 56, 960, `800 62px ${DM}`, t.acc, 'left'); }
        texto(c, 'Preço visto hoje. Valores podem mudar.', M + 56, desc ? 1060 : 1060, `500 26px ${DM}`, BR2, 'left');
      },
    } });

  // ======================================================================================
  // 4) POLAROID (premium): colagem de papel, fotos reveladas, fita adesiva, bilhete de loja
  // ======================================================================================
  function polaroid(c, img, cx, cy, w, rot, legenda, tag, t, zoom, fx, fy) {
    const lado = w - 44, h = lado + 22 + 92; c.save(); c.translate(cx, cy); c.rotate(rot); c.translate(-w / 2, -h / 2);
    c.save(); c.shadowColor = 'rgba(0,0,0,0.28)'; c.shadowBlur = 34; c.shadowOffsetY = 16; c.fillStyle = '#FFFFFF'; rr(c, 0, 0, w, h, 8, tag === 'foto2' ? 'polaroid2' : 'polaroid'); c.fill(); c.restore();
    fotoZoom(c, img, 22, 22, lado, lado, 4, zoom, fx, fy);
    if (legenda) { c.font = `italic 800 ${Math.round(w * 0.06)}px ${PF}`; texto(c, cabe(c, legenda, w - 50), w / 2, h - 34, c.font, '#2B2B2B', 'center'); }
    c.save(); c.translate(w / 2, 4); c.rotate(-0.07); c.fillStyle = rgba(t.acc, 0.82); rr(c, -85, -24, 170, 50, 4, 'int'); c.fill(); c.restore(); c.restore();
  }
  C.registrar('polaroid', { nome: 'Polaroid', premium: true, decor: false, fundo: (tipo, t) => t.b,
    moldura(c, fundo, t, d, i, n, ultimo) { G.fixo = true; try {
      c.fillStyle = t.b; c.fillRect(0, 0, W, H); c.fillStyle = rgba(t.ink, 0.14); for (let x = 24; x < W; x += 48) for (let y = 24; y < H; y += 48) { c.beginPath(); c.arc(x, y, 2, 0, 7); c.fill(); }
      c.font = `italic 800 38px ${PF}`; texto(c, cabe(c, d.arroba, W - 2 * M - 200), M, 120, c.font, t.ink, 'left');
      texto(c, String(i + 1) + ' de ' + n, W - M, 120, `italic 800 36px ${PF}`, t.ink, 'right');
      if (!ultimo) { texto(c, 'arrasta', M, 1292, `italic 800 36px ${PF}`, t.ink, 'left'); c.strokeStyle = t.ink; c.lineWidth = 4; c.lineCap = 'round'; c.beginPath(); c.moveTo(M + 130, 1296); c.bezierCurveTo(M + 180, 1270, M + 230, 1320, M + 290, 1288); c.stroke(); seta(c, M + 262, 1290, 30, t.ink, 4); }
    } finally { G.fixo = false; } },
    slides: {
      capa(c, s, t, f, d, img) {
        bloco(c, s.titulo, { fonte: F_SERIF, titulo: true, x: M, y: 190, larg: W - 2 * M, alt: 250, max: 100, min: 60, cor: t.ink, marca: mix(t.acc, t.b, 0.75), corMarca: t.ink });
        polaroid(c, img, 430, 810, 620, -0.055, s.legenda || 'achado do dia', 'foto', t, 1, 0.5, 0.5);
        polaroid(c, img, 830, 1000, 320, 0.1, 'detalhe', 'foto2', t, 2.2, 0.35, 0.4);
        if (temDesconto(d)) selo(c, 150, 610, 96, '-' + d.desconto + '%', t.acc, t.ink, -0.2);
      },
      produto(c, s, t, f, d, img) {
        polaroid(c, img, 460, 560, 620, -0.04, s.legenda || 'olha só!', 'foto', t, 1, 0.5, 0.5);
        polaroid(c, img, 870, 715, 260, 0.12, 'detalhe', 'foto2', t, 2.4, 0.6, 0.45);
        c.save(); c.translate(W / 2, 1062); c.rotate(0.012); c.save(); c.shadowColor = 'rgba(0,0,0,0.22)'; c.shadowBlur = 24; c.shadowOffsetY = 12; c.fillStyle = mix(t.acc, '#FFFFFF', 0.55); rr(c, -430, -120, 860, 240, 6, 'cartao'); c.fill(); c.restore();
        bloco(c, s.titulo, { fonte: F_SERIF, titulo: true, x: -400, y: -100, larg: 800, alt: 130, max: 54, min: 34, cor: '#2B2B2B', marca: '#FFFFFF', corMarca: '#2B2B2B' });
        c.font = `italic 700 28px ${PF}`; texto(c, cabe(c, (s.chips || []).join('  ·  '), 800), -400, 96, c.font, 'rgba(43,43,43,0.85)', 'left'); c.restore();
      },
      preco(c, s, t, f, d) {
        const desc = temDesconto(d), x = 190, y = 210, w = 700, h = 950; c.save(); c.translate(W / 2, y + h / 2); c.rotate(-0.025); c.translate(-w / 2, -h / 2);
        c.save(); c.shadowColor = 'rgba(0,0,0,0.25)'; c.shadowBlur = 30; c.shadowOffsetY = 14; c.fillStyle = '#FFFFFF'; rr(c, 0, 0, w, h, 6, 'cartao'); c.fill(); c.restore();
        const P = '#2B2B2B', mid = w / 2; texto(c, cabe(c, d.arroba.toUpperCase(), w - 80), mid, 96, `800 34px ${MONO}`, P, 'center'); texto(c, '- - - - - - - - - - - - - - -', mid, 140, `700 30px ${MONO}`, 'rgba(43,43,43,0.6)', 'center');
        bloco(c, (d.nome || 'Produto'), { fonte: { corpo: MONO }, x: 50, y: 175, larg: w - 100, alt: 100, max: 30, min: 22, cor: P, peso: 700, lh: 1.25 });
        let yy = 330; const lin = (a, b) => { texto(c, a, 50, yy, `700 30px ${MONO}`, P, 'left'); texto(c, b, w - 50, yy, `700 30px ${MONO}`, P, 'right'); yy += 52; };
        if (desc) { lin('DE', brl(d.de)); lin('DESCONTO', '-' + d.desconto + '%'); lin('ECONOMIA', brl(d.de - d.por)); }
        texto(c, '- - - - - - - - - - - - - - -', mid, yy + 6, `700 30px ${MONO}`, 'rgba(43,43,43,0.6)', 'center');
        texto(c, 'TOTAL', 50, yy + 80, `800 40px ${MONO}`, P, 'left'); const k = encaixar(c, brl(d.por), w - 100, 120, 800, MONO, 50); texto(c, brl(d.por), w - 50, yy + 80 + k * 0.95 + 20, `800 ${k}px ${MONO}`, P, 'right');
        const tot = yy + 80 + k * 0.95 + 20, by = tot + 46; reg(c, 70, by, w - 140, 80, 'forma'); for (let q = 0, px = 70; px < w - 70; q++) { const bw = 3 + ((q * 7 + 3) % 5) * 2; if (px + bw > w - 70) break; c.fillStyle = P; c.fillRect(px, by, bw, 80); px += bw + 5 + (q % 3) * 2; }
        texto(c, 'OBRIGADO PELA VISITA!', mid, by + 80 + 50, `700 26px ${MONO}`, P, 'center'); texto(c, 'Valores podem mudar', mid, by + 80 + 88, `500 22px ${MONO}`, 'rgba(43,43,43,0.75)', 'center'); c.restore();
      },
    } });

  // ======================================================================================
  // 5) BENTO (premium): painel de blocos arredondados, como ficha do produto
  // ======================================================================================
  const GAP = 24, X0 = M, LW = W - 2 * M;
  C.registrar('bento', { nome: 'Bento', premium: true, decor: false, fundo: (tipo, t) => t.b,
    moldura(c, fundo, t, d, i, n, ultimo) { G.fixo = true; try {
      c.fillStyle = t.b; c.fillRect(0, 0, W, H);
      c.fillStyle = t.ink; c.beginPath(); c.arc(M + 34, 112, 34, 0, 7); c.fill(); texto(c, (d.arroba.replace('@', '')[0] || 'A').toUpperCase(), M + 34, 124, `800 36px ${DM}`, t.acc, 'center');
      c.font = `700 33px ${DM}`; const w = c.measureText('00 / 00').width + 44; texto(c, cabe(c, d.arroba, W - 2 * M - 86 - w - 30), M + 86, 124, `700 33px ${DM}`, t.ink, 'left');
      c.strokeStyle = rgba(t.ink, 0.4); c.lineWidth = 3; rr(c, W - M - w, 82, w, 60, 30, 'pilula'); c.stroke(); texto(c, String(i + 1).padStart(2, '0') + ' / ' + String(n).padStart(2, '0'), W - M - w / 2, 121, `700 28px ${DM}`, t.ink, 'center');
      if (!ultimo) { texto(c, 'Arrasta', M, 1292, `700 30px ${DM}`, rgba(t.ink, 0.85), 'left'); seta(c, M + 138, 1281, 54, rgba(t.ink, 0.85), 6); }
      for (let k = 0; k < n; k++) { c.fillStyle = k === i ? t.a : rgba(t.ink, 0.28); rr(c, W - M - (n - k) * 30 + (k === i ? -16 : 0), 1276, k === i ? 34 : 14, 14, 7, 'int'); c.fill(); }
    } finally { G.fixo = false; } },
    slides: {
      capa(c, s, t, f, d, img) {
        const pw = 600, ph = 590, cw = LW - pw - GAP, h1 = Math.round((ph - GAP) * 0.52), h2 = ph - GAP - h1;
        c.fillStyle = '#FFFFFF'; rr(c, X0, 200, pw, ph, 46, 'foto'); c.fill(); fotoZoom(c, img, X0 + 14, 214, pw - 28, ph - 28, 34, 1, 0.5, 0.5);
        const cx = X0 + pw + GAP; c.fillStyle = t.acc; rr(c, cx, 200, cw, h1, 46, 'cartao'); c.fill(); const oa = sobre(t.acc, t);
        texto(c, 'POR APENAS', cx + 26, 200 + 62, `800 22px ${DM}`, oa, 'left', '2px'); const k = encaixar(c, brl(d.por), cw - 52, 70, 800, DM, 30); texto(c, brl(d.por), cx + 26, 200 + 62 + k + 18, `800 ${k}px ${DM}`, oa, 'left');
        c.fillStyle = t.ink; rr(c, cx, 200 + h1 + GAP, cw, h2, 46, 'cartao'); c.fill();
        if (temDesconto(d)) texto(c, '-' + d.desconto + '%', cx + cw / 2, 200 + h1 + GAP + h2 / 2 + 24, `800 78px ${DM}`, t.acc, 'center'); else texto(c, 'OFERTA', cx + cw / 2, 200 + h1 + GAP + h2 / 2 + 20, `800 56px ${DM}`, t.acc, 'center');
        const yt = 200 + ph + GAP, ht = 1190 - yt; c.fillStyle = t.a; rr(c, X0, yt, LW, ht, 46, 'cartao'); c.fill(); pilula(c, X0 + 36, yt + 30, s.selo || 'ACHADO', { fundo: t.acc, cor: sobre(t.acc, t), tam: 24, pad: 22 });
        bloco(c, s.titulo, { fonte: f, titulo: true, x: X0 + 36, y: yt + 106, larg: LW - 72, alt: ht - 126, max: 78, min: 36, cor: sobre(t.a, t), marca: t.acc, corMarca: sobre(t.acc, t) });
      },
      produto(c, s, t, f, d, img) {
        c.fillStyle = '#FFFFFF'; rr(c, X0, 200, LW, 610, 46, 'foto'); c.fill(); fotoZoom(c, img, X0 + 14, 214, LW - 28, 582, 34, 1, 0.5, 0.5);
        c.fillStyle = t.a; rr(c, X0, 834, LW, 196, 46, 'cartao'); c.fill(); texto(c, (s.rotulo || 'CONHEÇA').toUpperCase(), X0 + 40, 880, `800 24px ${DM}`, razao(t.a, t.acc) >= 4.5 ? t.acc : sobre(t.a, t), 'left', '4px');
        bloco(c, s.titulo, { fonte: f, titulo: true, x: X0 + 40, y: 894, larg: LW - 80, alt: 120, max: 60, min: 32, cor: sobre(t.a, t), marca: t.acc, corMarca: sobre(t.acc, t) });
        const cw = (LW - 2 * GAP) / 3, cs = (s.chips || []).slice(0, 3); cs.forEach((ch, k) => { const x = X0 + k * (cw + GAP); c.fillStyle = k === 1 ? t.acc : t.ink; rr(c, x, 1054, cw, 136, 40, 'cartao'); c.fill();
          const col = k === 1 ? sobre(t.acc, t) : '#FFFFFF'; bloco(c, ch, { fonte: f, titulo: false, x: x + 24, y: 1078, larg: cw - 48, alt: 96, max: 32, min: 22, cor: col, peso: 800, lh: 1.15, centro: true }); });
      },
      preco(c, s, t, f, d) {
        const desc = temDesconto(d); c.fillStyle = t.acc; rr(c, X0, 200, LW, desc ? 400 : 520, 46, 'cartao'); c.fill(); const on = sobre(t.acc, t);
        texto(c, desc ? 'AGORA POR APENAS' : 'POR APENAS', X0 + 48, 276, `800 28px ${DM}`, on, 'left', '4px'); const k = encaixar(c, brl(d.por), LW - 96, 230, 800, DM, 80); texto(c, brl(d.por), X0 + 48, 276 + k * 0.9 + 40, `800 ${k}px ${DM}`, on, 'left');
        if (!desc) { texto(c, 'Preço visto hoje. Valores podem mudar a qualquer momento.', X0, 780, `500 28px ${DM}`, rgba(t.ink, 0.85), 'left'); return; }
        const w2 = (LW - GAP) / 2; c.fillStyle = '#FFFFFF'; rr(c, X0, 624, w2, 260, 46, 'cartao'); c.fill(); texto(c, 'ANTES', X0 + 40, 690, `800 24px ${DM}`, rgba(t.ink, 0.75), 'left', '4px');
        const k2 = encaixar(c, brl(d.de), w2 - 80, 64, 700, DM, 30); texto(c, brl(d.de), X0 + 40, 690 + k2 + 34, `700 ${k2}px ${DM}`, rgba(t.ink, 0.78), 'left'); c.font = `700 ${k2}px ${DM}`; const wd = c.measureText(brl(d.de)).width; c.strokeStyle = t.a; c.lineWidth = 6; c.beginPath(); c.moveTo(X0 + 34, 690 + k2 + 10); c.lineTo(X0 + 46 + wd, 690 + k2 + 4); c.stroke();
        c.fillStyle = t.ink; rr(c, X0 + w2 + GAP, 624, w2, 260, 46, 'cartao'); c.fill(); texto(c, 'DESCONTO', X0 + w2 + GAP + 40, 690, `800 24px ${DM}`, t.acc, 'left', '4px'); texto(c, '-' + d.desconto + '%', X0 + w2 + GAP + 40, 690 + 120, `800 110px ${DM}`, t.acc, 'left');
        c.fillStyle = t.a; rr(c, X0, 908, LW, 282, 46, 'cartao'); c.fill(); const oa = sobre(t.a, t); texto(c, 'VOCÊ ECONOMIZA', X0 + 48, 984, `800 28px ${DM}`, oa, 'left', '4px'); const k3 = encaixar(c, brl(d.de - d.por), LW - 96, 130, 800, DM, 50); texto(c, brl(d.de - d.por), X0 + 48, 984 + k3 + 30, `800 ${k3}px ${DM}`, oa, 'left');
      },
    } });
})();
