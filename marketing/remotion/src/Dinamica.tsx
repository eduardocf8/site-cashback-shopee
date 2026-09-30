import React from 'react';
import {
  AbsoluteFill,
  Easing,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import {Apoio, NumeroContando, Palco, SemEntrada, Titulo} from './Base';
import type {TipoDestaque} from './Base';
import {CENAS} from './constantes';
import {FechamentoConteudo} from './Fechamento';
import {MinimoConteudo} from './Minimo';
import {montarLinha} from './Apresentacao';
import {CORES} from './marca';

/** Segunda versão da apresentação: a mesma informação, com mais movimento.
 *
 * O que muda em relação à versão calma - e por que cada coisa está aqui:
 *
 * 1. NÃO EXISTE CORTE. Cada cena empurra a anterior para cima, como quem passa o
 *    dedo no feed. Corte seco é uma pausa de um frame em que a tela não muda de
 *    lugar, e é nessa pausa que o polegar decide rolar. Empurrando, o vídeo nunca
 *    para de se mover.
 * 2. O FUNDO NUNCA PARA. Um zoom lento e contínuo ao longo de cada cena. Sozinho não
 *    se nota; o que se nota é a ausência dele, que faz o quadro parecer um cartaz
 *    fotografado.
 * 3. OS NÚMEROS CONTAM. O olho não desvia de um dígito que muda, e a contagem dá
 *    duração ao valor: "R$ 20" vira resultado em vez de rótulo.
 * 4. O GANCHO ENTRA PALAVRA POR PALAVRA. É a única cena com esse tratamento, porque
 *    é a única em que o espectador ainda não decidiu ficar.
 * 5. O RITMO É MAIS CURTO. 15,6s contra 18,3s, com a mesma informação: o que encolheu
 *    foi o tempo parado depois que cada cena termina de entrar.
 *
 * O que deliberadamente NÃO entrou: partícula, brilho, tremor de câmera, giro de
 * texto e transição de "glitch". Todos aumentam movimento e todos custam a mesma
 * coisa - a peça passa a parecer template, e um produto que guarda dinheiro do
 * usuário não pode parecer template. Movimento aqui serve para conduzir a leitura,
 * e cada efeito acima disputa com ela.
 *
 * Os textos, os números e as ênfases vêm de constantes.ts, os mesmos da versão calma.
 * Só o tempo de cada cena é próprio daqui. */
const TRANSICAO = 12;

/** Quanto tempo cada cena fica, nesta versão. Os ids são os de constantes.ts; o que
 * encolheu em relação à calma foi o tempo parado, não o tempo de leitura. */
const DURACOES: Record<string, number> = {
  compra: 62,
  // 42 e não 36: o grifo leva 14 frames para abrir, e numa cena mais curta ele
  // terminaria já com o quadro saindo - o espectador veria o efeito, não a palavra.
  condicao: 42,
  promessa: 40,
  minimo: 108,
  mais: 42,
  saque: 54,
  semtaxa: 38,
  marca: 76,
};

const FUNDOS: Record<string, string> = {
  compra: 'fundo-roxo.png',
  condicao: 'fundo-roxo.png',
  promessa: 'fundo-roxo.png',
  minimo: 'fundo-diagonal.png',
  mais: 'fundo-roxo.png',
  saque: 'fundo-claro.png',
  semtaxa: 'fundo-claro.png',
  marca: 'fundo-halo.png',
};

const CLAROS = new Set(['saque', 'semtaxa']);

/** Um quadro: o fundo que desliza e dá zoom, e o conteúdo que entra depois.
 *
 * O conteúdo viaja junto com o fundo, e não entra depois que o quadro para. A
 * primeira versão fazia o contrário, e o resultado era meio segundo de tela sem texto
 * a cada troca - oito vezes num vídeo de quinze segundos, que é exatamente o buraco
 * em que o polegar rola. Viajando junto, o empurrão é a própria entrada do texto: por
 * isso a versão dinâmica desliga o `Entra` de cada elemento (ver SemEntrada, em
 * Base.tsx) e desloca em TRANSICAO tudo que acontece depois que o quadro para. */
const Quadro: React.FC<{
  fundo: string;
  claro: boolean;
  duracao: number;
  primeira?: boolean;
  ultima?: boolean;
  children: React.ReactNode;
}> = ({fundo, claro, duracao, primeira, ultima, children}) => {
  const frame = useCurrentFrame();

  // A primeira cena não desliza: não há nada atrás dela para empurrar, e entrar de
  // baixo faria o vídeo abrir com meio segundo de tela vazia - justamente o meio
  // segundo em que o espectador decide se fica.
  const entrando = primeira
    ? 0
    : interpolate(frame, [0, TRANSICAO], [1920, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.out(Easing.cubic),
      });
  // A última cena também não sai: não há nada depois dela para entrar no lugar, e
  // sair deixaria o vídeo terminando num fundo vazio, sem a marca - justamente o
  // quadro que fica parado na tela quando o vídeo acaba.
  const saindo = ultima
    ? 0
    : interpolate(frame, [duracao, duracao + TRANSICAO], [0, -1920], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.in(Easing.cubic),
      });
  // A saída de uma cena e a entrada da seguinte são a MESMA janela de tempo. Uma sobe
  // e a outra vem de baixo com a mesma curva, então as duas viajam coladas e a tela
  // nunca mostra vão.
  const y = entrando + saindo;

  // O zoom atravessa a cena inteira, transições incluídas. Reiniciar a cada quadro
  // daria um salto visível justamente no momento em que o quadro está parado.
  const zoom = interpolate(frame, [0, duracao + TRANSICAO], [1, 1.07], {
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{transform: `translateY(${y}px)`}}>
      <AbsoluteFill
        style={{backgroundColor: claro ? CORES.paper : CORES.brandStrong, overflow: 'hidden'}}
      >
        {/* O zoom é scale e não largura maior: a imagem tem a proporção exata do
            quadro, e esticá-la para caber o zoom deformaria as manchas do fundo. Com
            scale ela cresce a partir do centro e o excedente é cortado pelo overflow
            do pai, que é o que um zoom de câmera faz. */}
        <Img
          src={staticFile(fundo)}
          style={{width: 1080, height: 1920, transform: `scale(${zoom})`}}
        />
        <Palco>{children}</Palco>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/** O gancho, revelado palavra por palavra.
 *
 * Cada palavra ocupa o lugar dela desde o primeiro frame - o que muda é só a tinta e
 * um deslocamento de 22px. Revelando com layout, a linha se remontaria a cada palavra
 * e a frase dançaria enquanto é lida. */
const ATRASO_POR_PALAVRA = 3;

const Gancho: React.FC<{
  texto: string;
  corpo: number;
  destaque: {tipo: 'pintura'; inicio: number};
  atraso: number;
}> = ({texto, corpo, destaque, atraso}) => {
  const frame = useCurrentFrame();
  let ordem = 0;
  return (
    <Titulo corpo={corpo}>
      {texto.split('\n').map((linha) => (
        <div key={linha}>
          {linha.split(' ').map((palavra) => {
            const inicio = atraso + ordem++ * ATRASO_POR_PALAVRA;
            const p = interpolate(frame - inicio, [0, 9], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
              easing: Easing.out(Easing.cubic),
            });
            return (
              <span
                key={palavra}
                style={{
                  display: 'inline-block',
                  opacity: p,
                  transform: `translateY(${(1 - p) * 22}px)`,
                }}
              >
                {montarLinha(palavra, false, destaque)}
                {' '}
              </span>
            );
          })}
        </div>
      ))}
    </Titulo>
  );
};

/** Cena de número com o valor contando. Os rótulos são os mesmos da versão calma. */
const NumeroContado: React.FC<{
  claro: boolean;
  acima?: string;
  valor: string;
  abaixo: string;
}> = ({claro, acima, valor, abaixo}) => (
  <>
    {acima ? (
      <Apoio claro={claro} corpo={CORPO_ROTULO} margemTopo={0} margemBase={32}>
        {acima}
      </Apoio>
    ) : null}
    {/* A contagem começa com o empurrão, não depois dele: o quadro pousa com o número
        já correndo. Esperando, o espectador via "R$ 0" parado por meio segundo - e
        zero é a única quantia que este vídeo não quer mostrar. */}
    <NumeroContando
      valor={valor}
      cor={claro ? CORES.success : CORES.highlight}
      duracao={26}
    />
    <Apoio claro={claro} corpo={CORPO_ROTULO} margemTopo={20}>
      {abaixo}
    </Apoio>
  </>
);

/** Texto que já chega montado, trazido pelo empurrão do quadro.
 *
 * A cena de lista é a única exceção: as duas linhas vêm com 6 frames de diferença
 * uma da outra, ainda durante o empurrão. Assim "sem mensalidade" e "sem taxa"
 * continuam sendo dois fatos e não uma frase, que é o que a versão calma consegue
 * com a entrada escalonada - só que aqui sem parar o quadro para isso. */
const ATRASO_ENTRE_LINHAS = 6;

const TextoCarregado: React.FC<{
  claro: boolean;
  texto: string;
  corpo?: number;
  lista?: boolean;
  destaque?: {tipo: TipoDestaque; inicio: number};
}> = ({claro, texto, corpo, lista, destaque}) => {
  const frame = useCurrentFrame();
  return (
    <Titulo claro={claro} corpo={corpo}>
      {texto.split('\n').map((linha, i) => {
        const atrasoLinha = i * ATRASO_ENTRE_LINHAS;
        // A primeira linha vem inteira com o empurrão; só as seguintes atrasam. Se
        // todas desbotassem, o quadro pousaria vazio e a lista perderia o empurrão
        // como entrada.
        const p =
          lista && i > 0
            ? interpolate(frame - atrasoLinha, [0, 10], [0, 1], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
                easing: Easing.out(Easing.cubic),
              })
            : 1;
        return (
          <div
            key={linha}
            style={{opacity: p, transform: `translateY(${(1 - p) * 40}px)`}}
          >
            {montarLinha(linha, claro, destaque)}
          </div>
        );
      })}
    </Titulo>
  );
};

const CORPO_ROTULO = 56;

const inicios = CENAS.reduce<number[]>(
  (acc, cena, i) => [...acc, (acc[i - 1] ?? 0) + (i === 0 ? 0 : DURACOES[CENAS[i - 1].id])],
  [],
);

export const DURACAO_DINAMICA =
  CENAS.reduce((total, cena) => total + DURACOES[cena.id], 0) + TRANSICAO;

export const Dinamica: React.FC = () => (
  <SemEntrada.Provider value>
    <AbsoluteFill style={{backgroundColor: CORES.brandStrong}}>
      {CENAS.map((cena, i) => {
        const duracao = DURACOES[cena.id];
        // Tudo que acontece dentro da cena conta a partir do instante em que o quadro
        // para de andar - menos na primeira, que já nasce parada.
        const atraso = i === 0 ? 0 : TRANSICAO;
        const claro = CLAROS.has(cena.id);
        // O instante da ênfase é outro aqui. Na versão calma ela espera o texto
        // terminar de entrar; nesta o texto já chega inteiro, então ela dispara assim
        // que o quadro para. O gancho é a exceção: as palavras ainda estão sendo
        // reveladas uma a uma, e pintar "cashback" antes de ela existir na tela
        // pintaria o nada.
        const destaque =
          'destaque' in cena
            ? {tipo: cena.destaque.tipo, inicio: atraso + (cena.id === 'compra' ? 34 : 2)}
            : undefined;
        return (
          <Sequence
            key={cena.id}
            from={inicios[i]}
            // A faixa de cada cena dura o tempo dela MAIS a transição: é esse excedente
            // que mantém a cena montada enquanto ela sai, com a seguinte já entrando.
            durationInFrames={duracao + TRANSICAO}
          >
            <Quadro
              fundo={FUNDOS[cena.id]}
              claro={claro}
              duracao={duracao}
              primeira={i === 0}
              ultima={i === CENAS.length - 1}
            >
              {'convite' in cena ? (
                <FechamentoConteudo
                  convite={cena.convite}
                  dominio={cena.dominio}
                  sufixo={cena.sufixo}
                  atraso={atraso}
                />
              ) : 'primeiro' in cena ? (
                <MinimoConteudo
                  primeiro={cena.primeiro}
                  segundo={cena.segundo}
                  otico={cena.otico}
                  oticoSegundo={cena.oticoSegundo}
                  condicao={cena.condicao}
                  atraso={atraso}
                  contando
                />
              ) : 'numero' in cena ? (
                <NumeroContado
                  claro={claro}
                  acima={'acima' in cena ? cena.acima : undefined}
                  valor={cena.numero}
                  abaixo={cena.abaixo}
                />
              ) : cena.id === 'compra' ? (
                <Gancho
                  texto={cena.texto}
                  corpo={cena.corpo}
                  destaque={destaque as {tipo: 'pintura'; inicio: number}}
                  atraso={atraso}
                />
              ) : (
                <TextoCarregado
                  claro={claro}
                  texto={cena.texto}
                  lista={cena.entrada === 'linhas'}
                  destaque={destaque}
                />
              )}
            </Quadro>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  </SemEntrada.Provider>
);
