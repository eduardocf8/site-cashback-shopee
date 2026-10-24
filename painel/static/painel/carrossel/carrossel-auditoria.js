/* Auditoria do carrossel: roda em teste (não vai para o painel). Registra cada texto e
 * cada forma desenhada e procura o que a vista cansa de deixar passar: sobreposição,
 * texto cortado ou fora da margem, texto invadindo o topo/rodapé e baixo contraste. */
(function () {
  const C = window.Carrossel, G = C.G, W = C.W, H = C.H, M = C.M;
  let itens, avisos, atualSlide, zc = 0;
  const push = (o) => { o.z = zc++; itens.push(o); };
  const aabb = (m, x, y, w, h) => { const p = [[x, y], [x + w, y], [x, y + h], [x + w, y + h]].map(([a, b]) => [m.a * a + m.c * b + m.e, m.b * a + m.d * b + m.f]);
    const xs = p.map((q) => q[0]), ys = p.map((q) => q[1]); return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) }; };
  const inter = (a, b) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  const dentro = (a, b, t = 3) => a.x >= b.x - t && a.y >= b.y - t && a.x + a.w <= b.x + b.w + t && a.y + a.h <= b.y + b.h + t; // a dentro de b
  const igual = (a, b) => Math.abs(a.x - b.x) < 2 && Math.abs(a.y - b.y) < 2 && Math.abs(a.w - b.w) < 2 && Math.abs(a.h - b.h) < 2;
  const aviso = (nivel, msg) => avisos.push({ slide: atualSlide, nivel, msg });
  const cor = (css) => { if (css[0] === '#') { const n = parseInt(css.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255, 1]; }
    const m = css.match(/rgba?\(([^)]+)\)/); if (!m) return [0, 0, 0, 1]; const v = m[1].split(',').map(Number); return [v[0], v[1], v[2], v.length > 3 ? v[3] : 1]; };
  const lum = (r, g, b) => { const f = (c) => { c /= 255; return c <= .03928 ? c / 12.92 : Math.pow((c + .055) / 1.055, 2.4); }; return .2126 * f(r) + .7152 * f(g) + .0722 * f(b); };
  const razao = (a, b) => { const x = lum(...a), y = lum(...b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };

  G.forma = (c, x, y, w, h, tag) => { if (![x, y, w, h].every(Number.isFinite)) aviso('erro', `forma com posição inválida (NaN): ${tag}`); if (tag === 'int' || tag === 'marca') return; const b = aabb(c.getTransform(), x, y, w, h); push({ k: 'forma', tag, fixo: !!G.fixo, ...b, circ: tag === 'selo' ? { cx: b.x + b.w / 2, cy: b.y + b.h / 2, r: b.w / 2 } : null }); };
  G.decor = (c, x, y, w, h) => push({ k: 'decor', fixo: !!G.fixo, ...aabb(c.getTransform(), x, y, w, h) });
  G.bloco = (b) => { const maior = Math.max(0, ...b.lin.map((l) => l.w)), usada = b.lin.length * b.tam * b.lh;
    if (b.lin.some((l) => l.w > b.larg + 1)) aviso('erro', `palavra mais larga que a caixa em "${b.txt.slice(0, 30)}"`);
    if (usada > b.alt + 2) aviso('erro', `texto estoura a altura (${Math.round(usada)} > ${b.alt}) em "${b.txt.slice(0, 30)}…" (${b.lin.length} linhas, fonte ${Math.round(b.tam)})`);
    else if (b.tam <= b.min + 0.5 && b.lin.length > 1) aviso('aviso', `texto no tamanho mínimo em "${b.txt.slice(0, 30)}…"`); };
  G.antes = (c) => { itens = []; avisos = []; zc = 0; if (c.__aud) return; c.__aud = true; const orig = c.fillText.bind(c);
    c.fillText = (t, x, y, mw) => { if (G.ignorarTexto) return orig(t, x, y, mw); if (!Number.isFinite(x) || !Number.isFinite(y)) aviso('erro', `texto com posição inválida (NaN): "${String(t).slice(0, 24)}"`); const m = c.measureText(String(t)); const al = c.textAlign; const x0 = al === 'center' ? x - m.width / 2 : al === 'right' ? x - m.width : x;
      const tamF = parseFloat(c.font.match(/(\d+(\.\d+)?)px/)[1]), emoji = /\p{Extended_Pictographic}/u.test(String(t)); // emoji informa altura exagerada: usa o tamanho da fonte
      const top = emoji ? y - tamF * 0.8 : y - m.actualBoundingBoxAscent, h = emoji ? tamF : m.actualBoundingBoxAscent + m.actualBoundingBoxDescent;
      const tr = c.getTransform(), bx = aabb(tr, x0, top, m.width, h), inclina = Math.min(bx.h - 4, m.width * Math.abs(tr.b)); // texto girado: tira da caixa o que é só inclinação
      push({ k: 'texto', t: String(t), fixo: !!G.fixo, cor: c.fillStyle, fundo: G.fundoMarca || null, tam: parseFloat(c.font.match(/(\d+(\.\d+)?)px/)[1]), negrito: /^(700|800|900|bold)/.test(c.font), ...bx, y: bx.y + inclina / 2, h: bx.h - inclina }); return orig(t, x, y, mw); };
    const fr = c.fillRect.bind(c), sr = c.strokeRect.bind(c), rect = (nome, orig) => (x, y, w, h) => { if (w >= 12 && h >= 12 && !(w >= W * 0.9 && h >= H * 0.9)) push({ k: 'forma', tag: 'forma', fixo: !!G.fixo, ...aabb(c.getTransform(), x, y, w, h) }); return orig(x, y, w, h); };
    c.fillRect = rect('fill', fr); c.strokeRect = rect('stroke', sr);
    const arc = c.arc.bind(c); c.arc = (x, y, r, ...a) => { if (r >= 20 && !G.ignorarArc) push({ k: 'forma', tag: 'forma', fixo: !!G.fixo, ...aabb(c.getTransform(), x - r, y - r, 2 * r, 2 * r) }); return arc(x, y, r, ...a); }; };
  G.depois = (c, i, s) => { const z = [{ tag: 'topo', x: 0, y: 60, w: W, h: 100 }, { tag: 'rodape', x: 0, y: 1212, w: W, h: 138 }];
    const textos = itens.filter((q) => q.k === 'texto' && q.w > 0), formas = itens.filter((q) => q.k === 'forma'), decor = itens.filter((q) => q.k === 'decor');
    const id = (q) => q.k === 'texto' ? `texto "${q.t.slice(0, 22)}"` : `${q.tag || 'forma'}@${Math.round(q.x)},${Math.round(q.y)}`;
    // 1) texto x texto
    for (let a = 0; a < textos.length; a++) for (let b = a + 1; b < textos.length; b++) { const A = textos[a], B = textos[b];
      const sh = (q) => ({ x: q.x + 2, y: q.y + 3, w: q.w - 4, h: q.h - 6 }); if (A.w > 4 && B.w > 4 && inter(sh(A), sh(B)) > 12) aviso('erro', `${id(A)} sobrepõe ${id(B)}`); }
    // 2) forma x forma
    const permitido = (a, b) => { const p = [a.tag, b.tag].sort().join('+'); return ['foto+selo', 'cartao+selo', 'forma+selo', 'foto+foto2', 'foto2+selo', 'foto+pilula', 'polaroid+polaroid2', 'polaroid+selo', 'polaroid2+selo', 'ponte+selo', 'cartao+foto', 'cartao+foto2', 'foto2+pilula', 'cartao+ponte', 'foto2+ponte', 'pilula+ponte'].includes(p); };
    for (let a = 0; a < formas.length; a++) for (let b = a + 1; b < formas.length; b++) { const A = formas[a], B = formas[b];
      if (igual(A, B) || dentro(A, B) || dentro(B, A) || permitido(A, B)) continue; if (inter(A, B) > 40) aviso('erro', `${id(A)} cruza ${id(B)}`); }
    // 3) texto x forma
    const selos = formas.filter((q) => q.tag === 'selo');
    textos.forEach((T) => formas.forEach((F) => { if (F.circ) { const px = Math.max(T.x, Math.min(F.circ.cx, T.x + T.w)), py = Math.max(T.y, Math.min(F.circ.cy, T.y + T.h)); const d = Math.hypot(px - F.circ.cx, py - F.circ.cy);
        const fora = T.x < F.circ.cx - F.circ.r || T.x + T.w > F.circ.cx + F.circ.r || T.y < F.circ.cy - F.circ.r || T.y + T.h > F.circ.cy + F.circ.r;
        if (d < F.circ.r * 0.9 && fora) aviso('erro', `${id(T)} cruza a borda de ${id(F)}`); return; }
      const area = inter(T, F); if (area <= 6) return; if (selos.some((S) => dentro(T, S, 4))) return;
      if (formas.some((S) => S !== F && S.z > F.z && S.z < T.z && dentro(T, S, 4))) return; /* o texto está numa forma desenhada por cima desta: esta fica coberta */
      const dentroF = dentro(T, F, 4), cobre = dentro(F, T, 4);
      if (cobre) return; if (!dentroF) aviso('erro', `${id(T)} é cortado/cruza a borda de ${id(F)}`); else if (F.tag === 'foto' || F.tag === 'ponte') aviso('erro', `${id(T)} está sobre a foto`); }));
    // 4) decoração por baixo de texto
    textos.forEach((T) => decor.forEach((D) => { if (inter(T, D) > 20 && !T.fixo) aviso('aviso', `pontinhos de fundo por baixo de ${id(T)}`); }));
    // 5) margens e zonas
    textos.forEach((T) => { if (!T.fixo && (T.x + T.w < 0 || T.y + T.h < 0 || T.x > W || T.y > H)) aviso('erro', `texto fora do slide: ${id(T)}`); });
    [...textos, ...formas].filter((q) => !q.fixo).forEach((q) => { const zona = z.find((Z) => inter(q, Z) > 4);
      if (zona) aviso('erro', `${id(q)} invade o ${zona.tag} (y ${Math.round(q.y)}–${Math.round(q.y + q.h)})`);
      const lim = q.k === 'texto' ? M - 8 : 20; if (q.k === 'texto' && selos.some((S) => dentro(q, S, 4))) return; if (q.tag === 'ponte') return; if (q.tag === 'ponte') return; if (q.x < lim || q.x + q.w > W - lim) aviso('erro', `${id(q)} fora da margem (x ${Math.round(q.x)}–${Math.round(q.x + q.w)})`); });
    // 6) contraste: cor do texto contra a cor que mais aparece atrás dele
    const dados = c.getImageData(0, 0, W, H).data;
    textos.forEach((T) => { if (T.w < 6) return; const cont = {}; let melhor = null, mx = 0; const x0 = Math.max(0, Math.floor(T.x)), x1 = Math.min(W, Math.ceil(T.x + T.w)), y0 = Math.max(0, Math.floor(T.y)), y1 = Math.min(H, Math.ceil(T.y + T.h));
      const fc = cor(T.cor); for (let y = y0; y < y1; y += 3) for (let x = x0; x < x1; x += 3) { const o = (y * W + x) * 4; if (Math.abs(dados[o] - fc[0]) + Math.abs(dados[o + 1] - fc[1]) + Math.abs(dados[o + 2] - fc[2]) < 40 && fc[3] === 1) continue; const k = (dados[o] >> 4) + ',' + (dados[o + 1] >> 4) + ',' + (dados[o + 2] >> 4); const e = cont[k] || (cont[k] = { n: 0, r: dados[o], g: dados[o + 1], b: dados[o + 2] }); e.n++; if (e.n > mx) { mx = e.n; melhor = e; } }
      if (T.fundo) { const q = cor(T.fundo); melhor = { r: q[0], g: q[1], b: q[2] }; } if (!melhor) return; const f = cor(T.cor), bg = [melhor.r, melhor.g, melhor.b]; const sobre = [0, 1, 2].map((k) => f[k] * f[3] + bg[k] * (1 - f[3])); const r = razao(sobre, bg); const minimo = (T.tam >= 40 || (T.negrito && T.tam >= 26)) ? 3 : 4.5;
      if (r < minimo) aviso('erro', `contraste baixo (${r.toFixed(1)}:1) em ${id(T)}`); });
    return avisos.slice(); };

  C.auditar = (canvas, roteiro, dados, op) => { const todos = []; roteiro.forEach((s, i) => { const a = (atualSlide = i + 1, C.desenhar(canvas, roteiro, i, dados, op)); todos.push(...(a || [])); }); return todos; };
})();
