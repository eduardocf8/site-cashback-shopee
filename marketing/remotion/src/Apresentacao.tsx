import React from 'react';
import {AbsoluteFill, Img, interpolate, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {Apoio, Cena, Entra, Numero, Titulo} from './Base';
import {CENAS} from './constantes';
import {CORES, FONTE} from './marca';

const inicios = CENAS.reduce<number[]>(
  (acc, cena, i) => [...acc, (acc[i - 1] ?? 0) + (CENAS[i - 1]?.frames ?? 0)],
  [],
);

/** Fecha o vídeo: o wordmark e o endereço sobre o fundo halo.
 *
 * O halo é o único fundo da família em que o miolo NÃO fica vazio - ele existe para
 * emoldurar, e é exatamente o que uma cena de assinatura pede. */
const Marca: React.FC<{endereco: string}> = ({endereco}) => {
  const frame = useCurrentFrame();
  const escala = interpolate(frame, [0, 70], [1, 1.05]);
  return (
    <Cena fundo="fundo-halo.png">
      <div style={{textAlign: 'center', transform: `scale(${escala})`}}>
        <Entra>
          <Img src={staticFile('wordmark-claro.png')} style={{width: 620, margin: '0 auto'}} />
        </Entra>
        <Entra atraso={12}>
          <div
            style={{
              fontFamily: FONTE.texto,
              fontSize: 56,
              fontWeight: 600,
              marginTop: 44,
              color: CORES.highlight,
            }}
          >
            {endereco}
          </div>
        </Entra>
      </div>
    </Cena>
  );
};

export const Apresentacao: React.FC = () => (
  <AbsoluteFill>
    {CENAS.map((cena, i) => (
      <Sequence key={cena.id} from={inicios[i]} durationInFrames={cena.frames}>
        {cena.id === 'marca' ? (
          <Marca endereco={(cena as {endereco: string}).endereco} />
        ) : 'numero' in cena ? (
          // As cenas de número viram a cor de fundo junto: a diagonal na promessa, o
          // claro na prova. A virada de cor marca a passagem de "promete" para "mostra".
          <Cena fundo={cena.id === 'saque' ? 'fundo-claro.png' : 'fundo-diagonal.png'} claro={cena.id === 'saque'}>
            <Entra>
              <Numero cor={cena.id === 'saque' ? CORES.success : CORES.highlight}>{cena.numero}</Numero>
            </Entra>
            <Entra atraso={8}>
              <Apoio claro={cena.id === 'saque'}>{cena.apoio}</Apoio>
            </Entra>
          </Cena>
        ) : (
          <Cena fundo={cena.id === 'semtaxa' ? 'fundo-claro.png' : 'fundo-roxo.png'} claro={cena.id === 'semtaxa'}>
            <Entra>
              <Titulo claro={cena.id === 'semtaxa'}>{(cena as {texto: string}).texto}</Titulo>
            </Entra>
          </Cena>
        )}
      </Sequence>
    ))}
  </AbsoluteFill>
);
