import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {CORES, FONTE, SEGURO} from './marca';

/** Fundo da cena + a faixa segura onde o texto pode cair.
 *
 * O fundo entra como imagem e não como cor chapada: são os fundos da família da marca
 * (marketing/fundos-marca), desenhados para deixar o miolo livre. */
export const Cena: React.FC<{fundo: string; children: React.ReactNode; claro?: boolean}> = ({
  fundo,
  children,
  claro,
}) => (
  <AbsoluteFill style={{backgroundColor: claro ? CORES.paper : CORES.brandStrong}}>
    <Img src={staticFile(fundo)} style={{width: 1080, height: 1920}} />
    <AbsoluteFill
      style={{
        paddingTop: SEGURO.topo,
        paddingBottom: SEGURO.base,
        paddingLeft: SEGURO.lateral,
        paddingRight: SEGURO.lateral,
        justifyContent: 'center',
        // Tudo centralizado: em vídeo o olho já está no meio da tela, e texto à
        // esquerda obriga a varrer de volta a cada corte. Em peça estática a borda
        // reta ajuda a ler; aqui, com um corte a cada dois segundos, atrapalha.
        alignItems: 'center',
        textAlign: 'center',
      }}
    >
      {children}
    </AbsoluteFill>
  </AbsoluteFill>
);

/** Entrada padrão de qualquer elemento: sobe alguns pixels e aparece.
 *
 * A mola dá a desaceleração; a opacidade entra em interpolate separado porque mola em
 * opacidade passa de 1 no overshoot e a tinta "pisca". */
export const Entra: React.FC<{atraso?: number; children: React.ReactNode}> = ({
  atraso = 0,
  children,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const mola = spring({frame: frame - atraso, fps, config: {damping: 200}});
  const opacidade = interpolate(frame - atraso, [0, 8], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div style={{transform: `translateY(${interpolate(mola, [0, 1], [44, 0])}px)`, opacity: opacidade}}>
      {children}
    </div>
  );
};

export const Titulo: React.FC<{children: React.ReactNode; claro?: boolean; corpo?: number}> = ({
  children,
  claro,
  corpo,
}) => (
  <div
    style={{
      fontFamily: FONTE.texto,
      fontSize: corpo ?? 118,
      fontWeight: 700,
      lineHeight: 1.04,
      letterSpacing: '-0.04em',
      color: claro ? CORES.ink : '#fff',
      whiteSpace: 'pre-line',
    }}
  >
    {children}
  </div>
);

/** O número em corpo de cartaz.
 *
 * O espaço é renderizado como gap de flex, não como caractere. Numa fonte mono o
 * espaço ocupa a largura de um dígito - em "R$ 20", com 330px de corpo, isso são
 * 160px de vazio no meio do número, e o olho lê "R$" e "20" como duas coisas em vez
 * de um preço. Como gap, o respiro vira um valor que eu escolho (0.18em) em vez de
 * uma herança da métrica da fonte.
 *
 * `lineHeight: 1` fica porque é o que faz a caixa coincidir com a tinta deste
 * número: o cifrão sobe e desce quase o em inteiro. Apertar mais encavalaria o
 * rótulo de cima - quem controla o respiro é a margem dos rótulos. */
const ESPACO_MONO = '0.18em';

export const Numero: React.FC<{children: string; cor?: string; otico?: number}> = ({
  children,
  cor,
  otico = 0,
}) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'baseline',
      justifyContent: 'center',
      gap: ESPACO_MONO,
      fontFamily: FONTE.numero,
      fontSize: 330,
      fontWeight: 700,
      // A vírgula e o espaço da mono ocupam a largura de um dígito; em corpo de cartaz
      // isso abre buraco. O letter-spacing negativo fecha sem trocar de fonte.
      letterSpacing: '-0.06em',
      // O letter-spacing negativo também é aplicado DEPOIS do último algarismo, e o
      // que ele encolhe é a caixa, não a tinta: a caixa fica 0.06em mais estreita que
      // o número, e centralizar a caixa joga o número 10px para a direita do eixo.
      // A margem devolve exatamente essa largura. Medido no quadro: sem ela o centro
      // da tinta cai em x=550; com ela, em 540, que é o meio do vídeo.
      marginRight: '0.06em',
      // Depois disso sobra o que nenhuma conta de CSS alcança: a folga lateral do
      // próprio desenho da letra. O "1" da JetBrains Mono é estreito dentro da célula
      // e o "%" quase encosta na borda, então "1%" nasce 13px à direita do eixo mesmo
      // com a caixa centralizada. `otico` é esse resto, medido no quadro renderizado -
      // a mesma correção que BRAND.md já registra para a assinatura da marca.
      transform: otico ? `translateX(${otico}px)` : undefined,
      lineHeight: 1,
      color: cor ?? CORES.highlight,
    }}
  >
    {children.split(' ').map((parte) => (
      <span key={parte}>{parte}</span>
    ))}
  </div>
);

export const Apoio: React.FC<{
  children: React.ReactNode;
  claro?: boolean;
  corpo?: number;
  margemTopo?: number;
  margemBase?: number;
}> = ({children, claro, corpo, margemTopo = 18, margemBase = 0}) => (
  <div
    style={{
      fontFamily: FONTE.texto,
      fontSize: corpo ?? 44,
      fontWeight: 600,
      lineHeight: 1.1,
      marginTop: margemTopo,
      marginBottom: margemBase,
      color: claro ? CORES.muted : 'rgba(255,255,255,0.78)',
    }}
  >
    {children}
  </div>
);
