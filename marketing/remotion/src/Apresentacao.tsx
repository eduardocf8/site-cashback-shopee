import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {Apoio, Cena, Destaque, Entra, Numero, Titulo} from './Base';
import type {Entrada, TipoDestaque} from './Base';
import {Minimo} from './Minimo';
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
export const ConteudoNumero: React.FC<{
  claro: boolean;
  acima?: string;
  numero: string;
  abaixo: string;
  entrada: Entrada;
}> = ({claro, acima, numero, abaixo, entrada}) => (
  <>
    {acima ? (
      <Entra>
        <Apoio claro={claro} corpo={CORPO_ROTULO} margemTopo={0} margemBase={GRAFO_ACIMA}>
          {acima}
        </Apoio>
      </Entra>
    ) : null}
    {/* O tipo vale para o número, não para os rótulos: se a cena inteira crescesse,
        o bloco todo "respiraria" e o peso do algarismo se perderia no meio. */}
    <Entra atraso={acima ? 6 : 0} tipo={entrada}>
      <Numero cor={claro ? CORES.success : CORES.highlight}>
        {numero}
      </Numero>
    </Entra>
    <Entra atraso={acima ? 12 : 8}>
      <Apoio claro={claro} corpo={CORPO_ROTULO} margemTopo={GRAFO_ABAIXO}>
        {abaixo}
      </Apoio>
    </Entra>
  </>
);

const CenaNumero: React.FC<React.ComponentProps<typeof ConteudoNumero>> = (props) => (
  <Cena fundo={props.claro ? 'fundo-claro.png' : 'fundo-diagonal.png'} claro={props.claro}>
    <ConteudoNumero {...props} />
  </Cena>
);

/** Cena de texto.
 *
 * Em `linhas` o bloco é quebrado nas próprias quebras que o texto já declara, e cada
 * linha entra 7 frames depois da anterior. 7 é o menor intervalo em que a pausa ainda
 * se percebe a 30fps - abaixo disso as linhas parecem entrar juntas, e o efeito vira
 * só um borrão. Nos outros tipos o texto continua sendo um bloco só: quebrar por
 * quebrar faria a frase perder a unidade.
 *
 * O asterisco marca a palavra em destaque. Marcar dentro do próprio texto, e não num
 * campo separado com a palavra repetida, evita o erro silencioso de mudar a frase e
 * deixar para trás um destaque apontando para uma palavra que não existe mais. */
const ATRASO_ENTRE_LINHAS = 7;

export const montarLinha = (
  linha: string,
  claro: boolean,
  destaque?: {tipo: TipoDestaque; inicio: number},
) =>
  // split com grupo de captura devolve os pedaços intercalados: índice par é texto
  // comum, ímpar é o que estava entre asteriscos.
  linha.split(/\*([^*]+)\*/).map((pedaco, i) =>
    i % 2 === 1 && destaque ? (
      <Destaque key={i} tipo={destaque.tipo} inicio={destaque.inicio} claro={claro}>
        {pedaco}
      </Destaque>
    ) : (
      <React.Fragment key={i}>{pedaco}</React.Fragment>
    ),
  );

export const ConteudoTexto: React.FC<{
  claro: boolean;
  texto: string;
  corpo?: number;
  entrada: Entrada;
  destaque?: {tipo: TipoDestaque; inicio: number};
}> = ({claro, texto, corpo, entrada, destaque}) => {
  const linhas = texto.split('\n');
  if (entrada === 'linhas') {
    return (
      <>
        {linhas.map((linha, i) => (
          <Entra key={linha} atraso={i * ATRASO_ENTRE_LINHAS}>
            <Titulo claro={claro} corpo={corpo}>
              <div>{montarLinha(linha, claro, destaque)}</div>
            </Titulo>
          </Entra>
        ))}
      </>
    );
  }
  return (
    <Entra tipo={entrada}>
      <Titulo claro={claro} corpo={corpo}>
        {linhas.map((linha) => (
          <div key={linha}>{montarLinha(linha, claro, destaque)}</div>
        ))}
      </Titulo>
    </Entra>
  );
};

const CenaTexto: React.FC<React.ComponentProps<typeof ConteudoTexto>> = (props) => (
  <Cena fundo={props.claro ? 'fundo-claro.png' : 'fundo-roxo.png'} claro={props.claro}>
    <ConteudoTexto {...props} />
  </Cena>
);

export const Apresentacao: React.FC = () => (
  <AbsoluteFill>
    {CENAS.map((cena, i) => (
      <Sequence key={cena.id} from={inicios[i]} durationInFrames={cena.frames}>
        {'convite' in cena ? (
          <Fechamento convite={cena.convite} dominio={cena.dominio} sufixo={cena.sufixo} />
        ) : 'primeiro' in cena ? (
          <Minimo
            primeiro={cena.primeiro}
            segundo={cena.segundo}
            otico={cena.otico}
            oticoSegundo={cena.oticoSegundo}
            condicao={cena.condicao}
          />
        ) : 'numero' in cena ? (
          <CenaNumero
            claro={cena.id === 'saque'}
            acima={'acima' in cena ? cena.acima : undefined}
            numero={cena.numero}
            abaixo={cena.abaixo}
            entrada={cena.entrada}
          />
        ) : (
          <CenaTexto
            claro={cena.id === 'semtaxa'}
            texto={cena.texto}
            corpo={'corpo' in cena ? cena.corpo : undefined}
            entrada={cena.entrada}
            destaque={'destaque' in cena ? cena.destaque : undefined}
          />
        )}
      </Sequence>
    ))}
  </AbsoluteFill>
);
