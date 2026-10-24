/* Artes criadas para o segundo slide do carrossel (protótipo).
 * Em vez de repetir a foto do produto logo depois da capa, o slide 2 ganha uma ilustração
 * desenhada que combina com o tipo de produto (cozinha, Natal, mesa posta, tecnologia...).
 * A IA escolhe o motivo pelo tipo do produto; aqui cada motivo é desenhado com formas simples,
 * em estilo adesivo (contorno grosso e sombra dura), para combinar com os modelos. */
(function () {
  const C = window.Carrossel, U = C.util, { rr, rgba, G } = U;
  const VERDE = '#2E7D32', VERDE2 = '#43A047', VERM = '#E53935', OURO = '#FFC107', MARROM = '#6D4C41', ROXO = '#6A1B9A', VINHO = '#8E1B3A', QUEIJO = '#FFD54F';

  function estrela4(c, x, y, r, cor) { c.fillStyle = cor; c.beginPath(); for (let i = 0; i < 8; i++) { const a = -Math.PI / 2 + i * Math.PI / 4, q = i % 2 ? r * 0.3 : r; c.lineTo(x + Math.cos(a) * q, y + Math.sin(a) * q); } c.closePath(); c.fill(); }
  function floco(c, x, y, r, ink) { c.save(); c.translate(x, y); c.strokeStyle = '#FFFFFF'; c.lineWidth = 7; c.lineCap = 'round'; for (let i = 0; i < 3; i++) { c.rotate(Math.PI / 3); c.beginPath(); c.moveTo(-r, 0); c.lineTo(r, 0); c.stroke(); } c.restore(); }
  const contorno = (c, ink, w) => { c.strokeStyle = ink; c.lineWidth = w || 6; c.lineJoin = 'round'; c.stroke(); };

  const MOTIVOS = {
    cozinha(c, t) {
      c.save(); c.translate(-150, 120); c.rotate(-0.55); c.fillStyle = t.ink; rr(c, -9, -10, 18, 160, 9, 'int'); c.fill(); c.fillStyle = '#FFFFFF'; rr(c, -38, -105, 76, 100, 26, 'int'); c.fill(); contorno(c, t.ink); c.restore();
      c.save(); c.translate(155, 110); c.rotate(0.55); c.fillStyle = t.ink; rr(c, -9, 0, 18, 120, 9, 'int'); c.fill(); c.strokeStyle = t.ink; c.lineWidth = 7; [[34, 78], [22, 78], [10, 78]].forEach(([rx, ry]) => { c.beginPath(); c.ellipse(0, -62, rx, ry, 0, 0, 7); c.stroke(); }); c.restore();
      c.fillStyle = t.a; rr(c, -125, -5, 250, 140, 28, 'int'); c.fill(); contorno(c, t.ink);
      c.fillStyle = '#FFFFFF'; rr(c, -142, -42, 284, 40, 20, 'int'); c.fill(); contorno(c, t.ink);
      c.fillStyle = t.ink; c.beginPath(); c.arc(0, -56, 17, 0, 7); c.fill();
      c.fillStyle = '#FFFFFF'; rr(c, -172, 30, 44, 24, 12, 'int'); c.fill(); contorno(c, t.ink, 5); rr(c, 128, 30, 44, 24, 12, 'int'); c.fill(); contorno(c, t.ink, 5);
      c.strokeStyle = '#FFFFFF'; c.lineWidth = 12; c.lineCap = 'round'; [-48, 0, 48].forEach((x, i) => { c.beginPath(); c.moveTo(x, -90); c.bezierCurveTo(x - 22, -120, x + 22, -145, x, -178 - i * 4); c.stroke(); });
      estrela4(c, -178, -120, 26, '#FFFFFF'); estrela4(c, 190, -110, 20, '#FFFFFF');
    },
    natal(c, t) {
      c.save(); c.beginPath(); c.arc(0, 0, 240, 0, 7); c.clip(); c.fillStyle = '#FFFFFF'; c.beginPath(); c.ellipse(0, 235, 280, 80, 0, 0, 7); c.fill(); contorno(c, t.ink, 5); c.restore();
      c.fillStyle = MARROM; rr(c, -24, 100, 48, 56, 6, 'int'); c.fill(); contorno(c, t.ink);
      [[VERDE, 0, -48, 100, 140, 190], [VERDE2, 0, -108, 78, 110, 70], [VERDE, 0, -160, 55, 80, -10]].forEach(() => 0);
      const camada = (cor, topo, base, meia) => { c.fillStyle = cor; c.beginPath(); c.moveTo(0, topo); c.lineTo(-meia, base); c.lineTo(meia, base); c.closePath(); c.fill(); contorno(c, t.ink); };
      camada(VERDE, -20, 110, 140); camada(VERDE2, -95, 30, 112); camada(VERDE, -165, -45, 84);
      c.fillStyle = OURO; c.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? 14 : 34; c.lineTo(Math.cos(a) * r, -196 + Math.sin(a) * r); } c.closePath(); c.fill(); contorno(c, t.ink, 5);
      [[-50, 40, VERM], [58, 76, OURO], [-84, 92, OURO], [30, -30, VERM], [-20, -88, OURO], [8, 104, VERM]].forEach(([x, y, cor]) => { c.fillStyle = cor; c.beginPath(); c.arc(x, y, 15, 0, 7); c.fill(); contorno(c, t.ink, 4); });
      floco(c, -178, -100, 26); floco(c, 182, -60, 22); floco(c, 160, 130, 18); floco(c, -170, 90, 16);
    },
    festa(c, t) {
      c.fillStyle = QUEIJO; c.beginPath(); c.moveTo(20, 150); c.lineTo(200, 150); c.lineTo(200, 40); c.closePath(); c.fill(); contorno(c, t.ink);
      c.fillStyle = OURO; c.beginPath(); c.moveTo(20, 150); c.lineTo(200, 150); c.lineTo(200, 195); c.lineTo(20, 195); c.closePath(); c.fill(); contorno(c, t.ink);
      c.fillStyle = 'rgba(0,0,0,0.18)'; [[120, 130, 11], [165, 105, 9], [170, 160, 8], [75, 170, 8]].forEach(([x, y, r]) => { c.beginPath(); c.arc(x, y, r, 0, 7); c.fill(); });
      c.fillStyle = 'rgba(255,255,255,0.55)'; c.beginPath(); c.moveTo(-70, -10); c.bezierCurveTo(-70, -120, 70, -120, 70, -10); c.bezierCurveTo(70, 50, -70, 50, -70, -10); c.closePath(); c.fill(); contorno(c, t.ink);
      c.save(); c.beginPath(); c.moveTo(-70, -10); c.bezierCurveTo(-70, 50, 70, 50, 70, -10); c.lineTo(66, -34); c.lineTo(-66, -34); c.closePath(); c.fillStyle = VINHO; c.fill(); c.restore();
      c.beginPath(); c.moveTo(-70, -10); c.bezierCurveTo(-70, -120, 70, -120, 70, -10); c.bezierCurveTo(70, 50, -70, 50, -70, -10); contorno(c, t.ink);
      c.strokeStyle = t.ink; c.lineWidth = 12; c.lineCap = 'round'; c.beginPath(); c.moveTo(0, 38); c.lineTo(0, 150); c.stroke(); c.fillStyle = t.ink; c.beginPath(); c.ellipse(0, 158, 66, 14, 0, 0, 7); c.fill();
      c.fillStyle = '#FFFFFF'; c.beginPath(); c.ellipse(-30, -40, 9, 30, 0.3, 0, 7); c.fill();
      [[-140, 95, 0], [-110, 95, 0], [-170, 95, 0], [-125, 130, 1], [-155, 130, 1], [-140, 165, 2]].forEach(([x, y]) => { c.fillStyle = ROXO; c.beginPath(); c.arc(x, y + 10, 24, 0, 7); c.fill(); contorno(c, t.ink, 4); c.fillStyle = 'rgba(255,255,255,0.5)'; c.beginPath(); c.arc(x - 7, y + 3, 6, 0, 7); c.fill(); });
      c.strokeStyle = VERDE; c.lineWidth = 9; c.lineCap = 'round'; c.beginPath(); c.moveTo(-140, 72); c.lineTo(-132, 48); c.stroke(); estrela4(c, -178, -120, 24, '#FFFFFF'); estrela4(c, 196, -100, 22, '#FFFFFF');
    },
    tech(c, t) {
      c.strokeStyle = t.ink; c.lineWidth = 30; c.lineCap = 'round'; c.beginPath(); c.arc(0, 10, 130, Math.PI * 1.08, Math.PI * 1.92); c.stroke();
      c.strokeStyle = '#FFFFFF'; c.lineWidth = 14; c.beginPath(); c.arc(0, 10, 130, Math.PI * 1.12, Math.PI * 1.88); c.stroke();
      [-132, 132].forEach((x) => { c.fillStyle = t.a; rr(c, x - 44, -10, 88, 150, 40, 'int'); c.fill(); contorno(c, t.ink); c.fillStyle = '#FFFFFF'; rr(c, x - 22, 24, 44, 82, 22, 'int'); c.fill(); });
      c.strokeStyle = t.ink; c.lineWidth = 8; c.lineCap = 'round'; [60, 92].forEach((r, i) => { [-1, 1].forEach((s) => { c.beginPath(); c.arc(s * 132, 66, r + 36, s > 0 ? -0.5 : Math.PI - 0.5 + 0.0, s > 0 ? 0.5 : Math.PI + 0.5); c.stroke(); }); });
      estrela4(c, 0, -150, 26, '#FFFFFF'); estrela4(c, -190, -110, 18, '#FFFFFF'); estrela4(c, 195, -100, 20, '#FFFFFF');
    },
    presente(c, t) {
      c.fillStyle = t.a; rr(c, -130, -10, 260, 170, 14, 'int'); c.fill(); contorno(c, t.ink); c.fillStyle = '#FFFFFF'; rr(c, -146, -50, 292, 56, 14, 'int'); c.fill(); contorno(c, t.ink);
      c.fillStyle = '#FFFFFF'; c.fillRect(-18, -50, 36, 210); c.strokeStyle = t.ink; c.lineWidth = 6; c.strokeRect(-18, -50, 36, 210);
      [-1, 1].forEach((s) => { c.beginPath(); c.moveTo(0, -50); c.bezierCurveTo(s * 20, -140, s * 120, -150, s * 100, -80); c.bezierCurveTo(s * 90, -52, s * 30, -50, 0, -50); c.fillStyle = '#FFFFFF'; c.fill(); contorno(c, t.ink); });
      estrela4(c, -178, -120, 26, '#FFFFFF'); estrela4(c, 186, -100, 22, '#FFFFFF');
    },
  };

  /** Desenha o adesivo-ilustração: disco com sombra dura e o motivo por cima. */
  function arte(c, tipo, cx, cy, tam, t) {
    const img = U.IMGS_ARTE && U.IMGS_ARTE[tipo];
    if (img) { // arte gerada por IA: entra como um cartão com borda e sombra dura, igual ao adesivo desenhado
      const lado = tam * 0.92, x = cx - lado / 2, y = cy - lado / 2;
      if (G.forma) G.forma(c, x, y, lado, lado, 'arte');
      c.save(); c.fillStyle = t.ink; rr(c, x + 14, y + 16, lado, lado, 44, 'int'); c.fill();
      c.save(); rr(c, x, y, lado, lado, 44, 'int'); c.clip(); c.drawImage(img, x, y, lado, lado); c.restore();
      rr(c, x, y, lado, lado, 44, 'int'); c.strokeStyle = t.ink; c.lineWidth = 8; c.stroke(); c.restore(); return;
    }
    const k = tam / 520, motivo = MOTIVOS[tipo] || MOTIVOS.presente; const raio = 250 * k;
    if (G.forma) G.forma(c, cx - raio, cy - raio, 2 * raio, 2 * raio, 'arte');
    const sv = G.ignorarArc; G.ignorarArc = true; // o adesivo inteiro já está registrado como uma forma só
    c.save(); c.translate(cx, cy); c.scale(k, k);
    c.fillStyle = t.ink; c.beginPath(); c.arc(16, 18, 250, 0, 7); c.fill();
    c.fillStyle = t.acc; c.beginPath(); c.arc(0, 0, 250, 0, 7); c.fill(); c.strokeStyle = t.ink; c.lineWidth = 8; c.stroke();
    c.save(); c.beginPath(); c.arc(0, 0, 246, 0, 7); c.clip(); motivo(c, t); c.restore(); c.restore(); G.ignorarArc = sv;
  }
  U.arte = arte; U.MOTIVOS_DE_ARTE = Object.keys(MOTIVOS);
})();
