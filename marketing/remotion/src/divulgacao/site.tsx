/** Tema 2: Meu site (o link na bio do afiliado Shopee). Duas versões:
 * - SiteMonteOSeu: o site se montando no celular na ordem real da página (perfil, botões, redes,
 *   conversor e vitrine), cada parte com o seu balão, e depois os cliques contados.
 * - SiteDoStoryAoClique: o caminho do seguidor, do story ao site, e as duas formas de comprar pelo
 *   link do afiliado: uma oferta da vitrine ou um link colado no conversor.
 * A página segue meusite/templates/meusite/publico.html (ordem, textos padrão e cores do tema
 * colorido: o fundo é 78% da cor + 22% de quase preto, meusite/cores.py). Tudo o que aparece existe
 * no Meu site (landing/recursos.py, função site()). */
import React from 'react';
import {AbsoluteFill, Img, Sequence, interpolateColors, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, FONTE} from '../appfiliado/marca';
import {Digitando, produto} from '../appfiliado/ui';
import {Cabecalho, CelularNaCena, Conta, Cortina, DURACAO_FINAL, Final, Fundo, Legendas, POS, TELA, Toque, mola, s, vai} from './comum';
import {CTA, ENDERECO, INCLUSOS, OFERTAS} from './textos';

const ROSA = '#D6336C';
const AZUL = '#2F6FDE';
const TINTA = '#1C2B23';

/** Fundo da página no estilo colorido (meusite/cores.py: 78% da cor + 22% de #1A1A1A). */
const fundoDe = (cor: string) => {
  const c = [1, 3, 5].map((i) => parseInt(cor.slice(i, i + 2), 16));
  return '#' + c.map((x) => Math.round(x * 0.78 + 26 * 0.22).toString(16).padStart(2, '0')).join('');
};

const BOTOES = ['💬 Grupo VIP de ofertas', '📣 Canal de ofertas', '🎟️ Cupons do dia'];
const VITRINE = [OFERTAS[0], OFERTAS[1], OFERTAS[3], OFERTAS[4]];
const CATEGORIAS = ['Todas', 'Eletrônicos', 'Casa', 'Esporte'];
const LINK_COLADO = 'shopee.com.br/Air-Fryer-4L-i.3829.17';
const desconto = (de: string, por: string) => {
  const n = (v: string) => Number(v.replace(/[^\d,]/g, '').replace(',', '.'));
  return `-${Math.round((1 - n(por) / n(de)) * 100)}%`;
};

// ícones de rede genéricos (sem logo de marca), em traço branco como no site
const ICONES_REDE = [
  'M7 3h10a4 4 0 0 1 4 4v10a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V7a4 4 0 0 1 4-4zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM17.5 6.5h.01',
  'M9 18V5l11-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM20 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z',
  'M3 7a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3zM10 9l5 3-5 3z',
  'M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z',
];

// --- a página do Meu site, desenhada na tela do celular (560 x 1120) -------------------------------

type Parte = 'perfil' | 'botoes' | 'redes' | 'conversor' | 'vitrine' | '';

type Estado = {
  endereco: string; foto: number; nome: React.ReactNode; frase: number; botoes: number[]; redes: number; conversor: number;
  colado?: React.ReactNode; apertado?: boolean; vitrine: number; rodape: number;
};

const CHEIO: Estado = {endereco: ENDERECO, foto: 1, nome: 'Achadinhos da Bia', frase: 1, botoes: [1, 1, 1], redes: 1, conversor: 1, vitrine: 1, rodape: 1};

/** Uma parte da página, com o contorno amarelo quando é a parte da vez. */
const Parte: React.FC<{destaque: number; children: React.ReactNode; style?: React.CSSProperties}> = ({destaque, children, style}) => (
  <div style={{position: 'relative', ...style}}>
    {children}
    <div style={{position: 'absolute', inset: -10, borderRadius: 30, border: `4px solid ${C.amarelo}`, opacity: destaque, boxShadow: '0 0 0 6px rgba(242,194,48,.18)',
      pointerEvents: 'none'}} />
  </div>
);

const PaginaSite: React.FC<{e: Estado; cor: string; fundo: string; rolagem?: number; ativo?: Parte; destaque?: number; toqueProduto?: number}> = ({
  e, cor, fundo, rolagem = 0, ativo = '', destaque = 0, toqueProduto,
}) => {
  const f = useCurrentFrame();
  const sobe = (t: number) => ({opacity: Math.min(1, t * 1.3), transform: `translateY(${(1 - t) * 26}px) scale(${0.94 + 0.06 * t})`});
  const d = (p: Parte) => (ativo === p ? destaque : 0);
  return (
    <div style={{position: 'absolute', inset: 0, background: fundo, color: C.branco, fontFamily: FONTE, overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: 26, right: 26, top: 138, transform: `translateY(${-rolagem}px)`}}>
        {/* perfil */}
        <Parte destaque={d('perfil')} style={{textAlign: 'center', paddingBottom: 26}}>
          <div style={{width: 136, height: 136, margin: '0 auto', borderRadius: '50%', overflow: 'hidden', ...sobe(e.foto)}}>
            <Img src={produto('bolsa')} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
          </div>
          <div style={{fontSize: 36, fontWeight: 800, marginTop: 12, minHeight: 44}}>{e.nome}</div>
          <div style={{fontSize: 20, marginTop: 6, color: 'rgba(255,255,255,.82)', opacity: e.frase}}>As melhores ofertas da Shopee todo dia ✨</div>
        </Parte>
        {/* botões de link */}
        <Parte destaque={d('botoes')} style={{display: 'grid', gap: 12}}>
          {BOTOES.map((b, i) => (
            <div key={b} style={{minHeight: 68, display: 'grid', placeItems: 'center', borderRadius: 999, fontSize: 23, color: TINTA, ...sobe(e.botoes[i] ?? 0),
              background: i === 0 ? C.branco : 'rgba(255,255,255,.84)', fontWeight: i === 0 ? 800 : 500, boxShadow: i === 0 ? '0 6px 18px rgba(0,0,0,.18)' : 'none'}}>{b}</div>
          ))}
        </Parte>
        {/* redes */}
        <Parte destaque={d('redes')} style={{display: 'flex', justifyContent: 'center', gap: 34, margin: '24px 0 6px', padding: '6px 0'}}>
          {ICONES_REDE.map((icone, i) => (
            <svg key={i} viewBox="0 0 24 24" width={40} height={40} fill="none" stroke={C.branco} strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round"
              style={sobe(Math.min(1, Math.max(0, e.redes * 4 - i)))}>
              <path d={icone} />
            </svg>
          ))}
        </Parte>
        {/* conversor */}
        <Parte destaque={d('conversor')} style={{margin: '26px 0 20px'}}>
          <div style={{background: C.branco, color: TINTA, borderRadius: 28, padding: 22, textAlign: 'center', ...sobe(e.conversor)}}>
            <div style={{fontSize: 28, fontWeight: 800}}>Achou algo na Shopee?</div>
            <div style={{fontSize: 18, lineHeight: 1.4, color: '#6B6B6B', marginTop: 6}}>Cole o link do produto e compre pelo meu link. Você não paga nada a mais e me ajuda a continuar postando ofertas.</div>
            <div style={{height: 64, marginTop: 14, borderRadius: 16, border: `2px solid ${e.colado ? cor : '#EEE6DD'}`, background: e.colado ? C.branco : '#FCFAF7', display: 'grid',
              placeItems: 'center', fontSize: 20, color: e.colado ? TINTA : '#9A9A9A', whiteSpace: 'nowrap', overflow: 'hidden', padding: '0 12px'}}>
              {e.colado ?? 'Cole aqui o link da Shopee'}
            </div>
            <div style={{height: 64, marginTop: 10, borderRadius: 16, background: e.apertado ? cor : TINTA, color: C.branco, display: 'grid', placeItems: 'center', fontSize: 22,
              fontWeight: 800, transform: `scale(${e.apertado ? 0.97 : 1})`}}>Ir pra Shopee com o meu link</div>
          </div>
        </Parte>
        {/* vitrine */}
        <Parte destaque={d('vitrine')} style={{paddingTop: 6, opacity: Math.min(1, e.vitrine * 3)}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
            <div style={{fontSize: 26, fontWeight: 800}}>Ofertas de hoje</div>
            <div style={{fontSize: 15, color: 'rgba(255,255,255,.82)'}}>atualizado às 14:30</div>
          </div>
          <div style={{display: 'flex', gap: 8, marginTop: 12}}>
            {CATEGORIAS.map((c, i) => (
              <div key={c} style={{fontSize: 16, fontWeight: 800, padding: '9px 16px', borderRadius: 999, whiteSpace: 'nowrap',
                background: i === 0 ? C.branco : 'rgba(255,255,255,.16)', color: i === 0 ? TINTA : C.branco}}>{c}</div>
            ))}
          </div>
          <div style={{display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 14, marginTop: 14}}>
            {VITRINE.map((o, i) => {
              const t = Math.min(1, Math.max(0, e.vitrine * 5 - i));
              const tocado = i === 0 && toqueProduto !== undefined && f >= toqueProduto && f < toqueProduto + 14;
              return (
                <div key={o.foto} style={{position: 'relative', background: C.branco, color: TINTA, borderRadius: 20, overflow: 'hidden', ...sobe(t),
                  outline: tocado ? `5px solid ${C.amarelo}` : 'none'}}>
                  <Img src={produto(o.foto)} style={{width: '100%', aspectRatio: '1', objectFit: 'cover', display: 'block'}} />
                  <div style={{padding: '10px 12px 12px'}}>
                    <div style={{fontSize: 16, lineHeight: 1.3, height: 42, overflow: 'hidden'}}>{o.nome}</div>
                    <div style={{fontSize: 14, color: '#6B6B6B', textDecoration: 'line-through', marginTop: 4}}>{o.de}</div>
                    <div style={{fontSize: 22, fontWeight: 800, color: cor}}>{o.por}
                      <span style={{fontSize: 13, fontWeight: 800, background: `${cor}24`, padding: '2px 7px', borderRadius: 7, marginLeft: 6, verticalAlign: 3}}>{desconto(o.de, o.por)}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{marginTop: 14, borderRadius: 999, padding: 15, textAlign: 'center', fontSize: 18, fontWeight: 800, background: 'rgba(255,255,255,.16)'}}>Ver mais ofertas</div>
        </Parte>
        {/* rodapé */}
        <div style={{textAlign: 'center', fontSize: 15, lineHeight: 1.6, color: 'rgba(255,255,255,.82)', marginTop: 30, opacity: e.rodape}}>
          Links de afiliado da Shopee: quem divulga ganha uma comissão, sem custo extra para você.<br />
          <b style={{color: C.branco}}>Feito com Appfiliado</b>
        </div>
      </div>
      {/* barra do navegador por cima do que rola */}
      <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 124, background: fundo}} />
      <div style={{position: 'absolute', top: 62, left: 18, right: 18, height: 50, borderRadius: 25, background: 'rgba(255,255,255,.95)', display: 'flex', alignItems: 'center',
        gap: 8, padding: '0 16px', fontSize: 19, fontWeight: 800, color: TINTA, whiteSpace: 'nowrap', overflow: 'hidden', letterSpacing: '-.01em'}}>
        <span style={{fontSize: 15}}>🔒</span>{e.endereco}
      </div>
    </div>
  );
};

/** Botão "Ir pra Shopee com o meu link" na tela, com a página rolada em ROLAGEM.conversor. */
const ROLAGEM = {conversor: 210, vitrine: 906};
const BOTAO_CONVERSOR = {x: 280, y: 748};
const PRODUTO_1 = {x: 150, y: 420};

/** Tela de saída: o produto e a ida pra Shopee pelo link de afiliado (sem nada visual da Shopee). */
const TelaIndo: React.FC<{inicio: number; oferta: (typeof OFERTAS)[number]; subId: string}> = ({inicio, oferta, subId}) => {
  const f = useCurrentFrame();
  return (
    <div style={{position: 'absolute', inset: 0, background: C.creme, color: C.tinta, padding: '120px 34px 0', fontFamily: FONTE}}>
      <div style={{background: C.branco, borderRadius: 26, padding: 18, boxShadow: '0 12px 30px rgba(23,48,31,.1)'}}>
        <Img src={produto(oferta.foto)} style={{width: '100%', height: 300, objectFit: 'cover', borderRadius: 18, display: 'block'}} />
        <div style={{fontSize: 22, fontWeight: 800, marginTop: 14}}>{oferta.nome}</div>
        <div style={{marginTop: 6}}><span style={{color: C.cinza, textDecoration: 'line-through', fontSize: 20}}>{oferta.de}</span> <span style={{fontSize: 32, fontWeight: 800, color: C.ok}}>{oferta.por}</span></div>
      </div>
      <div style={{marginTop: 30, fontSize: 24, fontWeight: 800, textAlign: 'center'}}>Indo pra Shopee pelo seu link</div>
      <div style={{height: 12, borderRadius: 999, background: C.borda, marginTop: 16, overflow: 'hidden'}}>
        <div style={{height: '100%', width: `${vai(f, inicio, inicio + 44, 0, 100)}%`, background: C.verde, borderRadius: 999}} />
      </div>
      <div style={{marginTop: 26, display: 'grid', gap: 12, justifyItems: 'center', opacity: vai(f, inicio + 18, inicio + 30)}}>
        <div style={{background: C.verde, color: C.creme, borderRadius: 999, padding: '12px 22px', fontSize: 20, fontWeight: 800}}>👉 {oferta.link}</div>
        <div style={{background: C.amarelo, color: C.verde, borderRadius: 999, padding: '10px 20px', fontSize: 18, fontWeight: 800}}>Seu link de afiliado · Sub ID: {subId}</div>
      </div>
    </div>
  );
};

// --- Site-MonteOSeu ---------------------------------------------------------------------------------

// Quando cada parte da página entra (frames da cena da montagem), na ordem real do site.
const M = {endereco: 16, perfil: 54, botoes: 102, redes: 142, conversor: 178, colar: 214, aperta: 252, vitrine: 272, cores: 340, topo: 384, fim: 432};
const MONTE = {montagem: M.fim, numeros: s(5), final: DURACAO_FINAL.comInclusos};
export const DURACAO_SITE_MONTE = MONTE.montagem + MONTE.numeros + MONTE.final;

const Montagem: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const n = Math.round(vai(f, M.endereco + 2, M.endereco + 34, 0, ENDERECO.length));
  const cor = interpolateColors(f, [M.cores + 14, M.cores + 32], [ROSA, AZUL]);
  const fundo = interpolateColors(f, [M.cores + 14, M.cores + 32], [fundoDe(ROSA), fundoDe(AZUL)]);
  const e: Estado = {
    endereco: f < M.endereco + 2 ? '' : ENDERECO.slice(0, n),
    foto: mola(f, M.perfil, fps, 12),
    nome: f < M.perfil + 10 ? '' : <Digitando texto="Achadinhos da Bia" inicio={M.perfil + 10} fim={M.perfil + 30} cursor={false} />,
    frase: vai(f, M.perfil + 30, M.perfil + 42),
    botoes: [0, 1, 2].map((i) => mola(f, M.botoes + i * 10, fps, 13)),
    redes: vai(f, M.redes, M.redes + 22),
    conversor: mola(f, M.conversor + 6, fps, 13),
    colado: f < M.colar + 6 ? undefined : <Digitando texto={LINK_COLADO} inicio={M.colar + 6} fim={M.colar + 30} cursor={false} />,
    apertado: f >= M.aperta && f < M.aperta + 8,
    // a vitrine aparece antes de a página rolar até ela (senão a rolagem passa por um espaço vazio)
    vitrine: vai(f, M.vitrine - 8, M.vitrine + 12),
    rodape: vai(f, M.vitrine + 4, M.vitrine + 20),
  };
  const rolagem = vai(f, M.conversor, M.conversor + 22, 0, ROLAGEM.conversor) + vai(f, M.vitrine, M.vitrine + 26, 0, ROLAGEM.vitrine - ROLAGEM.conversor)
    - vai(f, M.topo, M.topo + 30, 0, ROLAGEM.vitrine);
  const partes: [Parte, number, number][] = [['perfil', M.perfil, M.botoes], ['botoes', M.botoes, M.redes], ['redes', M.redes, M.conversor],
    ['conversor', M.conversor + 6, M.vitrine], ['vitrine', M.vitrine + 12, M.cores]];
  const agora = partes.find(([, de, ate]) => f >= de && f < ate);
  const destaque = agora ? Math.min(vai(f, agora[1], agora[1] + 8), vai(f, agora[2] - 8, agora[2], 1, 0)) : 0;
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.tinta}}>
      <Fundo tom="creme" />
      <Cabecalho chapeu="Meu site" titulo={'Seu link na bio\n*pronto em segundos.*'} inicio={-12} tamanho={84} />
      <CelularNaCena inicio={-4} barraClara fundoTela={fundo}>
        <PaginaSite e={e} cor={cor} fundo={fundo} rolagem={rolagem} ativo={agora?.[0]} destaque={destaque} />
        <Toque x={BOTAO_CONVERSOR.x} y={BOTAO_CONVERSOR.y} f={M.aperta} />
      </CelularNaCena>
      <Legendas falas={[
        {f: M.endereco, texto: 'Um endereço só seu', icone: '🌐'},
        {f: M.perfil, texto: 'Sua foto, seu nome e uma frase', icone: '📷'},
        {f: M.botoes, texto: 'Botões pros seus grupos e canais', icone: '🔗'},
        {f: M.redes, texto: 'Suas redes sociais', icone: '📱'},
        {f: M.conversor, texto: 'Um conversor de links no seu site', icone: '🔄'},
        {f: M.colar + 14, texto: 'Quem visita compra pelo seu link', icone: '🛒', tom: 'amarelo'},
        {f: M.vitrine, texto: 'Vitrine de ofertas com o seu link', icone: '🛍️'},
        {f: M.cores, texto: <span style={{display: 'inline-flex', alignItems: 'center', gap: 14}}>Nas cores que você quiser
          {[ROSA, AZUL, '#7048E8', '#2F9E44'].map((c) => (
            <span key={c} style={{width: 34, height: 34, borderRadius: '50%', background: c, flex: 'none',
              boxShadow: c === (f >= M.cores + 14 ? AZUL : ROSA) ? `0 0 0 4px ${C.branco}, 0 0 0 7px ${C.verde}` : 'none'}} />
          ))}</span>, icone: '🎨'},
        {f: M.topo, texto: 'Pronto para colocar na bio', icone: '✅', tom: 'amarelo'},
      ]} />
    </AbsoluteFill>
  );
};

const NUMEROS = [
  {rotulo: 'Cliques nos botões e redes', valor: 1389, icone: '👆'},
  {rotulo: 'Cliques nos produtos', valor: 2716, icone: '🛍️'},
  {rotulo: 'Links convertidos no conversor', valor: 342, icone: '🔄'},
];

const Numeros: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme}}>
      <Fundo tom="escuro" />
      <Cabecalho chapeu="Nos últimos 30 dias" titulo={'E você vê\no que *funciona.*'} inicio={4} escuro tamanho={92} />
      <div style={{position: 'absolute', left: 90, right: 90, top: POS.celular + 20, display: 'grid', gap: 28}}>
        {NUMEROS.map((n, i) => {
          const t = mola(f, 12 + i * 8, fps, 14);
          return (
            <div key={n.rotulo} style={{display: 'flex', alignItems: 'center', gap: 30, background: 'rgba(246,243,234,.08)', border: '3px solid rgba(246,243,234,.14)', borderRadius: 32,
              padding: '30px 36px', opacity: Math.min(1, t * 1.4), transform: `translateX(${(1 - t) * 80}px)`}}>
              <div style={{fontSize: 58}}>{n.icone}</div>
              <div>
                <div style={{fontSize: 30, color: C.suave, fontWeight: 500}}>{n.rotulo}</div>
                <div style={{fontSize: 80, fontWeight: 800, letterSpacing: '-.03em', color: i === 0 ? C.amarelo : C.creme}}><Conta ate={n.valor} inicio={16 + i * 8} duracao={46} /></div>
              </div>
            </div>
          );
        })}
      </div>
      <Legendas falas={[
        {f: 30, texto: 'Os produtos mais clicados em destaque', icone: '📈'},
        {f: 88, texto: 'Sub ID próprio para medir as vendas', icone: '📊', tom: 'amarelo'},
      ]} />
    </AbsoluteFill>
  );
};

export const SiteMonteOSeu: React.FC = () => (
  <AbsoluteFill style={{background: C.verde}}>
    <Sequence durationInFrames={MONTE.montagem}><Montagem /></Sequence>
    <Sequence from={MONTE.montagem} durationInFrames={MONTE.numeros}><Numeros /></Sequence>
    <Sequence from={MONTE.montagem + MONTE.numeros} durationInFrames={MONTE.final}>
      <Final frase={'Seu link na bio\n*que vende.*'} linha={CTA.site} inclusos={INCLUSOS} />
    </Sequence>
    <Sequence from={MONTE.montagem - 9} durationInFrames={18}><Cortina /></Sequence>
    <Sequence from={MONTE.montagem + MONTE.numeros - 9} durationInFrames={18}><Cortina /></Sequence>
  </AbsoluteFill>
);

// --- Site-DoStoryAoClique ------------------------------------------------------------------------

/** Frames da cena: as trocas de tela (+1 avança, -1 volta) e os momentos de cada parte. */
const T = {perfil: 82, site: 164, oferta: 236, indo1: 254, volta: 320, colar: 352, aperta: 390, indo2: 404, fim: 498};
const TROCAS: [number, number][] = [[T.perfil, 1], [T.site, 1], [T.indo1, 1], [T.volta, -1], [T.indo2, 1]];
const PASSOS = ['Story', 'Perfil', 'Seu site', 'Seu link'];
const STORY = {caminho: T.fim, final: DURACAO_FINAL.comInclusos};
export const DURACAO_SITE_STORY = STORY.caminho + STORY.final;

const TelaStory: React.FC = () => {
  const f = useCurrentFrame();
  const balanco = Math.sin(f / 9) * 6;
  return (
    <div style={{position: 'absolute', inset: 0, background: '#111', color: C.branco}}>
      <Img src={produto('fone')} style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover'}} />
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(0,0,0,.45) 0%, rgba(0,0,0,0) 28%, rgba(0,0,0,0) 50%, rgba(0,0,0,.7) 100%)'}} />
      <div style={{position: 'absolute', top: 66, left: 20, right: 20, display: 'flex', gap: 6}}>
        {[0, 1].map((i) => (
          <div key={i} style={{flex: 1, height: 5, borderRadius: 3, background: 'rgba(255,255,255,.4)', overflow: 'hidden'}}>
            <div style={{height: '100%', width: `${i === 0 ? vai(f, 0, T.perfil, 0, 100, (t) => t) : 0}%`, background: C.branco}} />
          </div>
        ))}
      </div>
      <div style={{position: 'absolute', top: 88, left: 20, display: 'flex', alignItems: 'center', gap: 12}}>
        <div style={{width: 52, height: 52, borderRadius: '50%', overflow: 'hidden', border: '2px solid #fff'}}><Img src={produto('bolsa')} style={{width: '100%', height: '100%', objectFit: 'cover'}} /></div>
        <div style={{fontSize: 21, fontWeight: 800}}>achadinhosdabia</div>
        <div style={{fontSize: 19, opacity: 0.8}}>2 h</div>
      </div>
      <div style={{position: 'absolute', left: 36, right: 36, bottom: 330, fontSize: 38, fontWeight: 800, lineHeight: 1.15, textShadow: '0 2px 10px rgba(0,0,0,.5)'}}>
        Achei esse fone por R$ 79,90 😱
      </div>
      <div style={{position: 'absolute', left: '50%', bottom: 200, transform: `translate(-50%, ${balanco}px) rotate(-3deg)`, background: C.branco, color: C.tinta,
        borderRadius: 20, padding: '18px 30px', fontSize: 30, fontWeight: 800, whiteSpace: 'nowrap', boxShadow: '0 10px 24px rgba(0,0,0,.35)'}}>
        🔗 Link na bio 👆
      </div>
    </div>
  );
};

const TelaPerfil: React.FC = () => (
  <div style={{position: 'absolute', inset: 0, background: C.branco, color: C.tinta}}>
    <div style={{position: 'absolute', top: 66, left: 0, right: 0, textAlign: 'center', fontSize: 23, fontWeight: 800}}>achadinhosdabia</div>
    <div style={{position: 'absolute', top: 128, left: 28, right: 28}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 26}}>
        <div style={{width: 128, height: 128, borderRadius: '50%', overflow: 'hidden', flex: 'none', border: `4px solid ${C.amarelo}`}}><Img src={produto('bolsa')} style={{width: '100%', height: '100%', objectFit: 'cover'}} /></div>
        <div style={{display: 'flex', flex: 1, justifyContent: 'space-around', textAlign: 'center'}}>
          {[['312', 'posts'], ['18,4 mil', 'seguidores'], ['210', 'seguindo']].map(([n, r]) => (
            <div key={r}><div style={{fontSize: 24, fontWeight: 800}}>{n}</div><div style={{fontSize: 16, color: C.cinza}}>{r}</div></div>
          ))}
        </div>
      </div>
      <div style={{fontSize: 21, fontWeight: 800, marginTop: 18}}>Achadinhos da Bia</div>
      <div style={{fontSize: 19, lineHeight: 1.4, marginTop: 4}}>Ofertas da Shopee todo dia ✨<br />Cupons e achadinhos aqui embaixo 👇</div>
      <div style={{fontSize: 18, fontWeight: 800, color: '#2F6FD8', marginTop: 8}}>🔗 {ENDERECO}</div>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4, marginTop: 26, marginLeft: -28, marginRight: -28}}>
        {['airfryer', 'garrafa', 'tenis', 'relogio', 'secador', 'mochila', 'luminaria', 'copo', 'kit'].map((p) => (
          <Img key={p} src={produto(p)} style={{width: '100%', height: 176, objectFit: 'cover', display: 'block'}} />
        ))}
      </div>
    </div>
  </div>
);

const Caminho: React.FC = () => {
  const f = useCurrentFrame();
  const pos = TROCAS.reduce((acc, [t, lado]) => acc + lado * vai(f, t, t + 16), 0);
  const atual = Math.round(pos);
  const fundo = fundoDe(AZUL);
  // a página: rola até a vitrine (jeito 1) e, na volta, sobe até o conversor (jeito 2)
  const rolagem = vai(f, T.site + 22, T.site + 50, 0, ROLAGEM.vitrine) - vai(f, T.volta + 16, T.volta + 40, 0, ROLAGEM.vitrine - ROLAGEM.conversor);
  const naVitrine = f < T.volta + 16;
  const e: Estado = {
    ...CHEIO,
    colado: f < T.colar ? undefined : <Digitando texto={LINK_COLADO} inicio={T.colar} fim={T.colar + 24} cursor={false} />,
    apertado: f >= T.aperta && f < T.aperta + 8,
  };
  const destaque = naVitrine ? Math.min(vai(f, T.site + 44, T.site + 54), vai(f, T.indo1 - 4, T.indo1 + 4, 1, 0))
    : Math.min(vai(f, T.volta + 36, T.volta + 46), vai(f, T.indo2 - 4, T.indo2 + 4, 1, 0));
  const indo = f < T.volta ? <TelaIndo inicio={T.indo1 + 8} oferta={OFERTAS[0]} subId="vitrine" /> : <TelaIndo inicio={T.indo2 + 8} oferta={OFERTAS[1]} subId="site" />;
  const telas = [
    <TelaStory key="story" />,
    <TelaPerfil key="perfil" />,
    <PaginaSite key="site" e={e} cor={AZUL} fundo={fundo} rolagem={rolagem} ativo={naVitrine ? 'vitrine' : 'conversor'} destaque={destaque} toqueProduto={T.oferta} />,
    <React.Fragment key="indo">{indo}</React.Fragment>,
  ];
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme}}>
      <Fundo tom="escuro" />
      <Cabecalho chapeu="Meu site" titulo={'Do story\n*ao clique.*'} inicio={-12} escuro tamanho={96} />
      <div style={{position: 'absolute', right: 90, top: POS.titulo + 54, display: 'grid', gap: 10, justifyItems: 'end', opacity: vai(f, 8, 22)}}>
        {PASSOS.map((p, i) => (
          <div key={p} style={{display: 'flex', alignItems: 'center', gap: 12, fontSize: 26, fontWeight: 800, color: i === atual ? C.verde : i < atual ? C.suave : 'rgba(246,243,234,.4)',
            background: i === atual ? C.amarelo : 'transparent', borderRadius: 999, padding: '6px 18px', transform: `scale(${i === atual ? 1.06 : 1})`, transformOrigin: 'right center'}}>
            {i < atual ? '✓' : `${i + 1}`} {p}
          </div>
        ))}
      </div>
      <CelularNaCena inicio={-6} barraClara={atual !== 1 && atual !== 3} fundoTela="#111">
        {telas.map((t, i) => (
          <div key={i} style={{position: 'absolute', top: 0, height: TELA.altura, width: TELA.largura, left: (i - pos) * TELA.largura}}>{t}</div>
        ))}
        <Toque x={130} y={112} f={T.perfil - 8} />
        <Toque x={250} y={384} f={T.site - 8} />
        <Toque x={PRODUTO_1.x} y={PRODUTO_1.y} f={T.oferta} />
        <Toque x={BOTAO_CONVERSOR.x} y={BOTAO_CONVERSOR.y} f={T.aperta} />
      </CelularNaCena>
      <Legendas falas={[
        {f: 6, texto: 'Seu story chama pra bio', icone: '📲'},
        {f: T.perfil + 8, texto: 'O endereço do seu site fica na bio', icone: '🔗'},
        {f: T.site + 20, texto: 'Jeito 1: uma oferta da vitrine', icone: '🛍️'},
        {f: T.indo1 + 10, texto: 'Vai pra Shopee pelo seu link', icone: '✓', tom: 'amarelo'},
        {f: T.volta + 14, texto: 'Jeito 2: um link colado no conversor', icone: '🔄'},
        {f: T.indo2 + 10, texto: 'Sua comissão com o Sub ID do site', icone: '✓', tom: 'amarelo'},
      ]} />
    </AbsoluteFill>
  );
};

export const SiteDoStoryAoClique: React.FC = () => (
  <AbsoluteFill style={{background: C.verde}}>
    <Sequence durationInFrames={STORY.caminho}><Caminho /></Sequence>
    <Sequence from={STORY.caminho} durationInFrames={STORY.final}>
      <Final frase={'Da bio pro produto\n*com o seu link.*'} linha={CTA.site} inclusos={INCLUSOS} />
    </Sequence>
    <Sequence from={STORY.caminho - 9} durationInFrames={18}><Cortina /></Sequence>
  </AbsoluteFill>
);
