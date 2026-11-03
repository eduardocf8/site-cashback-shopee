/** Bot de WhatsApp: "Grupos cheios". O que acontece quando os grupos lotam: o link de entrada (um link só
 * no anúncio, que manda cada pessoa pro grupo com vaga), o painel de membros (quem está lotando) e a
 * criação automática do próximo grupo (Premium). Encerramento com o preço e as ferramentas inclusas. */
import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, FONTE} from '../appfiliado/marca';
import {Cabecalho, CelularNaCena, Cortina, DURACAO_FINAL, Final, Fundo, Legendas, POS, Toque, mola, vai} from './comum';
import {Barra, ConviteGrupo, CriandoGrupo, FotoGrupo, GruposDoLink, Membros, PaginaEntrada, Painel, Rotulo, Selo, VERMELHO, corDaLotacao} from './botTelas';
import {CTA, INCLUSOS} from './textos';

/** Monta as cenas em sequência, com a cortina cobrindo cada troca (inclusive a do encerramento). */
export const Montagem: React.FC<{cenas: {duracao: number; cena: React.ReactNode; cortina?: string}[]}> = ({cenas}) => {
  let inicio = 0;
  const blocos: React.ReactNode[] = [];
  cenas.forEach((c, i) => {
    blocos.push(<Sequence key={`c${i}`} from={inicio} durationInFrames={c.duracao}>{c.cena}</Sequence>);
    if (i > 0) blocos.push(<Sequence key={`t${i}`} from={inicio - 9} durationInFrames={18}><Cortina cor={c.cortina} /></Sequence>);
    inicio += c.duracao;
  });
  return <AbsoluteFill style={{background: C.verde}}>{blocos}</AbsoluteFill>;
};

export const duracaoDe = (cenas: {duracao: number}[]) => cenas.reduce((a, c) => a + c.duracao, 0);

// --- 1. o grupo lotou -------------------------------------------------------------------------------

const Lotou: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const membros = Math.round(vai(f, 4, 50, 978, 1024));
  const p = (membros * 100) / 1024;
  const cheio = mola(f, 50, fps, 11);
  return (
    <AbsoluteFill style={{fontFamily: FONTE}}>
      <Fundo tom="escuro" />
      <Cabecalho chapeu="Bot de WhatsApp" titulo={'Grupo *lotou.*\nE quem chega agora?'} inicio={-12} escuro tamanho={86} />
      <Painel top={850} inicio={-14}>
        <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
          <FotoGrupo tamanho={92} />
          <div style={{flex: 1, fontSize: 36, fontWeight: 800}}>Achadinhos da Bia #1</div>
          <div style={{transform: `scale(${f >= 50 ? 0.6 + 0.4 * cheio : 0})`}}><Selo texto="Cheio" tom="vermelho" tamanho={28} /></div>
        </div>
        <div style={{display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 26}}>
          <span style={{fontSize: 96, fontWeight: 800, letterSpacing: '-.04em', color: f >= 50 ? VERMELHO : C.tinta, fontVariantNumeric: 'tabular-nums'}}>
            {membros.toLocaleString('pt-BR')}
          </span>
          <span style={{fontSize: 34, color: C.cinza, fontWeight: 800}}>de 1.024 membros</span>
        </div>
        <div style={{marginTop: 18}}><Barra porcento={p} cor={corDaLotacao(p)} altura={22} /></div>
      </Painel>
      <Legendas y={1260} falas={[{f: 56, texto: 'O WhatsApp aceita até 1.024 pessoas', icone: '🚫'}]} />
    </AbsoluteFill>
  );
};

// --- 2. o link de entrada -----------------------------------------------------------------------------

const LinkDeEntrada: React.FC = () => {
  const f = useCurrentFrame();
  const convite = vai(f, 84, 102);
  const trocaTela = vai(f, 148, 166);
  return (
    <AbsoluteFill style={{fontFamily: FONTE}}>
      <Fundo tom="creme" />
      <Cabecalho chapeu="Link de entrada" titulo={'Um link só\npra *todos os grupos.*'} inicio={-4} tamanho={86} />
      <div style={{position: 'absolute', inset: 0, opacity: 1 - trocaTela, transform: `translateY(${-trocaTela * 80}px) scale(${1 - trocaTela * 0.05})`}}>
        <CelularNaCena inicio={2} hora="20:14">
          <PaginaEntrada toque={76} />
          <Toque x={280} y={708} f={76} />
          {convite > 0 && <ConviteGrupo nome="Achadinhos da Bia #2" membros="987 participantes" t={convite} />}
        </CelularNaCena>
      </div>
      <Painel centro inicio={156}>
        <Rotulo>Grupos do link · Grupo VIP de Achadinhos</Rotulo>
        <div style={{marginTop: 22}}>
          <GruposDoLink inicio={176} duracao={60} grupos={[
            {nome: 'Achadinhos da Bia #1', de: 1000, ate: 1000},
            {nome: 'Achadinhos da Bia #2', de: 976, ate: 1000},
            {nome: 'Achadinhos da Bia #3', de: 612, ate: 641},
          ]} />
        </div>
        <div style={{marginTop: 22, fontSize: 23, color: C.cinza}}>Pixel do Meta ligado · 754 visitas e 442 cliques em 7 dias</div>
      </Painel>
      <Legendas falas={[
        {f: 18, texto: 'Vai no anúncio, na bio ou no story', icone: '📣'},
        {f: 96, texto: 'Manda pro grupo que tem vaga', icone: '👉', tom: 'amarelo'},
        {f: 172, texto: 'Encheu? O link passa pro próximo', icone: '🔁'},
        {f: 246, texto: 'O link do anúncio nunca muda', icone: '🔗', tom: 'amarelo'},
      ]} />
    </AbsoluteFill>
  );
};

// --- 3. os membros e a lotação ------------------------------------------------------------------------

const Lotacao: React.FC = () => (
  <AbsoluteFill style={{fontFamily: FONTE}}>
    <Fundo tom="escuro" />
    <Cabecalho chapeu="Membros dos grupos" titulo={'Veja quais grupos\n*estão lotando.*'} inicio={-4} escuro tamanho={86} />
    <Painel centro inicio={2}>
      <Membros inicio={12} aviso={104} grupos={[
        {nome: 'Achadinhos da Bia #1', de: 1006, ate: 1019, dia: '+13'},
        {nome: 'Achadinhos da Bia #2', de: 958, ate: 986, dia: '+28'},
        {nome: 'Casa e Cozinha', de: 788, ate: 812, dia: '+24'},
        {nome: 'Achadinhos da Bia #3', de: 604, ate: 640, dia: '+36'},
      ]} />
    </Painel>
    <Legendas falas={[
      {f: 20, texto: 'Entradas e saídas de cada grupo', icone: '📈'},
      {f: 108, texto: 'Aviso quando passa de 95%', icone: '⚠️', tom: 'amarelo'},
      {f: 168, texto: 'Até 500 grupos acompanhados', icone: '👥'},
    ]} />
  </AbsoluteFill>
);

// --- 4. o próximo grupo, sozinho ---------------------------------------------------------------------

const ProximoGrupo: React.FC = () => (
  <AbsoluteFill style={{fontFamily: FONTE}}>
    <Fundo tom="amarelo" />
    <Cabecalho chapeu="Criação automática · Premium" titulo={'Lotou? Ele cria\n*o próximo sozinho.*'} inicio={-4} amarelo tamanho={86} />
    <Painel centro inicio={2}>
      <CriandoGrupo inicio={40} intervalo={20} />
    </Painel>
    <Legendas falas={[
      {f: 18, texto: 'Quando todos os grupos estão lotando', icone: '🤖'},
      {f: 166, texto: 'E você recebe um e-mail avisando', icone: '✉️', tom: 'escuro'},
      {f: 214, texto: 'Até 5 grupos novos por dia', icone: '✨'},
      {f: 262, texto: 'No Standard: crie com um toque', icone: '👆', tom: 'escuro'},
    ]} />
  </AbsoluteFill>
);

const CENAS_GRUPOS = [
  {duracao: 96, cena: <Lotou />},
  {duracao: 300, cena: <LinkDeEntrada />},
  {duracao: 228, cena: <Lotacao />, cortina: C.verde},
  {duracao: 312, cena: <ProximoGrupo />},
  {duracao: DURACAO_FINAL.comInclusos, cena: <Final frase={'Seus grupos crescem\n*sem dar mais trabalho.*'} linha={CTA.bot} inclusos={INCLUSOS} />, cortina: C.verde},
];

export const DURACAO_BOT_GRUPOS = duracaoDe(CENAS_GRUPOS);
export const BotGruposCheios: React.FC = () => <Montagem cenas={CENAS_GRUPOS} />;
