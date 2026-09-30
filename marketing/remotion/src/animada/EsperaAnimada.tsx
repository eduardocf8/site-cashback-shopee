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

/** Toda transição dura uma batida (16 quadros, que é 16,17 a 111 BPM) e começa em cima de
 * uma batida da música. A cena que entra recebe o primeiro movimento exatamente quando a
 * transição termina, que é a batida seguinte. As durações abaixo foram escolhidas para
 * isso: cada uma é a distância entre duas batidas mais a transição que a fecha.
 *
 * A grade é `17,25 + 16,17 k` quadros (música começando junto com o vídeo). O drop da
 * música entra na batida 19 (quadro 325), que é onde as portas se abrem. */
const BATIDA = 16;

const CENAS_ANIMADAS: Def[] = [
  {id: 'gancho', dur: 82, Cena: CenaGancho, para: {tipo: 'iris', dur: BATIDA}},
  {id: 'frase', dur: 145, Cena: CenaFrase, para: {tipo: 'empurraCima', dur: BATIDA}},
  {id: 'minimo', dur: 146, Cena: CenaMinimo, para: {tipo: 'portas', dur: BATIDA}},
  {id: 'mais', dur: 80, Cena: CenaMais, para: {tipo: 'irisBaixo', dur: BATIDA}},
  {id: 'saque', dur: 81, Cena: CenaSaque, para: {tipo: 'empurraLado', dur: BATIDA}},
  {id: 'semtaxa', dur: 64, Cena: CenaSemTaxa, para: {tipo: 'relogio', dur: BATIDA}},
  {id: 'marca', dur: 113, Cena: CenaMarca},
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
