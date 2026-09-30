import {Easing, interpolate} from 'remotion';

export const W = 1080;
export const H = 1920;
export const CX = W / 2;
export const CY = H / 2;

/** As três curvas do vídeo. Poucas de propósito: o que faz um movimento parecer da mesma
 * família é a curva, e trocar de curva a cada cena é o que faz peça parecer colagem.
 *
 * `suave` é para o que atravessa a tela (transições): acelera e freia. `saida` é para o
 * que chega (elementos): rápido no começo, assenta devagar. `entrada` é para o que vai
 * embora: devagar no começo, some rápido. */
export const suave = Easing.bezier(0.65, 0, 0.35, 1);
export const saida = Easing.bezier(0.22, 1, 0.36, 1);
export const entrada = Easing.bezier(0.64, 0, 0.78, 0);

/** Progresso de 0 a 1 entre dois frames, sem passar dos extremos. */
export const prog = (
  frame: number,
  de: number,
  ate: number,
  easing?: (t: number) => number,
): number =>
  interpolate(frame, [de, ate], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing,
  });

/** Ponto de uma curva de Bézier quadrática. É o que faz a moeda voar em arco em vez de
 * em linha reta: reta lê como objeto em trilho, arco lê como objeto atirado. */
export const bezier = (
  p0: [number, number],
  p1: [number, number],
  p2: [number, number],
  t: number,
): [number, number] => {
  const u = 1 - t;
  return [
    u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
  ];
};

/** Pseudoaleatório determinístico. Math.random() faria cada quadro sair diferente e o
 * vídeo tremeria: o render é quadro a quadro, sem memória do quadro anterior. */
export const semente = (n: number): number => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};
