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

export const Titulo: React.FC<{children: React.ReactNode; claro?: boolean}> = ({children, claro}) => (
  <div
    style={{
      fontFamily: FONTE.texto,
      fontSize: 118,
      fontWeight: 700,
      lineHeight: 0.98,
      letterSpacing: '-0.04em',
      color: claro ? CORES.ink : '#fff',
      whiteSpace: 'pre-line',
    }}
  >
    {children}
  </div>
);

export const Numero: React.FC<{children: React.ReactNode; cor?: string}> = ({children, cor}) => (
  <div
    style={{
      fontFamily: FONTE.numero,
      fontSize: 260,
      fontWeight: 700,
      // A vírgula e o espaço da mono ocupam a largura de um dígito; em corpo de cartaz
      // isso abre buraco. O letter-spacing negativo fecha sem trocar de fonte.
      letterSpacing: '-0.06em',
      lineHeight: 1,
      color: cor ?? CORES.highlight,
    }}
  >
    {children}
  </div>
);

export const Apoio: React.FC<{children: React.ReactNode; claro?: boolean}> = ({children, claro}) => (
  <div
    style={{
      fontFamily: FONTE.texto,
      fontSize: 44,
      fontWeight: 600,
      marginTop: 18,
      color: claro ? CORES.muted : 'rgba(255,255,255,0.78)',
    }}
  >
    {children}
  </div>
);
