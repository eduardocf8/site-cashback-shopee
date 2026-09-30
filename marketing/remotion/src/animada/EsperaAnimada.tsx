import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {CORES} from '../marca';
import {
  CenaFrase,
  CenaGancho,
  CenaMais,
  CenaMarca,
  CenaMinimo,
  CenaSaque,
  CenaSemTaxa,
} from './cenas';
import {Camada, Janela} from './transicoes';

/** A versão animada do vídeo com o gancho "Espera.".
 *
 * Mesmas informações, mesma ordem, mesmos textos - e as cenas 2 e 3 viram uma só, porque
 * são uma frase cortada em duas. O que muda é tudo o que está entre elas: seis transições,
 * cada uma com um motivo (ver transicoes.tsx), a moeda da marca em movimento, números que
 * contam e rolam, e o fechamento com o halo ondulando.
 *
 * As cenas se sobrepõem na duração da transição que as liga: a que sai e a que entra
 * existem juntas por alguns frames. O início de cada uma é o início da anterior, mais a
 * duração dela, menos essa sobreposição. */
type Def = {
  id: string;
  dur: number;
  Cena: React.FC<{dur: number}>;
  /** Transição que liga ESTA cena à seguinte. */
  para?: Janela;
};

const CENAS_ANIMADAS: Def[] = [
  {id: 'gancho', dur: 72, Cena: CenaGancho, para: {tipo: 'iris', dur: 14}},
  {id: 'frase', dur: 148, Cena: CenaFrase, para: {tipo: 'empurraCima', dur: 14}},
  {id: 'minimo', dur: 150, Cena: CenaMinimo, para: {tipo: 'portas', dur: 16}},
  {id: 'mais', dur: 84, Cena: CenaMais, para: {tipo: 'irisBaixo', dur: 14}},
  {id: 'saque', dur: 88, Cena: CenaSaque, para: {tipo: 'empurraLado', dur: 14}},
  {id: 'semtaxa', dur: 62, Cena: CenaSemTaxa, para: {tipo: 'relogio', dur: 16}},
  {id: 'marca', dur: 110, Cena: CenaMarca},
];

const inicios = CENAS_ANIMADAS.reduce<number[]>((acc, cena, i) => {
  if (i === 0) return [0];
  const anterior = CENAS_ANIMADAS[i - 1];
  return [...acc, acc[i - 1] + anterior.dur - (anterior.para?.dur ?? 0)];
}, []);

const ultima = CENAS_ANIMADAS.length - 1;
export const DURACAO_ANIMADA = inicios[ultima] + CENAS_ANIMADAS[ultima].dur;

export const EsperaAnimada: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: CORES.brandStrong}}>
    {CENAS_ANIMADAS.map(({id, dur, Cena, para}, i) => (
      <Sequence key={id} from={inicios[i]} durationInFrames={dur} layout="none">
        <Camada
          id={id}
          z={i * 4}
          dur={dur}
          entra={i > 0 ? CENAS_ANIMADAS[i - 1].para : undefined}
          sai={para}
        >
          <Cena dur={dur} />
        </Camada>
      </Sequence>
    ))}
  </AbsoluteFill>
);
