import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Apoio, Cena, Entra, Numero} from './Base';

/** A cena do mínimo, em dois tempos.
 *
 * Primeiro tempo: "1% / no mínimo, em toda compra" - o piso que vale para qualquer
 * compra. Segundo tempo: da frase sobra só a palavra "mínimo", que sobe e vira o
 * rótulo do número; o 1% rola para cima e sai, o 1,6% rola para cima e entra, e
 * embaixo aparece a condição. O número subir na tela é a própria frase: o mínimo sobe.
 *
 * Por que a palavra viaja em vez de a cena cortar para um layout novo: é a mesma
 * palavra, e vê-la andar é o que liga os dois números. Com um corte, o espectador leria
 * dois fatos soltos e teria de montar a relação sozinho.
 *
 * Os dois números saem de cashback_shopee/settings.py, não de estimativa:
 * CASHBACK_MINIMO_VENDA_INDIRETA = 1 e CASHBACK_MINIMO_VENDA_DIRETA = 1.6. Por isso a
 * condição embaixo fala em "forma que você compra" - é literalmente o que separa os
 * dois pisos, venda indireta e venda direta.
 *
 * A cena inteira é posicionada em absoluto, e não empilhada em flex, porque no segundo
 * tempo os elementos precisam se cruzar: a palavra sai de baixo do número e vai para
 * cima dele enquanto outra coisa ocupa o lugar que ela deixou. Empilhado, cada saída
 * refluiria o resto e a cena andaria inteira a cada frame. As três alturas são as
 * mesmas medidas na tela do saque, para as duas cenas de número baterem. */
const Y_ACIMA = 724;
const Y_NUMERO = 944;
const Y_ABAIXO = 1164;

/** O segundo tempo, beat a beat.
 *
 * A ordem não é enfeite: os três movimentos passam pelo MESMO ponto da tela, o meio,
 * e se dois acontecerem juntos eles se atravessam. Então o meio é esvaziado antes de
 * ser cruzado, e só volta a ser ocupado depois:
 *
 *   40  o resto da frase some, e "mínimo" fica sozinho embaixo
 *   42  o 1% sobe e sai - o meio da tela fica vazio
 *   50  "mínimo" atravessa o meio agora vazio e para em cima do número
 *   60  o 1,6% sobe e entra no lugar que o 1% deixou
 *   74  a condição aparece embaixo, no lugar que "mínimo" deixou
 *
 * Antes dos 40 é 1,3s de leitura do primeiro tempo: o suficiente para "1% no mínimo"
 * virar informação, que é o que a troca depois nega. */
const TROCA = 40;
const SOBE_PALAVRA = TROCA + 10;
const ENTRA_SEGUNDO = TROCA + 20;
const ENTRA_CONDICAO = TROCA + 34;
const ROLAGEM = 110;

const CORPO_ROTULO = 56;

const Faixa: React.FC<{
  y: number;
  transformar?: string;
  opacidade?: number;
  children: React.ReactNode;
}> = ({y, transformar, opacidade, children}) => (
  <div
    style={{
      position: 'absolute',
      left: 0,
      right: 0,
      top: y,
      textAlign: 'center',
      transform: `translateY(-50%) ${transformar ?? ''}`,
      opacity: opacidade,
    }}
  >
    {children}
  </div>
);

export const Minimo: React.FC<{
  primeiro: string;
  segundo: string;
  otico?: number;
  oticoSegundo?: number;
  condicao: string;
}> = ({primeiro, segundo, otico, oticoSegundo, condicao}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const sobe = spring({frame: frame - SOBE_PALAVRA, fps, config: {damping: 200, mass: 1.1}});
  const saiPrimeiro = spring({frame: frame - (TROCA + 2), fps, config: {damping: 200}});
  const entraSegundo = spring({frame: frame - ENTRA_SEGUNDO, fps, config: {damping: 200}});

  const faixa = (de: number, ate: number) =>
    interpolate(frame, [de, ate], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  // O resto da frase encolhe a largura junto com a opacidade. A linha é centralizada,
  // então encolher é o que recentraliza "mínimo" sozinho - o mesmo recurso do ".com"
  // no fechamento, e pelo mesmo motivo: ninguém precisa adivinhar quantos pixels.
  // A opacidade cai em 6 frames e a largura leva 14. A ordem importa: a linha é
  // centralizada, então o que sobra dentro de uma caixa que encolhe é o MEIO do texto,
  // não o começo. Encolhendo junto com a tinta ainda visível, o espectador via
  // fragmentos soltos - um "r", um ", em" - que pareciam falha de render. Sumindo
  // primeiro, a largura fecha com a caixa já vazia.
  const tinta = 1 - faixa(TROCA, TROCA + 6);
  const largura = 1 - faixa(TROCA, TROCA + 14);
  const resto = (texto: string) => (
    <span
      style={{
        display: 'inline-block',
        overflow: 'hidden',
        whiteSpace: 'pre',
        opacity: tinta,
        maxWidth: `${largura * texto.length}ch`,
      }}
    >
      {texto}
    </span>
  );

  return (
    <Cena fundo="fundo-diagonal.png">
      {/* primeiro número: entra crescendo, sai rolando para cima */}
      <Faixa
        y={Y_NUMERO}
        transformar={`translateY(${interpolate(saiPrimeiro, [0, 1], [0, -ROLAGEM])}px)`}
        opacidade={1 - faixa(TROCA + 2, TROCA + 14)}
      >
        <Entra tipo="cresce">
          <Numero otico={otico}>{primeiro}</Numero>
        </Entra>
      </Faixa>

      {/* segundo número: chega por baixo, no lugar do primeiro */}
      <Faixa
        y={Y_NUMERO}
        transformar={`translateY(${interpolate(entraSegundo, [0, 1], [ROLAGEM, 0])}px)`}
        opacidade={faixa(ENTRA_SEGUNDO, ENTRA_SEGUNDO + 10)}
      >
        <Numero otico={oticoSegundo}>{segundo}</Numero>
      </Faixa>

      {/* a frase de baixo, da qual só "mínimo" sobrevive e sobe */}
      <Faixa y={Y_ABAIXO}>
        <Entra atraso={8}>
          <Apoio corpo={CORPO_ROTULO} margemTopo={0}>
            {resto('no ')}
            <span
              style={{
                display: 'inline-block',
                transform: `translateY(${interpolate(sobe, [0, 1], [0, Y_ACIMA - Y_ABAIXO])}px)`,
              }}
            >
              mínimo
            </span>
            {resto(', em toda compra')}
          </Apoio>
        </Entra>
      </Faixa>

      {/* a condição, que entra depois que o número já trocou */}
      <Faixa y={Y_ABAIXO} opacidade={faixa(ENTRA_CONDICAO, ENTRA_CONDICAO + 12)}>
        <Apoio corpo={CORPO_ROTULO} margemTopo={0}>
          {condicao.split('\n').map((linha) => (
            <div key={linha}>{linha}</div>
          ))}
        </Apoio>
      </Faixa>
    </Cena>
  );
};
