import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {H, W, prog, saida, suave} from './util';

/** Seis transições, uma para cada tipo de passagem que o vídeo faz.
 *
 * Em vez de sortear um efeito por cena, cada uma diz alguma coisa:
 *
 * - `iris`         do "Espera." para a frase. O círculo abre a partir do centro, onde a
 *                  palavra estava: a interrupção "se abre" na explicação.
 * - `empurraCima`  da frase para o número. Empurrão para cima com borrão vertical: é a
 *                  passagem "agora vem o dado".
 * - `portas`       do número para "bem mais". A cena se parte ao meio e abre para os
 *                  lados: literalmente abre para mais.
 * - `irisBaixo`    do roxo para o claro. O círculo nasce embaixo e sobe: a mudança de cor
 *                  de fundo é a passagem de "promete" para "mostra", e ela precisa
 *                  parecer uma mudança de estado, não só de cena.
 * - `empurraLado`  entre as duas cenas claras. Movimento na horizontal para não repetir
 *                  o eixo do empurrão anterior.
 * - `relogio`      para o fechamento. Varredura em ponteiro: é o único movimento
 *                  circular contínuo do vídeo, reservado para o final.
 *
 * Cada transição é uma janela de tempo em que a cena que sai e a que entra existem ao
 * mesmo tempo. O que muda entre os tipos é só o que cada uma faz durante a janela. */
export type Tipo = 'iris' | 'irisBaixo' | 'empurraCima' | 'empurraLado' | 'portas' | 'relogio';

export type Janela = {tipo: Tipo; dur: number};

const RAIO_CENTRO = Math.hypot(W / 2, H / 2);
const RAIO_BAIXO = Math.hypot(W / 2, H);
const BORRAO_MAX = 24;

type Peca = {
  estilo: React.CSSProperties;
  decoracao?: React.ReactNode;
  borrao?: {x: number; y: number};
};

/** Estilo da cena que ENTRA, conforme o tipo da transição e o progresso `p`. */
const entrando = (tipo: Tipo, p: number): Peca => {
  if (p >= 1) return {estilo: {}};
  switch (tipo) {
    case 'iris': {
      const r = p * RAIO_CENTRO;
      return {
        estilo: {clipPath: `circle(${r}px at 50% 50%)`},
        decoracao: (
          <svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0}}>
            <circle
              cx={W / 2}
              cy={H / 2}
              r={r}
              fill="none"
              stroke="#fff"
              strokeWidth={12 * (1 - p)}
              opacity={0.55 * (1 - p * 0.5)}
            />
          </svg>
        ),
      };
    }
    case 'irisBaixo':
      return {estilo: {clipPath: `circle(${p * RAIO_BAIXO}px at 50% 100%)`}};
    case 'empurraCima':
      return {
        estilo: {transform: `translateY(${(1 - p) * H}px)`},
        borrao: {x: 0, y: BORRAO_MAX * Math.sin(Math.PI * p)},
      };
    case 'empurraLado':
      return {
        estilo: {transform: `translateX(${(1 - p) * W}px)`},
        borrao: {x: BORRAO_MAX * Math.sin(Math.PI * p), y: 0},
      };
    case 'portas':
      // Por baixo das portas: a cena que entra assenta de um pouco maior, como quem
      // estava atrás da porta e só agora ganha lugar.
      return {estilo: {transform: `scale(${1 + 0.07 * (1 - p)})`}};
    case 'relogio': {
      const graus = p * 360;
      const mascara = `conic-gradient(from 0deg at 50% 50%, #000 ${graus}deg, transparent ${graus}deg)`;
      return {estilo: {WebkitMaskImage: mascara, maskImage: mascara}};
    }
  }
};

/** Estilo da cena que SAI. */
const saindo = (tipo: Tipo, p: number): Peca => {
  if (p <= 0) return {estilo: {}};
  switch (tipo) {
    case 'iris':
    case 'irisBaixo':
    case 'relogio':
      // A que sai recua um pouco. Sem isso a cena velha parece um papel sendo coberto;
      // com o recuo, ela parece ficar para trás. É 2,5% e não mais: a cena que recua
      // deixa uma borda de fundo à mostra, e com 6% a borda virava uma moldura.
      return {estilo: {transform: `scale(${1 - 0.025 * p})`}};
    case 'empurraCima':
      return {
        estilo: {transform: `translateY(${-p * H}px)`},
        borrao: {x: 0, y: BORRAO_MAX * Math.sin(Math.PI * p)},
      };
    case 'empurraLado':
      return {
        estilo: {transform: `translateX(${-p * W}px)`},
        borrao: {x: BORRAO_MAX * Math.sin(Math.PI * p), y: 0},
      };
    case 'portas':
      return {estilo: {}};
  }
};

const Filtro: React.FC<{id: string; x: number; y: number}> = ({id, x, y}) => (
  <svg width={0} height={0} style={{position: 'absolute'}}>
    <defs>
      <filter id={id} x="-5%" y="-5%" width="110%" height="110%">
        <feGaussianBlur stdDeviation={`${x} ${y}`} />
      </filter>
    </defs>
  </svg>
);

/** Uma cena dentro do vídeo, com a janela de entrada e a de saída.
 *
 * O `frame` aqui é o da Sequence onde a Camada está, então 0 é o início da cena e `dur`
 * é o último. A janela de entrada é [0, entra.dur] e a de saída é [dur - sai.dur, dur]. */
export const Camada: React.FC<{
  id: string;
  z: number;
  dur: number;
  entra?: Janela;
  sai?: Janela;
  children: React.ReactNode;
}> = ({id, z, dur, entra, sai, children}) => {
  const frame = useCurrentFrame();
  const pEntra = entra ? prog(frame, 0, entra.dur, suave) : 1;
  // As portas abrem na batida do drop, então arrancam de uma vez (curva de saída) em vez
  // de esperar a curva acelerar: com `suave` as metades mal se mexiam nos 3 primeiros
  // quadros, e o golpe chegava 100ms depois da música.
  const pSai = sai ? prog(frame, dur - sai.dur, dur, sai.tipo === 'portas' ? saida : suave) : 0;
  const saiu = sai ? frame >= dur - sai.dur : false;

  const a = entra ? entrando(entra.tipo, pEntra) : {estilo: {}};
  const b = sai ? saindo(sai.tipo, pSai) : {estilo: {}};
  const borrao = b.borrao ?? a.borrao;
  const filtro = borrao && (borrao.x > 0.4 || borrao.y > 0.4) ? `url(#b-${id})` : undefined;

  // As portas são o único caso em que a cena que SAI é desenhada duas vezes: a metade de
  // cima sobe e a de baixo desce. O filho é o mesmo; como o render é função do frame, as
  // duas cópias ficam idênticas.
  if (sai?.tipo === 'portas' && saiu) {
    return (
      // A cena que sai fica ACIMA da que entra (as portas se abrem para revelá-la), então o
      // z precisa passar do z da próxima cena, que é z + 4. Com `z + 3` ela ficava por
      // baixo e as portas se abriam atrás da cena nova: o que se via era um corte seco.
      <AbsoluteFill style={{zIndex: z + 5}}>
        {[0, 1].map((k) => (
          <AbsoluteFill
            key={k}
            style={{
              clipPath: k === 0 ? 'inset(0 0 50% 0)' : 'inset(50% 0 0 0)',
              transform: `translateY(${(k === 0 ? -1 : 1) * pSai * (H / 2 + 8)}px)`,
            }}
          >
            {children}
            <div
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                top: H / 2 - (k === 0 ? 5 : 0),
                height: 5,
                background: '#f59e0b',
              }}
            />
          </AbsoluteFill>
        ))}
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{zIndex: z}}>
      {filtro ? <Filtro id={`b-${id}`} x={borrao!.x} y={borrao!.y} /> : null}
      <AbsoluteFill style={{...a.estilo, ...b.estilo, filter: filtro}}>{children}</AbsoluteFill>
      {a.decoracao}
    </AbsoluteFill>
  );
};
