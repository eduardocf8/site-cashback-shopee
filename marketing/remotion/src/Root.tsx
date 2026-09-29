import React from 'react';
import {Composition} from 'remotion';
import {Apresentacao} from './Apresentacao';
import {DURACAO, FPS} from './constantes';
import {DURACAO_DINAMICA, Dinamica} from './Dinamica';

/** Duas composições, mesma informação.
 *
 * "Apresentacao" é a versão calma: corte seco entre cenas, quadro parado, números
 * prontos. "Dinamica" é a mesma coisa com as cenas se empurrando, o fundo em zoom
 * lento e os números contando - mais curta e com mais movimento.
 *
 * As duas leem os mesmos textos e os mesmos números de constantes.ts. Só o tempo de
 * cada cena é próprio de cada uma, e é por isso que dá para manter as duas: corrigir
 * uma frase corrige nos dois vídeos. */
export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Apresentacao"
      component={Apresentacao}
      durationInFrames={DURACAO}
      fps={FPS}
      width={1080}
      height={1920}
    />
    <Composition
      id="Dinamica"
      component={Dinamica}
      durationInFrames={DURACAO_DINAMICA}
      fps={FPS}
      width={1080}
      height={1920}
    />
  </>
);
