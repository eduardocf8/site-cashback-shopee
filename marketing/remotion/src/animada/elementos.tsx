import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {CORES, FONTE} from '../marca';
import {H, W, prog, saida, semente} from './util';

/** A moeda da marca: círculo com "R$" e o anel âmbar incompleto.
 *
 * É a mesma ilustração dos painéis de login e cadastro
 * (accounts/templates/accounts/_ilustracao_auth.html, classes .grafico-* de brand.css),
 * com as mesmas medidas do viewBox 320. Não desenhei uma moeda nova de propósito: a
 * marca já tem uma, e uma segunda moeda no vídeo seria a marca falando dois idiomas.
 *
 * O giro é achatar a largura com |cos|, e não uma rotação 3D: a moeda é plana (BRAND.md,
 * "forma geométrica plana"), e perspectiva a faria parecer objeto renderizado. */
export const Moeda: React.FC<{
  x: number;
  y: number;
  tam: number;
  giro?: number;
  rot?: number;
  escala?: number;
  opacidade?: number;
}> = ({x, y, tam, giro = 0, rot = 0, escala = 1, opacidade = 1}) => {
  const largura = Math.max(0.06, Math.abs(Math.cos(giro)));
  return (
    <svg
      width={tam}
      height={tam}
      viewBox="0 0 320 320"
      style={{
        position: 'absolute',
        left: x - tam / 2,
        top: y - tam / 2,
        overflow: 'visible',
        opacity: opacidade,
        transform: `rotate(${rot}deg) scale(${escala * largura}, ${escala})`,
        filter: 'drop-shadow(0 14px 22px rgba(17,24,39,0.28))',
      }}
    >
      <circle
        cx={160}
        cy={160}
        r={88}
        fill="none"
        stroke={CORES.highlight}
        strokeWidth={10}
        strokeLinecap="round"
        strokeDasharray="430 90"
        transform="rotate(-40 160 160)"
      />
      <circle cx={160} cy={160} r={66} fill={CORES.paper} />
      <text
        x={160}
        y={177}
        textAnchor="middle"
        fontSize={46}
        letterSpacing={-2}
        fontFamily={FONTE.texto}
        fontWeight={700}
        fill={CORES.brandStrong}
      >
        R$
      </text>
    </svg>
  );
};

/** Traços que saem de um ponto, como marca de impacto. Cada um nasce a `base` do centro,
 * cresce `comp` para fora e encolhe pela ponta de trás: o que se vê é uma faísca que
 * viaja e some, e não uma linha que aparece parada.
 *
 * `base` pode ser uma função do ângulo. É o que permite os raios nascerem na borda de uma
 * palavra larga (uma elipse) em vez de num círculo: com raio fixo, os de cima e de baixo
 * ficariam longe do texto e os dos lados escondidos atrás dele. */
export const Raios: React.FC<{
  x: number;
  y: number;
  p: number;
  n?: number;
  base: number | ((rad: number) => number);
  comp: number;
  largura?: number;
  cor?: string;
  giro?: number;
  /** Ignora os raios que apontam para cima. Sem isso, os de cima de uma palavra que tem
   * texto logo acima atravessam esse texto. */
  semOsDeCima?: boolean;
}> = ({x, y, p, n = 10, base, comp, largura = 10, cor = CORES.highlight, giro = 0, semOsDeCima}) => {
  if (p <= 0 || p >= 1) return null;
  const e = saida(p);
  return (
    <svg
      width={W}
      height={H}
      style={{position: 'absolute', left: 0, top: 0, opacity: 1 - p * p}}
    >
      {Array.from({length: n}, (_, i) => {
        const a = ((i / n) * 360 + giro) * (Math.PI / 180);
        if (semOsDeCima && Math.sin(a) < -0.32) return null;
        const b = typeof base === 'function' ? base(a) : base;
        const dentro = b + comp * Math.max(0, e * 1.25 - 0.35);
        const fora = b + comp * e;
        return (
          <line
            key={i}
            x1={x + Math.cos(a) * dentro}
            y1={y + Math.sin(a) * dentro}
            x2={x + Math.cos(a) * fora}
            y2={y + Math.sin(a) * fora}
            stroke={cor}
            strokeWidth={largura}
            strokeLinecap="round"
          />
        );
      })}
    </svg>
  );
};

/** Raio de uma elipse de semieixos a (horizontal) e b (vertical) no ângulo dado, mais uma
 * folga. É a `base` dos raios em volta de uma palavra: contorna o texto em vez de cortá-lo. */
export const contorno =
  (a: number, b: number, folga: number) =>
  (rad: number): number =>
    1 / Math.sqrt((Math.cos(rad) / a) ** 2 + (Math.sin(rad) / b) ** 2) + folga;

/** Anel que se expande e some. É o gesto do halo da marca (fundo 06-halo) posto em
 * movimento: arcos concêntricos, agora ondulando para fora. */
export const Onda: React.FC<{
  x: number;
  y: number;
  p: number;
  r0: number;
  r1: number;
  largura?: number;
  cor?: string;
  opacidade?: number;
}> = ({x, y, p, r0, r1, largura = 8, cor = '#fff', opacidade = 0.5}) => {
  if (p <= 0 || p >= 1) return null;
  return (
    <svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0}}>
      <circle
        cx={x}
        cy={y}
        r={r0 + (r1 - r0) * saida(p)}
        fill="none"
        stroke={cor}
        strokeWidth={largura * (1 - p * 0.7)}
        opacity={opacidade * (1 - p)}
      />
    </svg>
  );
};

/** Barras que sobem em degraus, com a última em âmbar cheio. É a imagem de "bem mais"
 * sem afirmar número nenhum: nenhuma barra tem rótulo, então o desenho não promete uma
 * proporção que o produto não garante. */
export const Barras: React.FC<{
  inicio: number;
  alturas: number[];
  baseY: number;
  largura?: number;
  folga?: number;
  passo?: number;
}> = ({inicio, alturas, baseY, largura = 84, folga = 28, passo = 5}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const total = alturas.length * largura + (alturas.length - 1) * folga;
  return (
    <>
      {alturas.map((altura, i) => {
        const mola = spring({
          frame: frame - (inicio + i * passo),
          fps,
          config: {damping: 13, stiffness: 140},
        });
        const h = Math.max(0, altura * mola);
        const ultima = i === alturas.length - 1;
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: (W - total) / 2 + i * (largura + folga),
              top: baseY - h,
              width: largura,
              height: h,
              borderRadius: '16px 16px 6px 6px',
              background: ultima ? CORES.highlight : 'rgba(255,255,255,0.22)',
            }}
          />
        );
      })}
    </>
  );
};

/** Marca de verificação que se desenha: o círculo entra com mola e o traço é riscado em
 * seguida. `pathLength=1` normaliza o comprimento do traço, então o dashoffset vai de 1
 * a 0 sem eu medir o caminho. */
export const Check: React.FC<{inicio: number; tam: number}> = ({inicio, tam}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const mola = spring({frame: frame - inicio, fps, config: {damping: 11, stiffness: 180}});
  const risca = prog(frame, inicio + 6, inicio + 16, saida);
  return (
    <svg
      width={tam}
      height={tam}
      viewBox="0 0 100 100"
      style={{
        flexShrink: 0,
        transform: `scale(${interpolate(mola, [0, 1], [0, 1])})`,
      }}
    >
      <circle cx={50} cy={50} r={46} fill={CORES.success} />
      <path
        d="M27 52 L44 68 L73 34"
        fill="none"
        stroke="#fff"
        strokeWidth={10}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={1}
        strokeDasharray={1}
        strokeDashoffset={1 - risca}
      />
    </svg>
  );
};

/** Trilho de progresso. `p` de 0 a 1 é quanto está cheio. */
export const Trilho: React.FC<{p: number; largura: number; altura?: number}> = ({
  p,
  largura,
  altura = 22,
}) => (
  <div
    style={{
      width: largura,
      height: altura,
      borderRadius: altura / 2,
      background: 'rgba(17,24,39,0.09)',
      overflow: 'hidden',
    }}
  >
    <div
      style={{
        width: `${p * 100}%`,
        height: '100%',
        borderRadius: altura / 2,
        background: CORES.success,
      }}
    />
  </div>
);

/** Moedas que estouram de um ponto e caem com gravidade. Todas as constantes de cada
 * moeda saem de `semente(i)`, então o estouro é o mesmo em todo render.
 *
 * O giro é lento (duas a quatro voltas em toda a queda). Com giro rápido cada moeda passa
 * a maior parte do tempo de lado, achatada, e o estouro parece um punhado de riscos. */
export const ChuvaDeMoedas: React.FC<{
  x: number;
  y: number;
  inicio: number;
  n?: number;
  duracao?: number;
  tam?: number;
}> = ({x, y, inicio, n = 10, duracao = 44, tam = 230}) => {
  const frame = useCurrentFrame();
  const p = prog(frame, inicio, inicio + duracao);
  if (p <= 0 || p >= 1) return null;
  return (
    <>
      {Array.from({length: n}, (_, i) => {
        // Ângulos espalhados em leque, com um pouco de acaso por moeda. Sorteando o
        // ângulo inteiro, o estouro saía torto: na primeira versão todas caíam do lado
        // direito da palavra.
        const ang = -Math.PI / 2 + (i / (n - 1) - 0.5) * Math.PI * 1.55 + (semente(i + 1) - 0.5) * 0.35;
        const v = 380 + semente(i + 20) * 420;
        const t = saida(p);
        const px = x + Math.cos(ang) * v * t;
        const py = y + Math.sin(ang) * v * t + 900 * p * p;
        return (
          <Moeda
            key={i}
            x={px}
            y={py}
            tam={tam * (0.75 + semente(i + 40) * 0.5)}
            giro={p * (2 + semente(i + 60) * 2)}
            rot={(semente(i + 80) - 0.5) * 50}
            opacidade={p < 0.75 ? 1 : 1 - (p - 0.75) / 0.25}
          />
        );
      })}
    </>
  );
};

/** Palavra que sobe de dentro de uma máscara: o texto já está inteiro, o que aparece é o
 * recorte. É a entrada de texto padrão deste vídeo, em vez do "sobe e aparece" - o efeito
 * de "sai de baixo de uma linha" é o que dá cara de título de filme.
 *
 * O padding e a margem negativa são a parte que passa despercebida: sem folga, o
 * overflow cortaria a haste de baixo do p e do g, o acento do ê e as bordas do grifo. A
 * margem negativa devolve o espaço, então a folga não desloca nada. */
export const Sobe: React.FC<{
  inicio: number;
  children: React.ReactNode;
  duracao?: number;
}> = ({inicio, children, duracao = 14}) => {
  const frame = useCurrentFrame();
  const p = prog(frame, inicio, inicio + duracao, saida);
  return (
    <span
      style={{
        display: 'inline-block',
        overflow: 'hidden',
        verticalAlign: 'top',
        padding: '0.22em 0.16em 0.22em',
        margin: '-0.22em -0.16em -0.22em',
      }}
    >
      <span
        style={{
          display: 'inline-block',
          transform: `translateY(${(1 - p) * 112}%)`,
        }}
      >
        {children}
      </span>
    </span>
  );
};

/** Uma linha de texto, palavra por palavra, cada uma subindo da sua máscara. */
export const LinhaSobe: React.FC<{
  texto: string;
  inicio: number;
  passo?: number;
  duracao?: number;
}> = ({texto, inicio, passo = 4, duracao = 14}) => (
  <>
    {texto.split(' ').map((palavra, i) => (
      <React.Fragment key={i}>
        {i > 0 ? ' ' : null}
        <Sobe inicio={inicio + i * passo} duracao={duracao}>
          {palavra}
        </Sobe>
      </React.Fragment>
    ))}
  </>
);
