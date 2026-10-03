import React from 'react';
import {useCurrentFrame} from 'remotion';
import {CORES, FONTE} from '../marca';
import {semente} from '../animada/util';

/** Peças de cenário da campanha 10.10: painel de letreiro (split-flap) e papel de recibo.
 *
 * É de propósito outra linguagem visual da dos vídeos "Espera": ali, fundo roxo, texto
 * enorme, moeda e transições de empurrar/íris/portas. Aqui, objetos físicos (calendário,
 * letreiro de aeroporto, recibo, relógio digital) em fundos de cor chapada. */

export const CREME = '#fff7e6';
export const TINTA_ESCURA = '#0f0d1c';

export const FLAP_W = 165;
export const FLAP_H = 230;
const FLAP_FUNDO = '#1c1b29';

const Metade: React.FC<{c: string; topo: boolean}> = ({c, topo}) => (
  <div
    style={{
      position: 'absolute',
      left: 0,
      right: 0,
      [topo ? 'top' : 'bottom']: 0,
      height: FLAP_H / 2,
      overflow: 'hidden',
      background: FLAP_FUNDO,
      borderRadius: topo ? '16px 16px 0 0' : '0 0 16px 16px',
      backfaceVisibility: 'hidden',
    }}
  >
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        [topo ? 'top' : 'bottom']: 0,
        height: FLAP_H,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: FONTE.numero,
        fontWeight: 700,
        fontSize: 190,
        lineHeight: 1,
        color: CREME,
      }}
    >
      {c}
    </div>
  </div>
);

/** Uma casa do letreiro. `seq` é a sequência de caracteres por onde ela passa; cada troca
 * dura `passo` quadros. Antes de `inicio` mostra o primeiro; depois da última troca, o
 * último.
 *
 * Uma troca é de verdade em duas metades: a de cima do caractere antigo cai (rotateX de 0
 * a -90) e, a meio caminho, a de baixo do novo termina de cair (de 90 a 0). Por trás ficam
 * a metade de cima do NOVO e a de baixo do ANTIGO, que é o que aparece enquanto as abas
 * giram. */
export const Casa: React.FC<{seq: string[]; inicio: number; passo?: number; largura?: number}> = ({
  seq,
  inicio,
  passo = 5,
  largura = FLAP_W,
}) => {
  const frame = useCurrentFrame();
  const n = seq.length - 1;
  const t = frame - inicio;
  const k = t < 0 ? 0 : Math.min(Math.floor(t / passo), n);
  const trocando = t >= 0 && k < n;
  const p = trocando ? (t - k * passo) / passo : 0;
  const de = seq[Math.min(k, n)];
  const para = seq[Math.min(k + 1, n)];
  const estaticoTopo = trocando ? para : de;
  const estaticoBase = de;

  return (
    <div style={{position: 'relative', width: largura, height: FLAP_H, perspective: 900}}>
      <Metade c={estaticoTopo} topo />
      <Metade c={estaticoBase} topo={false} />
      {trocando && p < 0.5 ? (
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: 0,
            height: FLAP_H / 2,
            transformOrigin: 'bottom center',
            transform: `rotateX(${-p * 2 * 90}deg)`,
          }}
        >
          <Metade c={de} topo />
        </div>
      ) : null}
      {trocando && p >= 0.5 ? (
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            height: FLAP_H / 2,
            transformOrigin: 'top center',
            transform: `rotateX(${(1 - (p - 0.5) * 2) * 90}deg)`,
          }}
        >
          <Metade c={para} topo={false} />
        </div>
      ) : null}
      {/* a fresta entre as duas metades e os pinos das laterais */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: FLAP_H / 2 - 2,
          height: 4,
          background: TINTA_ESCURA,
        }}
      />
    </div>
  );
};

/** Caracteres intermediários de uma troca: dígitos sorteados com semente, para o vídeo
 * sair igual a cada render. O letreiro real passa por vários antes de assentar. */
export const sequencia = (de: string, para: string, chave: number): string[] => {
  if (de === para) return [de];
  const meio = [0, 1].map((i) => String(Math.floor(semente(chave * 7 + i) * 10)));
  return [de, ...meio, para];
};

/** Borda serrilhada do papel de recibo (a parte de baixo, onde o papel foi rasgado). */
export const Serrilha: React.FC<{cor: string}> = ({cor}) => (
  <div
    style={{
      height: 22,
      background: `linear-gradient(135deg, ${cor} 25%, transparent 25%) -11px 0, linear-gradient(225deg, ${cor} 25%, transparent 25%) -11px 0`,
      backgroundSize: '22px 22px',
    }}
  />
);

export const Tracejado: React.FC = () => (
  <div style={{borderTop: `3px dashed ${CORES.muted}`, opacity: 0.45, margin: '18px 0'}} />
);
