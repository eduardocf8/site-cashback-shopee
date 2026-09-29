import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Cena, Entra} from './Base';
import {CORES, FONTE} from './marca';

/** Fechamento em dois tempos.
 *
 * Primeiro "acesse" e o endereço completo. Depois o ".com" sai e o "cash-b" continua:
 * cresce, sobe para o centro e vira branco. O nome não reaparece numa cena nova - ele
 * é o mesmo elemento o tempo todo, e é isso que faz a leitura "o site é a marca".
 *
 * O ".com" encolhe a largura junto com a opacidade. A linha está centralizada, então
 * encolher a largura recentraliza o "cash-b" sozinho, sem eu precisar adivinhar de
 * quantos pixels ele teria que andar. */
const INICIO_PADRAO = 34;

export const FechamentoConteudo: React.FC<{
  convite: string;
  dominio: string;
  sufixo: string;
  /** Desloca o relógio: na versão dinâmica a troca só começa depois que o quadro para. */
  atraso?: number;
}> = ({convite, dominio, sufixo, atraso = 0}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const INICIO_TROCA = INICIO_PADRAO + atraso;

  const troca = spring({
    frame: frame - INICIO_TROCA,
    fps,
    config: {damping: 200, mass: 1.2},
  });

  const saiSufixo = interpolate(frame, [INICIO_TROCA, INICIO_TROCA + 10], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const saiConvite = interpolate(frame, [INICIO_TROCA, INICIO_TROCA + 8], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const corpo = interpolate(troca, [0, 1], [68, 168]);
  const sobe = interpolate(troca, [0, 1], [0, -70]);
  // Do âmbar para o branco: enquanto é endereço ele é chamada (âmbar é a cor de
  // atenção da marca); quando vira marca, é a marca.
  const cor = troca < 0.5 ? CORES.highlight : '#fff';

  return (
    <div style={{transform: `translateY(${sobe}px)`}}>
      <Entra>
        <div
          style={{
            fontFamily: FONTE.texto,
            fontSize: 64,
            fontWeight: 600,
            color: 'rgba(255,255,255,0.8)',
            opacity: saiConvite,
            marginBottom: 18,
          }}
        >
          {convite}
        </div>
      </Entra>
      <Entra atraso={8}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'baseline',
            fontFamily: FONTE.texto,
            fontSize: corpo,
            fontWeight: 700,
            letterSpacing: '-0.04em',
            lineHeight: 1,
          }}
        >
          <span style={{color: cor, whiteSpace: 'nowrap'}}>{dominio}</span>
          <span
            style={{
              color: CORES.highlight,
              opacity: saiSufixo,
              // A largura encolhe junto: é o que recentraliza o "cash-b".
              maxWidth: `${saiSufixo * 4}ch`,
              overflow: 'hidden',
              display: 'inline-block',
              whiteSpace: 'nowrap',
            }}
          >
            {sufixo}
          </span>
        </div>
      </Entra>
    </div>
  );
};

export const Fechamento: React.FC<React.ComponentProps<typeof FechamentoConteudo>> = (
  props,
) => (
  <Cena fundo="fundo-halo.png">
    <FechamentoConteudo {...props} />
  </Cena>
);
