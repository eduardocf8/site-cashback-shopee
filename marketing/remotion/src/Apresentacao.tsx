import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {Apoio, Cena, Entra, Numero, Titulo} from './Base';
import {CENAS} from './constantes';
import {Fechamento} from './Fechamento';
import {CORES} from './marca';

const inicios = CENAS.reduce<number[]>(
  (acc, _cena, i) => [...acc, (acc[i - 1] ?? 0) + (CENAS[i - 1]?.frames ?? 0)],
  [],
);

/** Rótulo e respiro das cenas de número.
 *
 * "saque a partir de / R$ 20 / no Pix" é uma frase só, quebrada em três linhas. Só lê
 * como frase se as três linhas estiverem à mesma distância uma da outra e mais perto
 * entre si do que da borda - por isso o mesmo GRAFO em cima e embaixo do número, e não
 * a margem padrão do Apoio (que existe para texto solto). O rótulo também cresce junto
 * com o número: em 44px ao lado de um algarismo de 300px ele virava legenda. */
const CORPO_ROTULO = 56;
// Os dois respiros não são iguais de propósito. O rótulo de cima termina em descida
// ("saque a partir de" tem q e p), e descida é traço fino: o olho mede a distância a
// partir da linha de base, não da ponta do q. O de baixo começa em maiúscula cheia.
// Com o mesmo número nos dois lados o bloco parece encostado em cima e solto embaixo.
const GRAFO_ACIMA = 32;
const GRAFO_ABAIXO = 20;

/** As cenas de número viram a cor de fundo junto: a diagonal na promessa, o claro na
 * prova. A troca de cor marca a passagem de "promete" para "mostra" - todo site de
 * cashback promete, e o que separa é mostrar como o dinheiro sai. */
const CenaNumero: React.FC<{
  claro: boolean;
  acima?: string;
  numero: string;
  otico?: number;
  abaixo: string;
}> = ({claro, acima, numero, otico, abaixo}) => (
  <Cena fundo={claro ? 'fundo-claro.png' : 'fundo-diagonal.png'} claro={claro}>
    {acima ? (
      <Entra>
        <Apoio claro={claro} corpo={CORPO_ROTULO} margemTopo={0} margemBase={GRAFO_ACIMA}>
          {acima}
        </Apoio>
      </Entra>
    ) : null}
    <Entra atraso={acima ? 6 : 0}>
      <Numero cor={claro ? CORES.success : CORES.highlight} otico={otico}>
        {numero}
      </Numero>
    </Entra>
    <Entra atraso={acima ? 12 : 8}>
      <Apoio claro={claro} corpo={CORPO_ROTULO} margemTopo={GRAFO_ABAIXO}>
        {abaixo}
      </Apoio>
    </Entra>
  </Cena>
);

export const Apresentacao: React.FC = () => (
  <AbsoluteFill>
    {CENAS.map((cena, i) => (
      <Sequence key={cena.id} from={inicios[i]} durationInFrames={cena.frames}>
        {'convite' in cena ? (
          <Fechamento convite={cena.convite} dominio={cena.dominio} sufixo={cena.sufixo} />
        ) : 'numero' in cena ? (
          <CenaNumero
            claro={cena.id === 'saque'}
            acima={'acima' in cena ? cena.acima : undefined}
            numero={cena.numero}
            otico={'otico' in cena ? cena.otico : undefined}
            abaixo={cena.abaixo}
          />
        ) : (
          <Cena fundo={cena.id === 'semtaxa' ? 'fundo-claro.png' : 'fundo-roxo.png'} claro={cena.id === 'semtaxa'}>
            <Entra>
              <Titulo claro={cena.id === 'semtaxa'} corpo={'corpo' in cena ? cena.corpo : undefined}>
                {cena.texto}
              </Titulo>
            </Entra>
          </Cena>
        )}
      </Sequence>
    ))}
  </AbsoluteFill>
);
