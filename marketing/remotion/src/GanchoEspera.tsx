import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Cena, Entra, Titulo} from './Base';
import {CORES, FONTE} from './marca';

/** O gancho em dois tempos: a pergunta, uma pausa, e "Espera." como interrupção.
 *
 * A pausa é o que faz o gancho. Com as três linhas entrando juntas, "Espera." era só
 * mais uma linha; chegando sozinha depois de um segundo de pergunta parada, ela lê como
 * alguém cortando a frase. O que segura o espectador é a expectativa - a pergunta fica
 * no ar e o cérebro espera a resposta.
 *
 * O espaço de "Espera." é reservado desde o primeiro frame. Se o bloco crescesse quando
 * ela chega, a pergunta pularia para cima no exato instante em que o olho precisa estar
 * na palavra nova. A consequência é a pergunta nascer um pouco acima do meio da tela:
 * é o preço de nada se mexer depois.
 *
 * A entrada é uma batida: a palavra chega grande, encolhe até o tamanho e passa um
 * pouco dele antes de assentar (mola com pouco amortecimento). Ao mesmo tempo a pergunta
 * escurece, e o olho é conduzido para onde está o peso. Sem tremor de tela nem brilho:
 * um único movimento, e ele diz "para". */
const AMORTECIMENTO = 9;
const ESCALA_INICIAL = 1.45;

export const GanchoEspera: React.FC<{
  pergunta: string;
  palavra: string;
  corpo: number;
  corpoPalavra: number;
  chega: number;
}> = ({pergunta, palavra, corpo, corpoPalavra, chega}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const mola = spring({frame: frame - chega, fps, config: {damping: AMORTECIMENTO, stiffness: 220}});
  const escala = interpolate(mola, [0, 1], [ESCALA_INICIAL, 1]);
  // Opacidade em poucos frames e em interpolate separado: a mola passa de 1 no
  // overshoot e a tinta "piscaria".
  const aparece = interpolate(frame - chega, [0, 3], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const escurece = interpolate(frame - chega, [0, 8], [1, 0.5], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <Cena fundo="fundo-roxo.png">
      <div style={{opacity: escurece}}>
        <Entra>
          <Titulo corpo={corpo}>{pergunta}</Titulo>
        </Entra>
      </div>
      <div
        style={{
          fontFamily: FONTE.texto,
          fontSize: corpoPalavra,
          fontWeight: 700,
          lineHeight: 1.04,
          letterSpacing: '-0.04em',
          color: CORES.highlight,
          marginTop: 8,
          opacity: aparece,
          transform: `scale(${escala})`,
        }}
      >
        {palavra}
      </div>
    </Cena>
  );
};
