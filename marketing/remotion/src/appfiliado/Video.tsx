/** Vídeo das funcionalidades do Appfiliado: gancho, uma cena por ferramenta e o fechamento.
 * Texto na tela, sem voz (os creators gravam por cima). O mesmo vídeo sai em três formatos
 * (9:16, 16:9 e 4:5): cada cena põe o texto em cima (vertical) ou à esquerda (horizontal) e
 * escala a demonstração (desenhada em 900 x 1000) pro espaço que sobra. */
import React from 'react';
import {AbsoluteFill, Easing, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, FONTE} from './marca';
import {CenaBot, CenaCarrosseis, CenaConversor, CenaNotas, CenaRadar, CenaResultados, CenaSite} from './cenas';
import {ALTURA_DEMO, Icone, LARGURA_DEMO, Logo, entra, mola} from './ui';

type Ferramenta = {chapeu: string; titulo: string; texto: string; icone: string; duracao: number; Demo: React.FC};

const FERRAMENTAS: Ferramenta[] = [
  {chapeu: 'Bot de WhatsApp', titulo: 'Ofertas no automático nos seus grupos', texto: 'Sempre com o seu link de afiliado.', icone: 'bot', duracao: 300, Demo: CenaBot},
  {chapeu: 'Radar de ofertas', titulo: 'Ache o produto certo em segundos', texto: 'Mais de 30 mil produtos com comissão.', icone: 'radar', duracao: 240, Demo: CenaRadar},
  {chapeu: 'Conversor de links', titulo: 'Troque os links de qualquer texto pelo seu', texto: 'Cole, converta e encaminhe.', icone: 'conversor', duracao: 240, Demo: CenaConversor},
  {chapeu: 'Gerador de carrosséis', titulo: 'Cole um link e receba o carrossel pronto', texto: 'A IA escreve os slides e a legenda.', icone: 'carrosseis', duracao: 270, Demo: CenaCarrosseis},
  {chapeu: 'Meu site', titulo: 'Seu link na bio com vitrine de ofertas', texto: 'seunome.appfiliado.com.br', icone: 'site', duracao: 250, Demo: CenaSite},
  {chapeu: 'Resultados e metas', titulo: 'Veja quanto vendeu e quanto falta pro bônus', texto: 'Por dia, semana ou mês.', icone: 'resultados', duracao: 230, Demo: CenaResultados},
  {chapeu: 'Emissor NFS-e', titulo: 'As notas da comissão extra em poucos cliques', texto: 'Pra afiliado pessoa jurídica.', icone: 'notas', duracao: 240, Demo: CenaNotas},
];
const GANCHO = 96;
const ABERTURA = 72;
const FECHAMENTO = 150;
export const DURACAO_APPFILIADO = GANCHO + ABERTURA + FERRAMENTAS.reduce((a, f) => a + f.duracao, 0) + FECHAMENTO;

const useFormato = () => {
  const {width, height} = useVideoConfig();
  if (width > height) return 'horizontal' as const;
  return height / width > 1.5 ? ('vertical' as const) : ('retrato' as const);
};

const Fundo: React.FC<{escuro?: boolean}> = ({escuro}) => (
  <AbsoluteFill style={{zIndex: -1, background: escuro ? `radial-gradient(120% 90% at 88% 6%, ${C.verde2} 0%, ${C.verde} 46%, ${C.verde3} 100%)` : C.creme}} />
);

/** Entrada e saída suaves de cada cena (sobe e aparece / some). */
const Transicao: React.FC<{duracao: number; children: React.ReactNode}> = ({duracao, children}) => {
  const f = useCurrentFrame();
  const dentro = interpolate(f, [0, 12], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const fora = interpolate(f, [duracao - 10, duracao], [1, 0], {extrapolateLeft: 'clamp', easing: Easing.in(Easing.cubic)});
  return <AbsoluteFill style={{opacity: Math.min(dentro, fora), transform: `translateY(${(1 - dentro) * 50}px) scale(${0.98 + 0.02 * fora})`}}>{children}</AbsoluteFill>;
};

const CenaDeFerramenta: React.FC<{ferramenta: Ferramenta; numero: number}> = ({ferramenta, numero}) => {
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const formato = useFormato();
  const {Demo} = ferramenta;
  // área do texto e da demonstração em cada formato
  const horizontal = formato === 'horizontal';
  const margem = horizontal ? 90 : 70;
  const areaTexto = horizontal ? {left: margem, top: 0, width: width * 0.36, height} : {left: margem, top: formato === 'vertical' ? 150 : 70, width: width - 2 * margem, height: formato === 'vertical' ? 420 : 300};
  const areaDemo = horizontal
    ? {left: width * 0.36 + margem * 1.4, top: 70, width: width - width * 0.36 - margem * 2.4, height: height - 140}
    : {left: margem, top: areaTexto.top + areaTexto.height + 20, width: width - 2 * margem, height: height - (areaTexto.top + areaTexto.height + 20) - (formato === 'vertical' ? 230 : 60)};
  const escala = Math.min(areaDemo.width / LARGURA_DEMO, areaDemo.height / ALTURA_DEMO);
  const titulo = horizontal ? 74 : formato === 'vertical' ? 76 : 60;
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.tinta}}>
      <Fundo />
      <div style={{position: 'absolute', ...areaTexto, display: 'flex', flexDirection: 'column', justifyContent: horizontal ? 'center' : 'flex-start'}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 18, opacity: entra(f, 4)}}>
          <div style={{width: 76, height: 76, borderRadius: 22, background: C.verde, display: 'grid', placeItems: 'center'}}><Icone nome={ferramenta.icone} tamanho={44} /></div>
          <div style={{fontSize: 30, fontWeight: 800, letterSpacing: '.12em', textTransform: 'uppercase', color: '#8A6A00'}}>{ferramenta.chapeu}</div>
          <div style={{marginLeft: 'auto', fontSize: 26, fontWeight: 800, opacity: 0.35}}>{numero}/{FERRAMENTAS.length}</div>
        </div>
        <div style={{fontSize: titulo, fontWeight: 800, letterSpacing: '-.03em', lineHeight: 1.04, marginTop: 24, opacity: entra(f, 8), transform: `translateY(${(1 - entra(f, 8)) * 30}px)`}}>
          {ferramenta.titulo}
        </div>
        <div style={{fontSize: horizontal ? 36 : 34, color: C.cinza, marginTop: 18, opacity: entra(f, 16)}}>{ferramenta.texto}</div>
      </div>
      <div style={{position: 'absolute', left: areaDemo.left + (areaDemo.width - LARGURA_DEMO * escala) / 2, top: areaDemo.top,
        width: LARGURA_DEMO, height: ALTURA_DEMO, transform: `scale(${escala})`, transformOrigin: 'top left'}}>
        <Demo />
      </div>
    </AbsoluteFill>
  );
};

const Gancho: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const formato = useFormato();
  const grande = formato === 'horizontal' ? 120 : formato === 'vertical' ? 112 : 96;
  const risco = interpolate(f, [44, 58], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme, justifyContent: 'center', padding: '0 90px'}}>
      <Fundo escuro />
      <div style={{position: 'relative', fontSize: grande, fontWeight: 800, letterSpacing: '-.035em', lineHeight: 1.02}}>
        <div style={{transform: `translateY(${(1 - mola(f, 0, fps)) * 60}px)`, opacity: mola(f, 0, fps)}}>Ainda posta oferta</div>
        <div style={{transform: `translateY(${(1 - mola(f, 8, fps)) * 60}px)`, opacity: mola(f, 8, fps)}}>da Shopee</div>
        <div style={{transform: `translateY(${(1 - mola(f, 16, fps)) * 60}px)`, opacity: mola(f, 16, fps), color: C.amarelo, position: 'relative', display: 'inline-block'}}>
          na mão?
          <div style={{position: 'absolute', left: 0, top: '55%', height: 14, width: `${risco}%`, background: C.creme, borderRadius: 8}} />
        </div>
        <div style={{fontSize: grande * 0.42, fontWeight: 500, color: C.suave, marginTop: 34, opacity: entra(f, 60)}}>Deixa o Appfiliado fazer por você.</div>
      </div>
    </AbsoluteFill>
  );
};

const Abertura: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = mola(f, 0, fps, 11);
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme, alignItems: 'center', justifyContent: 'center', textAlign: 'center'}}>
      <Fundo escuro />
      <div style={{transform: `scale(${s})`}}><Logo tamanho={200} /></div>
      <div style={{fontSize: 96, fontWeight: 800, letterSpacing: '-.03em', marginTop: 34, opacity: entra(f, 10)}}>Appfiliado</div>
      <div style={{fontSize: 40, color: C.suave, marginTop: 10, opacity: entra(f, 20)}}>O painel do afiliado da Shopee</div>
    </AbsoluteFill>
  );
};

const Fechamento: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const formato = useFormato();
  const icones = ['bot', 'radar', 'conversor', 'carrosseis', 'site', 'resultados', 'notas'];
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme, alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: 80}}>
      <Fundo escuro />
      <div style={{display: 'flex', gap: 18, flexWrap: 'wrap', justifyContent: 'center', maxWidth: 900}}>
        {icones.map((i, k) => {
          const s = mola(f, k * 4, fps);
          return <div key={i} style={{width: 96, height: 96, borderRadius: 26, background: 'rgba(246,243,234,.10)', border: '3px solid rgba(246,243,234,.16)',
            display: 'grid', placeItems: 'center', transform: `scale(${s})`}}><Icone nome={i} tamanho={52} /></div>;
        })}
      </div>
      <div style={{fontSize: formato === 'retrato' ? 78 : 92, fontWeight: 800, letterSpacing: '-.03em', lineHeight: 1.05, marginTop: 50, opacity: entra(f, 24)}}>
        Tudo isso <span style={{color: C.amarelo, whiteSpace: 'nowrap'}}>num painel só.</span>
      </div>
      <div style={{fontSize: 42, color: C.suave, marginTop: 22, opacity: entra(f, 36)}}>Planos a partir de R$ 19,90/mês</div>
      <div style={{display: 'flex', alignItems: 'center', gap: 20, marginTop: 50, opacity: entra(f, 48), transform: `scale(${0.9 + 0.1 * entra(f, 48)})`}}>
        <Logo tamanho={84} />
        <div style={{fontSize: 52, fontWeight: 800}}>appfiliado.com.br</div>
      </div>
    </AbsoluteFill>
  );
};

export const VideoAppfiliado: React.FC = () => {
  let inicio = 0;
  const bloco = (duracao: number, conteudo: React.ReactNode, chave: string) => {
    const el = (
      <Sequence key={chave} from={inicio} durationInFrames={duracao}>
        <Transicao duracao={duracao}>{conteudo}</Transicao>
      </Sequence>
    );
    inicio += duracao;
    return el;
  };
  return (
    <AbsoluteFill style={{background: C.verde}}>
      {bloco(GANCHO, <Gancho />, 'gancho')}
      {bloco(ABERTURA, <Abertura />, 'abertura')}
      {FERRAMENTAS.map((ferramenta, i) => bloco(ferramenta.duracao, <CenaDeFerramenta ferramenta={ferramenta} numero={i + 1} />, ferramenta.icone))}
      {bloco(FECHAMENTO, <Fechamento />, 'fechamento')}
    </AbsoluteFill>
  );
};
