import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Apoio, Destaque, NumeroContando, Palco, Titulo} from '../Base';
import {CENAS, GANCHO_ESPERA} from '../constantes';
import {FechamentoConteudo} from '../Fechamento';
import {CORES, FONTE} from '../marca';
import {
  Barras,
  Check,
  ChuvaDeMoedas,
  LinhaSobe,
  Moeda,
  Onda,
  Raios,
  Sobe,
  Trilho,
  contorno,
} from './elementos';
import {CX, W, bezier, entrada, prog, saida, suave} from './util';

/** As sete cenas da versão animada.
 *
 * Os textos e os números vêm de constantes.ts - as mesmas cenas das outras versões -, e
 * só o que é próprio desta versão (tempo, posição, movimento) está aqui. Corrigir uma
 * frase lá corrige aqui. */

// A faixa segura tem centro em y=940, não 960: o Palco reserva 380px em cima e 420 embaixo.
const CENTRO_Y = 940;

const Fundo: React.FC<{arquivo: string; claro?: boolean; dur: number}> = ({arquivo, claro, dur}) => {
  const frame = useCurrentFrame();
  // Zoom lento e contínuo, como na versão dinâmica: o fundo nunca para.
  const zoom = 1 + 0.06 * prog(frame, 0, dur);
  return (
    <AbsoluteFill
      style={{backgroundColor: claro ? CORES.paper : CORES.brandStrong, overflow: 'hidden'}}
    >
      <Img src={staticFile(arquivo)} style={{width: 1080, height: 1920, transform: `scale(${zoom})`}} />
    </AbsoluteFill>
  );
};

/** Item posicionado pelo centro, em coordenadas absolutas. Nas cenas em que os elementos
 * se cruzam (a palavra que sobe, o número que se abre) o empilhamento em flex refluiria o
 * resto a cada quadro. */
const Faixa: React.FC<{y: number; children: React.ReactNode; style?: React.CSSProperties}> = ({
  y,
  children,
  style,
}) => (
  <div
    style={{
      position: 'absolute',
      left: 0,
      right: 0,
      top: y,
      textAlign: 'center',
      transform: 'translateY(-50%)',
      ...style,
    }}
  >
    {children}
  </div>
);

// ----------------------------------------------------------------------------- 1. gancho

const g = GANCHO_ESPERA;
const CHEGA = 33;
// Centro vertical da palavra em repouso, medido no quadro renderizado.
const PALAVRA_Y = 1143;

/** "Vai comprar na Shopee?" ... "Espera."
 *
 * Quatro palavras sobem das máscaras, uma pausa, e a palavra chega como uma batida: escala
 * grande que assenta com mola, um anel que se expande, raios que contornam a palavra, um
 * clarão âmbar que some rápido e um soco de câmera de 3,5% em tudo. Tudo isso dura 15
 * frames - o que dá impacto é a pausa antes, e o resto só precisa confirmá-lo. */
export const CenaGancho: React.FC<{dur: number}> = ({dur}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const mola = spring({frame: frame - CHEGA, fps, config: {damping: 9, stiffness: 220}});
  const aparece = prog(frame, CHEGA, CHEGA + 3);
  const escurece = interpolate(prog(frame, CHEGA, CHEGA + 8), [0, 1], [1, 0.5]);
  const empurra = -12 * prog(frame, CHEGA, CHEGA + 10, saida);
  const soco = frame >= CHEGA ? 1 + 0.035 * (1 - prog(frame, CHEGA, CHEGA + 9, saida)) : 1;
  const clarao = frame >= CHEGA ? 1 - prog(frame, CHEGA, CHEGA + 11) : 0;

  const linhas = g.pergunta.split('\n');
  return (
    <AbsoluteFill style={{transform: `scale(${soco})`}}>
      <Fundo arquivo="fundo-roxo.png" dur={dur} />
      <div
        style={{
          position: 'absolute',
          left: CX - 560,
          top: PALAVRA_Y - 560,
          width: 1120,
          height: 1120,
          borderRadius: '50%',
          background:
            'radial-gradient(circle, rgba(245,158,11,0.42) 0%, rgba(245,158,11,0) 62%)',
          opacity: clarao,
        }}
      />
      <Onda x={CX} y={PALAVRA_Y} p={prog(frame, CHEGA, CHEGA + 20)} r0={140} r1={640} largura={10} />
      <Raios
        x={CX}
        y={PALAVRA_Y}
        p={prog(frame, CHEGA + 1, CHEGA + 17)}
        n={14}
        base={contorno(400, 150, 26)}
        comp={170}
        largura={11}
        giro={7}
        semOsDeCima
      />
      <Palco>
        <div style={{opacity: escurece, transform: `translateY(${empurra}px)`}}>
          <Titulo corpo={g.corpo}>
            {linhas.map((linha, i) => (
              <div key={i}>
                <LinhaSobe texto={linha} inicio={3 + i * 9} passo={4} />
              </div>
            ))}
          </Titulo>
        </div>
        <div
          style={{
            fontFamily: FONTE.texto,
            fontSize: g.corpoPalavra,
            fontWeight: 700,
            lineHeight: 1.04,
            letterSpacing: '-0.04em',
            color: CORES.highlight,
            marginTop: 8,
            // O letter-spacing negativo também vale depois do ponto final: a caixa fica
            // 0,04em mais estreita que a tinta, e centralizar a caixa empurra a palavra
            // para a direita (medido: 5,5px). A margem devolve essa largura.
            marginRight: '0.04em',
            opacity: aparece,
            transform: `scale(${interpolate(mola, [0, 1], [1.45, 1])})`,
          }}
        >
          {g.palavra}
        </div>
      </Palco>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------ 2. frase

const cond = CENAS[1];
const prom = CENAS[2];
const [, ANTES, MARCADA] = /^(.*?)\s*\*(.+)\*$/.exec(cond.texto)!;
const [PROM_A, PROM_B] = prom.texto.split('\n');
const VOLTA = PROM_B.replace(/\*/g, '');
const CORPO_FRASE = 118;
// "volta" é a palavra da frase e cresce: com o mesmo corpo das outras linhas, a moeda que
// pousa nela era maior que ela.
const CORPO_VOLTA = 150;
const LINHA_FRASE = CORPO_FRASE * 1.04;
const LINHA_VOLTA = CORPO_VOLTA * 1.04;
const ALTURA_FRASE = 3 * LINHA_FRASE + LINHA_VOLTA;
const TOPO_FRASE = CENTRO_Y - ALTURA_FRASE / 2;
// Centro de cada linha com o bloco completo. A quarta linha tem outro corpo, então o
// centro dela não é (k + 0,5) linhas: errar essa conta pousou a moeda em cima de "dinheiro".
const Y_LINHA = [
  TOPO_FRASE + 0.5 * LINHA_FRASE,
  TOPO_FRASE + 1.5 * LINHA_FRASE,
  TOPO_FRASE + 2.5 * LINHA_FRASE,
  TOPO_FRASE + 3 * LINHA_FRASE + LINHA_VOLTA / 2,
];
// Enquanto a segunda metade não chegou, o bloco fica deslocado para baixo para a primeira
// estar centrada: metade da altura das duas últimas linhas.
const DESLOCA_INICIAL = (LINHA_FRASE + LINHA_VOLTA) / 2;

/** "Comprando pela cash-b, parte do dinheiro volta" - as cenas 2 e 3 das outras versões
 * viram uma só. É UMA frase cortada em duas, e mostrá-la em duas cenas separadas por um
 * corte é o que a fazia se partir. Aqui a primeira metade fica na tela e a segunda chega
 * embaixo dela.
 *
 * E a moeda: sai de "cash-b," para fora da tela quando o texto diz "parte", e volta de
 * baixo, em arco, para aterrissar em "volta". O gesto da palavra vira o gesto da imagem. */
const SAI_DE = 30;
const SAI_ATE = 58;
const VOLTA_DE = 62;
const POUSA = 88;

export const CenaFrase: React.FC<{dur: number}> = ({dur}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const chegaMeta = prog(frame, 42, 60, saida);
  const desloca = (1 - chegaMeta) * DESLOCA_INICIAL;

  const YV = Y_LINHA[3];
  const P_SAI: [[number, number], [number, number], [number, number]] = [
    [CX, Y_LINHA[1] + DESLOCA_INICIAL],
    [980, 560],
    [1400, -260],
  ];
  const P_VOLTA: [[number, number], [number, number], [number, number]] = [
    [-330, 1800],
    [230, 1350],
    [CX, YV],
  ];

  const voltando = frame >= VOLTA_DE;
  const bruto = voltando ? prog(frame, VOLTA_DE, POUSA) : prog(frame, SAI_DE, SAI_ATE);
  const nasce = spring({frame: frame - SAI_DE, fps, config: {damping: 12, stiffness: 200}});
  const pouso = prog(frame, POUSA, POUSA + 7, saida);
  const escalaMoeda = voltando
    ? interpolate(suave(bruto), [0, 1], [1.05, 0.8]) * (1 - pouso)
    : interpolate(nasce, [0, 1], [0, 1]);
  const visivel = frame >= SAI_DE && frame < SAI_ATE + 4 ? true : voltando && pouso < 1;

  // A moeda deixa um rastro de três cópias, cada uma mais atrás no caminho e mais fraca:
  // é o que dá velocidade ao movimento, sem borrão.
  const coin = (folga: number, opacidade: number, escala: number, chave: number) => {
    const t = suave(Math.max(0, bruto - folga));
    const pos = bezier(...(voltando ? P_VOLTA : P_SAI), t);
    const giro = t * Math.PI * (voltando ? 3 : 4);
    return (
      <Moeda
        key={chave}
        x={pos[0]}
        y={pos[1]}
        tam={400}
        giro={giro}
        rot={(voltando ? -1 : 1) * 22 * t}
        escala={escalaMoeda * escala}
        opacidade={opacidade}
      />
    );
  };

  const chegaVolta = POUSA;
  const molaVolta = spring({frame: frame - chegaVolta, fps, config: {damping: 9, stiffness: 220}});
  const apareceVolta = prog(frame, chegaVolta, chegaVolta + 3);

  return (
    <AbsoluteFill>
      <Fundo arquivo="fundo-roxo.png" dur={dur} />
      <Raios
        x={CX}
        y={YV}
        p={prog(frame, chegaVolta, chegaVolta + 16)}
        n={14}
        base={contorno(190, 80, 30)}
        comp={130}
        largura={10}
        giro={11}
        semOsDeCima
      />
      <Onda
        x={CX}
        y={YV}
        p={prog(frame, chegaVolta, chegaVolta + 18)}
        r0={120}
        r1={520}
        largura={9}
      />
      <Palco>
        <div style={{transform: `translateY(${desloca}px)`}}>
          <Titulo corpo={CORPO_FRASE}>
            <div>
              <LinhaSobe texto={ANTES} inicio={4} />
            </div>
            <div>
              <Sobe inicio={13}>
                <Destaque tipo="grifo" inicio={24}>
                  {MARCADA}
                </Destaque>
              </Sobe>
            </div>
            <div style={{opacity: chegaMeta}}>
              <LinhaSobe texto={PROM_A} inicio={46} passo={4} />
            </div>
            <div
              style={{
                fontSize: CORPO_VOLTA,
                color: CORES.highlight,
                opacity: apareceVolta,
                transform: `scale(${interpolate(molaVolta, [0, 1], [0.55, 1])})`,
              }}
            >
              {VOLTA}
            </div>
          </Titulo>
        </div>
      </Palco>
      {visivel
        ? [
            coin(0.1, 0.1, 0.93, 3),
            coin(0.07, 0.18, 0.96, 2),
            coin(0.035, 0.3, 0.98, 1),
            coin(0, 1, 1, 0),
          ]
        : null}
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------ 3. mínimo

const min = CENAS[3];
const Y_ACIMA = 724;
const Y_NUMERO = 944;
const Y_ABAIXO = 1164;
const CORPO_ROTULO = 56;
const CORPO_NUMERO = 330;
const TROCA = 46;

/** O número em que só o último algarismo muda: "1%" vira "1,6%" abrindo espaço no meio e
 * rolando o "6" como um hodômetro.
 *
 * Nas outras versões um número saía e outro entrava. Aqui é o mesmo número que cresce,
 * porque é isso que a frase diz: o mínimo *sobe*. O "6" rola de 0 até 6, passando pelos
 * algarismos no caminho, e o olho lê a subida em vez de ver dois valores trocando.
 *
 * O "," e o "6" ficam numa caixa cuja largura abre de 0 a 0,78em. A linha é centralizada,
 * então "1" e "%" se afastam sozinhos e o conjunto se recentraliza sem conta de pixel. */
const NumeroRolando: React.FC<{
  abre: number;
  rola: number;
  otico: number;
  velocidade: number;
}> = ({abre, rola, otico, velocidade}) => {
  const [inteiro, resto] = min.segundo.split(',');
  const alvo = Number(resto.replace(/[^0-9]/g, ''));
  const sufixo = resto.replace(/[0-9]/g, '');
  const valor = alvo * rola;
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        fontFamily: FONTE.numero,
        fontSize: CORPO_NUMERO,
        fontWeight: 700,
        letterSpacing: '-0.06em',
        marginRight: '0.06em',
        lineHeight: 1,
        color: CORES.highlight,
        transform: `translateX(${otico}px)`,
      }}
    >
      <span>{inteiro}</span>
      <span
        style={{
          display: 'flex',
          alignItems: 'center',
          width: `${abre * 0.78}em`,
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        <span style={{margin: '0 -0.15em', flexShrink: 0}}>,</span>
        <span
          style={{
            display: 'block',
            height: '1em',
            width: '0.6em',
            marginRight: '-0.06em',
            overflow: 'hidden',
            flexShrink: 0,
          }}
        >
          <span
            style={{
              display: 'block',
              transform: `translateY(${-valor}em)`,
              // Borrão proporcional à velocidade: o algarismo que passa rápido some em
              // vez de piscar. Em repouso (velocidade zero) o filtro nem é aplicado.
              filter: velocidade > 0.004 ? `blur(${Math.min(10, velocidade * 90)}px)` : undefined,
            }}
          >
            {Array.from({length: alvo + 1}, (_, d) => (
              <span key={d} style={{display: 'block', height: '1em', lineHeight: 1}}>
                {d}
              </span>
            ))}
          </span>
        </span>
      </span>
      <span>{sufixo}</span>
    </div>
  );
};

// A palavra "mínimo" contorna o número pela direita: sair de baixo dele e chegar em cima
// atravessaria o algarismo. 330px é o suficiente para a palavra passar inteira ao lado de
// "1%" (meia largura do número, 180, mais meia largura da palavra, uns 100, mais folga).
const CONTORNO_LATERAL = 330;

export const CenaMinimo: React.FC<{dur: number}> = ({dur}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const nasce = spring({frame: frame - 6, fps, config: {damping: 12, stiffness: 170}});
  const apareceNumero = prog(frame, 6, 10);

  // O resto da frase some por opacidade e só depois fecha a largura - se as duas coisas
  // fossem juntas, a linha centralizada mostraria fragmentos soltos do meio do texto.
  const tinta = 1 - prog(frame, TROCA, TROCA + 6);
  const largura = 1 - prog(frame, TROCA, TROCA + 14);
  const resto = (texto: string) => (
    <span
      style={{
        overflow: 'hidden',
        whiteSpace: 'pre',
        flexShrink: 0,
        opacity: tinta,
        maxWidth: `${largura * texto.length}ch`,
      }}
    >
      {texto}
    </span>
  );

  // Em sequência, e não ao mesmo tempo: primeiro a palavra dá a volta e chega em cima,
  // depois o número se abre. Juntos, o "6" e a palavra disputariam o mesmo lado da tela.
  const orbita = prog(frame, TROCA + 8, TROCA + 34, suave);
  const abre = prog(frame, TROCA + 36, TROCA + 50, saida);
  const rola = prog(frame, TROCA + 38, TROCA + 64, suave);
  const oticoAtual = interpolate(abre, [0, 1], [-13, -14]);
  const entraCondicao = TROCA + 60;

  return (
    <AbsoluteFill>
      <Fundo arquivo="fundo-diagonal.png" dur={dur} />
      <Faixa y={Y_NUMERO} style={{opacity: apareceNumero}}>
        <div style={{transform: `scale(${interpolate(nasce, [0, 1], [0.6, 1])})`}}>
          <NumeroRolando
            abre={abre}
            rola={rola}
            otico={oticoAtual}
            velocidade={Math.abs(rola - prog(frame - 1, TROCA + 38, TROCA + 64, suave))}
          />
        </div>
      </Faixa>

      <Faixa y={Y_ABAIXO}>
        <Apoio corpo={CORPO_ROTULO} margemTopo={0}>
          <span style={{display: 'flex', justifyContent: 'center', alignItems: 'center'}}>
            <Sobe inicio={16}>
              <span style={{opacity: tinta, whiteSpace: 'pre'}}>{'no '}</span>
            </Sobe>
            <span
              style={{
                flexShrink: 0,
                transform: `translate(${CONTORNO_LATERAL * Math.sin(Math.PI * orbita)}px, ${
                  (Y_ACIMA - Y_ABAIXO) * orbita
                }px)`,
              }}
            >
              <Sobe inicio={18}>mínimo</Sobe>
            </span>
            {resto(', em toda compra')}
          </span>
        </Apoio>
      </Faixa>

      <Faixa y={Y_ABAIXO}>
        <Apoio corpo={CORPO_ROTULO} margemTopo={0}>
          {min.condicao.split('\n').map((linha, i) => (
            <div key={i}>
              <LinhaSobe texto={linha} inicio={entraCondicao + i * 6} passo={3} />
            </div>
          ))}
        </Apoio>
      </Faixa>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------- 4. mais

const mais = CENAS[4];

/** "Muitas vezes, bem mais". A palavra-chave chega com mola, deixa dois ecos que crescem
 * e somem (o "mais" reverberando) e, embaixo, cinco barras sobem em degraus.
 *
 * As barras não têm rótulo nem escala: são a imagem de "mais", não uma afirmação de
 * quanto. Um número ali seria uma promessa que o produto não faz para todo pedido. */
export const CenaMais: React.FC<{dur: number}> = ({dur}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const [linhaA, linhaB] = mais.texto.split('\n');
  const chave = linhaB.replace(/\*/g, '');
  const mola = spring({frame: frame - 22, fps, config: {damping: 11, stiffness: 170}});
  const apareceChave = prog(frame, 22, 26);

  return (
    <AbsoluteFill>
      <Fundo arquivo="fundo-roxo.png" dur={dur} />
      <Palco>
        <div style={{transform: 'translateY(-90px)'}}>
          <Titulo corpo={118}>
            <div>
              <LinhaSobe texto={linhaA} inicio={8} />
            </div>
            <div style={{position: 'relative', display: 'inline-block', fontSize: 150}}>
              {[0, 1].map((k) => {
                const p = prog(frame, 24 + k * 6, 24 + k * 6 + 18, saida);
                return (
                  <div
                    key={k}
                    style={{
                      position: 'absolute',
                      inset: 0,
                      color: CORES.highlight,
                      opacity: 0.32 * (1 - p) * (p > 0 ? 1 : 0),
                      transform: `scale(${1 + 0.38 * p})`,
                    }}
                  >
                    {chave}
                  </div>
                );
              })}
              <div
                style={{
                  color: CORES.highlight,
                  opacity: apareceChave,
                  transform: `scale(${interpolate(mola, [0, 1], [0.5, 1])})`,
                }}
              >
                {chave}
              </div>
            </div>
          </Titulo>
        </div>
      </Palco>
      <Barras inicio={30} alturas={[80, 140, 208, 288, 388]} baseY={1470} largura={92} folga={30} />
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------ 5. saque

const saq = CENAS[5];
// O trilho fica abaixo da descida do cifrão: a 1088 ele encostava na haste do "$".
const S_ACIMA = 690;
const S_NUMERO = 896;
const S_TRILHO = 1126;
const S_ABAIXO = 1214;
const TRILHO_LARG = 640;

/** "saque a partir de R$ 20 no Pix", com o número contando e um trilho enchendo junto.
 * Quando o trilho fecha, a marca de verificação se desenha ao lado: "R$ 20" deixa de ser
 * um valor e vira uma meta que se cumpre. */
export const CenaSaque: React.FC<{dur: number}> = ({dur}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enche = prog(frame, 14, 44, saida);
  const molaNumero = spring({frame: frame - 12, fps, config: {damping: 14, stiffness: 170}});

  return (
    <AbsoluteFill>
      <Fundo arquivo="fundo-claro.png" claro dur={dur} />
      <Faixa y={S_ACIMA}>
        <Apoio claro corpo={CORPO_ROTULO} margemTopo={0}>
          <LinhaSobe texto={saq.acima} inicio={8} passo={4} />
        </Apoio>
      </Faixa>
      <Faixa
        y={S_NUMERO}
        style={{
          opacity: prog(frame, 12, 16),
          transform: `translateY(-50%) scale(${interpolate(molaNumero, [0, 1], [0.8, 1])})`,
        }}
      >
        <NumeroContando valor={saq.numero} cor={CORES.success} duracao={30} atraso={14} />
      </Faixa>
      <Faixa y={S_TRILHO} style={{display: 'flex', justifyContent: 'center'}}>
        <Trilho p={enche} largura={TRILHO_LARG} />
      </Faixa>
      <div style={{position: 'absolute', left: CX + TRILHO_LARG / 2 + 20, top: S_TRILHO - 36}}>
        <Check inicio={46} tam={72} />
      </div>
      <Faixa y={S_ABAIXO}>
        <Apoio claro corpo={CORPO_ROTULO} margemTopo={0}>
          <LinhaSobe texto={saq.abaixo} inicio={50} />
        </Apoio>
      </Faixa>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------- 6. sem taxa

const sem = CENAS[6];

/** "Sem mensalidade. Sem taxa." como duas linhas de uma lista: cada uma com a marca de
 * verificação desenhada ao lado e o texto subindo da máscara. Duas linhas entrando uma de
 * cada vez são dois fatos, e não uma frase. */
export const CenaSemTaxa: React.FC<{dur: number}> = ({dur}) => {
  const linhas = sem.texto.split('\n');
  return (
    <AbsoluteFill>
      <Fundo arquivo="fundo-claro.png" claro dur={dur} />
      {/* O bloco é centrado, e as marcas ficam numa coluna. Com cada linha centrada por
          conta própria, a marca da segunda ficava 40px fora do prumo da primeira, e numa
          lista o que entrega o alinhamento é justamente essa coluna. */}
      <Faixa y={CENTRO_Y} style={{display: 'flex', justifyContent: 'center'}}>
        <div style={{display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 46}}>
          {linhas.map((linha, i) => (
            <div key={i} style={{display: 'flex', alignItems: 'center', gap: 30}}>
              <Check inicio={8 + i * 12} tam={88} />
              <Titulo claro corpo={98}>
                <div style={{textAlign: 'left'}}>
                  <LinhaSobe texto={linha} inicio={10 + i * 12} passo={4} />
                </div>
              </Titulo>
            </div>
          ))}
        </div>
      </Faixa>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------- 7. fechamento

const marca = CENAS[7];
const ATRASO_FECHAMENTO = 14;
const INICIO_MOEDAS = 34 + ATRASO_FECHAMENTO + 10;

/** O fechamento, com o halo em movimento.
 *
 * Nas outras versões o halo (arcos concêntricos) é uma imagem parada. Aqui são anéis que
 * ondulam para fora sem parar, e no instante em que "cash-b" cresce e vira o centro, uma
 * onda mais forte parte dele e um punhado de moedas estoura de trás da palavra. É o único
 * momento de comemoração do vídeo, e por isso fica no final. */
export const CenaMarca: React.FC<{dur: number}> = ({dur}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Fundo arquivo="fundo-roxo.png" dur={dur} />
      {[0, 1, 2].map((k) => {
        const p = (((frame + k * 26) % 78) / 78) as number;
        return (
          <Onda
            key={k}
            x={CX}
            y={CENTRO_Y + 20}
            p={p}
            r0={190}
            r1={980}
            largura={5}
            opacidade={0.22}
          />
        );
      })}
      <Onda
        x={CX}
        y={CENTRO_Y + 20}
        p={prog(frame, INICIO_MOEDAS, INICIO_MOEDAS + 22)}
        r0={120}
        r1={780}
        largura={14}
        cor={CORES.highlight}
        opacidade={0.7}
      />
      <ChuvaDeMoedas x={CX} y={CENTRO_Y + 20} inicio={INICIO_MOEDAS} />
      <Palco>
        <FechamentoConteudo
          convite={marca.convite}
          dominio={marca.dominio}
          sufixo={marca.sufixo}
          atraso={ATRASO_FECHAMENTO}
        />
      </Palco>
    </AbsoluteFill>
  );
};
