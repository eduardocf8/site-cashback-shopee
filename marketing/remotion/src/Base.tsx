import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  interpolateColors,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {CORES, FONTE, SEGURO} from './marca';

/** Fundo da cena + a faixa segura onde o texto pode cair.
 *
 * O fundo entra como imagem e não como cor chapada: são os fundos da família da marca
 * (marketing/fundos-marca), desenhados para deixar o miolo livre. */
export const Cena: React.FC<{fundo: string; children: React.ReactNode; claro?: boolean}> = ({
  fundo,
  children,
  claro,
}) => (
  <AbsoluteFill style={{backgroundColor: claro ? CORES.paper : CORES.brandStrong}}>
    <Img src={staticFile(fundo)} style={{width: 1080, height: 1920}} />
    <AbsoluteFill
      style={{
        paddingTop: SEGURO.topo,
        paddingBottom: SEGURO.base,
        paddingLeft: SEGURO.lateral,
        paddingRight: SEGURO.lateral,
        justifyContent: 'center',
        // Tudo centralizado: em vídeo o olho já está no meio da tela, e texto à
        // esquerda obriga a varrer de volta a cada corte. Em peça estática a borda
        // reta ajuda a ler; aqui, com um corte a cada dois segundos, atrapalha.
        alignItems: 'center',
        textAlign: 'center',
      }}
    >
      {children}
    </AbsoluteFill>
  </AbsoluteFill>
);

/** As entradas possíveis. São quatro, não oito.
 *
 * A tentação, num vídeo de oito cenas, é dar uma animação diferente para cada uma.
 * O resultado é o contrário do pretendido: com oito movimentos diferentes em 15
 * segundos, o espectador para de ler o texto e começa a assistir às transições, e o
 * vídeo passa a parecer demonstração de template. O que dá dinâmica é o movimento
 * *dizer* alguma coisa - então cada entrada aqui tem um papel, e cenas com o mesmo
 * papel repetem a mesma entrada de propósito.
 *
 * - `sobe`    afirmação solta. É a calma, e é a padrão.
 * - `desliza` frase que continua. As cenas 2 e 3 são uma frase só cortada em duas;
 *             entrando do mesmo lado, o olho lê "ainda é a mesma frase". Se cada uma
 *             entrasse de um jeito, a frase se partia em duas ideias.
 * - `cresce`  número. Escala em vez de deslocamento, porque o que o número faz na
 *             cena é aparecer com peso, não chegar de algum lugar.
 * - `linhas`  lista. Cada linha entra por conta, e a pausa entre elas é o que
 *             transforma "sem mensalidade, sem taxa" em dois fatos e não numa frase. */
export type Entrada = 'sobe' | 'desliza' | 'cresce' | 'linhas';

/** Quanto o texto anda na horizontal em `desliza`.
 *
 * O teto não é estético: as duas cenas que deslizam param com 140px de margem, e a
 * área segura do Instagram pede 90 - então 48px é o máximo que o texto pode recuar
 * sem, no primeiro frame, começar fora dela. Na prática ele ainda está transparente
 * nesse ponto, mas margem que só vale enquanto ninguém vê não é margem. */
const DESLOCAMENTO_LATERAL = 48;

/** Entrada de um elemento: aparece, e o jeito de aparecer vem do tipo.
 *
 * A mola dá a desaceleração; a opacidade entra em interpolate separado porque mola em
 * opacidade passa de 1 no overshoot e a tinta "pisca". */
export const Entra: React.FC<{
  atraso?: number;
  tipo?: Entrada;
  children: React.ReactNode;
}> = ({atraso = 0, tipo = 'sobe', children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  // O número é o único que ganha mola com sobra (damping menor): um passo além de 1 e
  // de volta é o que lê como impacto. Nos textos a sobra viraria balanço, e texto
  // balançando em corpo de cartaz parece erro de render.
  const mola = spring({
    frame: frame - atraso,
    fps,
    config: tipo === 'cresce' ? {damping: 16} : {damping: 200},
  });
  const opacidade = interpolate(frame - atraso, [0, 8], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const transformar =
    tipo === 'cresce'
      ? `scale(${interpolate(mola, [0, 1], [0.86, 1])})`
      : tipo === 'desliza'
        ? `translateX(${interpolate(mola, [0, 1], [-DESLOCAMENTO_LATERAL, 0])}px)`
        : `translateY(${interpolate(mola, [0, 1], [44, 0])}px)`;

  return <div style={{transform: transformar, opacity: opacidade}}>{children}</div>;
};

export const Titulo: React.FC<{children: React.ReactNode; claro?: boolean; corpo?: number}> = ({
  children,
  claro,
  corpo,
}) => (
  <div
    style={{
      fontFamily: FONTE.texto,
      fontSize: corpo ?? 118,
      fontWeight: 700,
      lineHeight: 1.04,
      letterSpacing: '-0.04em',
      color: claro ? CORES.ink : '#fff',
    }}
  >
    {children}
  </div>
);

/** O número em corpo de cartaz.
 *
 * O espaço é renderizado como gap de flex, não como caractere. Numa fonte mono o
 * espaço ocupa a largura de um dígito - em "R$ 20", com 330px de corpo, isso são
 * 160px de vazio no meio do número, e o olho lê "R$" e "20" como duas coisas em vez
 * de um preço. Como gap, o respiro vira um valor que eu escolho (0.18em) em vez de
 * uma herança da métrica da fonte.
 *
 * `lineHeight: 1` fica porque é o que faz a caixa coincidir com a tinta deste
 * número: o cifrão sobe e desce quase o em inteiro. Apertar mais encavalaria o
 * rótulo de cima - quem controla o respiro é a margem dos rótulos. */
const ESPACO_MONO = '0.18em';

export const Numero: React.FC<{children: string; cor?: string; otico?: number}> = ({
  children,
  cor,
  otico = 0,
}) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'baseline',
      justifyContent: 'center',
      gap: ESPACO_MONO,
      fontFamily: FONTE.numero,
      fontSize: 330,
      fontWeight: 700,
      // A vírgula e o espaço da mono ocupam a largura de um dígito; em corpo de cartaz
      // isso abre buraco. O letter-spacing negativo fecha sem trocar de fonte.
      letterSpacing: '-0.06em',
      // O letter-spacing negativo também é aplicado DEPOIS do último algarismo, e o
      // que ele encolhe é a caixa, não a tinta: a caixa fica 0.06em mais estreita que
      // o número, e centralizar a caixa joga o número 10px para a direita do eixo.
      // A margem devolve exatamente essa largura. Medido no quadro: sem ela o centro
      // da tinta cai em x=550; com ela, em 540, que é o meio do vídeo.
      marginRight: '0.06em',
      // Depois disso sobra o que nenhuma conta de CSS alcança: a folga lateral do
      // próprio desenho da letra. O "1" da JetBrains Mono é estreito dentro da célula
      // e o "%" quase encosta na borda, então "1%" nasce 13px à direita do eixo mesmo
      // com a caixa centralizada. `otico` é esse resto, medido no quadro renderizado -
      // a mesma correção que BRAND.md já registra para a assinatura da marca.
      transform: otico ? `translateX(${otico}px)` : undefined,
      lineHeight: 1,
      color: cor ?? CORES.highlight,
    }}
  >
    {children.split(' ').map((parte, i) => (
      <span key={i}>
        {/* A vírgula ocupa uma célula inteira da mono - 198px em corpo 330 - e o
            desenho dela usa um sexto disso. Em "1,6%" o buraco resultante faz o olho
            ler dois números em vez de um. A margem negativa devolve a diferença; o
            letter-spacing sozinho não resolve, porque ele é igual para todo caractere
            e apertar o resto na mesma medida colaria os algarismos. */}
        {parte.split(',').map((trecho, j) => (
          <React.Fragment key={j}>
            {j > 0 ? <span style={{margin: '0 -0.15em'}}>,</span> : null}
            {trecho}
          </React.Fragment>
        ))}
      </span>
    ))}
  </div>
);

export const Apoio: React.FC<{
  children: React.ReactNode;
  claro?: boolean;
  corpo?: number;
  margemTopo?: number;
  margemBase?: number;
}> = ({children, claro, corpo, margemTopo = 18, margemBase = 0}) => (
  <div
    style={{
      fontFamily: FONTE.texto,
      fontSize: corpo ?? 44,
      fontWeight: 600,
      lineHeight: 1.1,
      marginTop: margemTopo,
      marginBottom: margemBase,
      color: claro ? CORES.muted : 'rgba(255,255,255,0.78)',
    }}
  >
    {children}
  </div>
);


/** Como uma palavra ganha ênfase dentro da frase.
 *
 * A cor é sempre a mesma - âmbar é a cor de atenção da marca, e trocá-la a cada cena
 * faria o espectador procurar significado onde não há. O que muda é o MECANISMO: cada
 * um é de uma família diferente, e é isso que impede o vídeo de ficar monótono sem
 * virar feira de efeitos.
 *
 * - `pintura` a cor. Varre a palavra da esquerda para a direita, como caneta passando
 *             por cima. A palavra já estava escrita; o que chega é a tinta.
 * - `grifo`   a forma. Uma barra cresce POR TRÁS da palavra, do centro para fora. A
 *             palavra não muda - o que aparece é o fundo dela. (A letra escurece junto
 *             porque branco sobre âmbar não tem contraste para ler; a mudança de cor
 *             aqui é consequência da barra, não o efeito.)
 * - `chega`   o movimento. A palavra entra depois do resto da frase, vindo da direita.
 *             Serve para "volta", onde o movimento diz a própria palavra.
 * - `cresce`  o tamanho. A palavra aumenta e fica maior que as vizinhas. Serve para
 *             "bem mais", pelo mesmo motivo.
 *
 * O `transform` de `cresce` e `chega` não reflui nada: o span é inline-block e o
 * espaço que ele ocupa na linha continua sendo o do tamanho de repouso. Sem isso a
 * linha inteira se mexeria junto e a ênfase viraria tremor. */
export type TipoDestaque = 'pintura' | 'grifo' | 'chega' | 'cresce';

const DURACAO_PINTURA = 12;
const AVANCO_CHEGA = 120;
const ESCALA_CRESCE = 1.18;

export const Destaque: React.FC<{
  tipo: TipoDestaque;
  inicio: number;
  claro?: boolean;
  children: string;
}> = ({tipo, inicio, claro, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const mola = spring({frame: frame - inicio, fps, config: {damping: 16}});
  const base = claro ? CORES.ink : '#fff';

  if (tipo === 'pintura') {
    // Duas paradas no mesmo ponto fazem a borda dura: é o que dá a leitura de tinta
    // avançando, e não de palavra trocando de cor.
    const avanco =
      interpolate(frame, [inicio, inicio + DURACAO_PINTURA], [0, 100], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      });
    return (
      <span
        style={{
          backgroundImage: `linear-gradient(90deg, ${CORES.highlight} ${avanco}%, ${base} ${avanco}%)`,
          backgroundClip: 'text',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
        }}
      >
        {children}
      </span>
    );
  }

  if (tipo === 'grifo') {
    const aberto = interpolate(mola, [0, 1], [0, 1]);
    // A barra abre por clip-path, e não por scaleX, porque scaleX esmaga o raio dos
    // cantos junto: no meio da animação a pastilha vira lente. Com clip-path a forma
    // é sempre a mesma e o que muda é quanto dela se vê.
    const recorte = (1 - aberto) * 50;
    // A letra escurece enquanto a barra abre. Branco sobre âmbar tem contraste de 2:1
    // e roxo sobre roxo não existe, então nenhuma das duas cores serve durante a
    // travessia - o jeito é atravessar depressa, junto com a barra.
    const tinta = interpolateColors(aberto, [0.3, 0.8], [base, CORES.brandStrong]);
    return (
      <span style={{position: 'relative', display: 'inline-block', isolation: 'isolate'}}>
        <span
          style={{
            position: 'absolute',
            left: '-0.09em',
            right: '-0.07em',
            top: '0.04em',
            bottom: '0.1em',
            background: CORES.highlight,
            clipPath: `inset(0 ${recorte}% 0 ${recorte}% round 18px)`,
            zIndex: 0,
          }}
        />
        <span style={{position: 'relative', zIndex: 1, color: tinta}}>{children}</span>
      </span>
    );
  }

  if (tipo === 'chega') {
    return (
      <span
        style={{
          display: 'inline-block',
          color: CORES.highlight,
          opacity: interpolate(frame - inicio, [0, 8], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          }),
          transform: `translateX(${interpolate(mola, [0, 1], [AVANCO_CHEGA, 0])}px)`,
        }}
      >
        {children}
      </span>
    );
  }

  return (
    <span
      style={{
        display: 'inline-block',
        color: CORES.highlight,
        transform: `scale(${interpolate(mola, [0, 1], [1, ESCALA_CRESCE])})`,
        transformOrigin: 'center',
      }}
    >
      {children}
    </span>
  );
};
