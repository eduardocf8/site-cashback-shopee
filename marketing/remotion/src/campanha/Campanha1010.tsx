import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame} from 'remotion';
import {H, entrada, prog, suave} from '../animada/util';
import {CenaCalendario, CenaDia, CenaFecho, CenaLetreiro, CenaRecibo} from './cenas';

/** Reel da campanha 10.10 (50% a mais de cashback): 18 s.
 *
 * Cinco cenas, cada uma um objeto físico, e quatro passagens que não aparecem no outro
 * vídeo (íris, empurrar, portas e relógio, que são as do "Espera"):
 *
 *   1. calendário  -> a casa do dia 10 cresce e vira a tela (a passagem é a própria cena)
 *   2. letreiro    -> persianas (a cena é fatiada em faixas que fecham)
 *   3. recibo      -> o papel cai
 *   4. 24 horas    -> a página vira para cima
 *   5. fecho
 *
 * Cada cena fica na linha do tempo `SOBRA` quadros além do seu fim: é nesse trecho que ela
 * sai por cima da próxima, que já está desenhada por baixo. */
const SOBRA = 18;

type Cena = {
  id: string;
  de: number;
  dur: number;
  saida?: 'persianas' | 'cai' | 'vira';
  C: React.FC<{dur: number}>;
};

const CENAS: Cena[] = [
  {id: 'calendario', de: 0, dur: 120, C: CenaCalendario},
  {id: 'letreiro', de: 102, dur: 156, saida: 'persianas', C: CenaLetreiro},
  {id: 'recibo', de: 240, dur: 168, saida: 'cai', C: CenaRecibo},
  {id: 'dia', de: 390, dur: 108, saida: 'vira', C: CenaDia},
  {id: 'fecho', de: 480, dur: 60, C: CenaFecho},
];

export const DURACAO_CAMPANHA = 540;

const FAIXAS = 9;

const Saida: React.FC<{tipo?: Cena['saida']; dur: number; children: React.ReactNode}> = ({
  tipo,
  dur,
  children,
}) => {
  const frame = useCurrentFrame();
  const ini = dur - SOBRA;

  if (tipo === 'persianas' && frame < ini) {
    // Antes de a transição começar, a cena é desenhada uma vez só: nove cópias recortadas
    // deixam fios claros nas emendas das faixas.
    return <AbsoluteFill>{children}</AbsoluteFill>;
  }
  if (tipo === 'persianas') {
    // Cada faixa horizontal fecha sobre o próprio centro, uma depois da outra.
    return (
      <AbsoluteFill>
        {Array.from({length: FAIXAS}, (_, k) => {
          const p = prog(frame, ini + k * 1.2, ini + k * 1.2 + 9, suave);
          const topo = ((k + p / 2) / FAIXAS) * 100;
          const base = (100 / FAIXAS) * (FAIXAS - k - 1) + (100 / FAIXAS) * (p / 2);
          return (
            <AbsoluteFill key={k} style={{clipPath: `inset(${topo}% 0 ${base}% 0)`}}>
              {children}
            </AbsoluteFill>
          );
        })}
      </AbsoluteFill>
    );
  }
  if (tipo === 'cai') {
    const p = prog(frame, ini, dur, entrada);
    return (
      <AbsoluteFill
        style={{
          transformOrigin: '50% 100%',
          transform: `translateY(${p * (H + 260)}px) rotate(${p * 8}deg)`,
        }}
      >
        {children}
      </AbsoluteFill>
    );
  }
  if (tipo === 'vira') {
    const p = prog(frame, ini, dur, suave);
    return (
      <AbsoluteFill
        style={{
          transformOrigin: '50% 0%',
          transform: `perspective(2600px) rotateX(${-p * 100}deg)`,
          backfaceVisibility: 'hidden',
        }}
      >
        {children}
      </AbsoluteFill>
    );
  }
  return <AbsoluteFill>{children}</AbsoluteFill>;
};

export const Campanha1010: React.FC = () => (
  <AbsoluteFill style={{background: '#000'}}>
    {CENAS.map((cena, i) => (
      <Sequence
        key={cena.id}
        from={cena.de}
        durationInFrames={cena.dur}
        style={{zIndex: 100 - i * 10}}
      >
        <Saida tipo={cena.saida} dur={cena.dur}>
          <cena.C dur={cena.dur} />
        </Saida>
      </Sequence>
    ))}
  </AbsoluteFill>
);

