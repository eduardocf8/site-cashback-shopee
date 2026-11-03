/** Tema 2: Meu site (o link na bio do afiliado Shopee). Duas versões:
 * - SiteMonteOSeu: o site se montando no celular, peça por peça, e os cliques contados.
 * - SiteDoStoryAoClique: o caminho do seguidor, do story ao produto pelo seu link de afiliado.
 * Tudo o que aparece existe no Meu site (landing/recursos.py, função site()). */
import React from 'react';
import {AbsoluteFill, Img, Sequence, interpolateColors, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, FONTE} from '../appfiliado/marca';
import {Digitando, produto} from '../appfiliado/ui';
import {Celular, Cena, Chapeu, Conta, Cortina, Etiqueta, Final, Fundo, TELA, Titulo, Toque, mola, s, vai} from './comum';
import {CTA, ENDERECO, OFERTAS} from './textos';

const ESCURO_AMARELO = '#8A6A00';
const ROSA = '#D6336C';
const AZUL = '#2F6FD8';
const BOTOES = ['💬 Grupo VIP de ofertas', '📣 Canal de ofertas', '🎟️ Cupons do dia'];
const REDES = ['📸', '🎵', '▶️', '💬'];
const VITRINE = OFERTAS.slice(0, 6);
const desconto = (de: string, por: string) => {
  const n = (v: string) => Number(v.replace(/[^\d,]/g, '').replace(',', '.'));
  return `-${Math.round((1 - n(por) / n(de)) * 100)}%`;
};

/** Mostra o filho entre `de` e `ate` (some suave no fim). */
const Janela: React.FC<{de: number; ate: number; children: React.ReactNode; style?: React.CSSProperties}> = ({de, ate, children, style}) => {
  const f = useCurrentFrame();
  if (f < de || f > ate) return null;
  return <div style={{position: 'absolute', opacity: vai(f, ate - 10, ate, 1, 0), ...style}}>{children}</div>;
};

// --- a página do Meu site, desenhada na tela do celular (560 x 1120) -------------------------------

type Partes = {endereco: string; foto: number; nome: React.ReactNode; frase: number; botoes: number[]; redes: number; vitrine: number; conversor?: number};

const PaginaSite: React.FC<{p: Partes; cor: string; rolagem?: number; toqueProduto?: number}> = ({p, cor, rolagem = 0, toqueProduto}) => {
  const f = useCurrentFrame();
  const sobe = (t: number) => ({opacity: Math.min(1, t * 1.3), transform: `translateY(${(1 - t) * 26}px) scale(${0.94 + 0.06 * t})`});
  return (
    <div style={{position: 'absolute', inset: 0, background: cor, color: C.branco, fontFamily: FONTE, overflow: 'hidden'}}>
      <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 120, background: cor, zIndex: 4}} />
      <div style={{position: 'absolute', top: 60, left: 18, right: 18, height: 50, borderRadius: 25, background: 'rgba(255,255,255,.94)', zIndex: 5, display: 'flex', alignItems: 'center',
        gap: 8, padding: '0 16px', fontSize: 19, fontWeight: 800, color: C.tinta, whiteSpace: 'nowrap', overflow: 'hidden', letterSpacing: '-.01em'}}>
        <span style={{fontSize: 15}}>🔒</span>{p.endereco}
      </div>
      <div style={{position: 'absolute', left: 30, right: 30, top: 136, textAlign: 'center', transform: `translateY(${-rolagem}px)`}}>
        <div style={{width: 132, height: 132, margin: '0 auto', borderRadius: '50%', overflow: 'hidden', border: '5px solid rgba(255,255,255,.7)', ...sobe(p.foto)}}>
          <Img src={produto('bolsa')} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        </div>
        <div style={{fontSize: 34, fontWeight: 800, marginTop: 14, minHeight: 42}}>{p.nome}</div>
        <div style={{fontSize: 19, marginTop: 4, opacity: 0.9 * p.frase}}>As melhores ofertas da Shopee, todo dia ✨</div>
        <div style={{display: 'grid', gap: 12, marginTop: 22}}>
          {BOTOES.map((b, i) => (
            <div key={b} style={{borderRadius: 18, padding: '16px 10px', fontSize: 21, fontWeight: 800, ...sobe(p.botoes[i] ?? 0),
              background: i === 0 ? C.branco : 'rgba(255,255,255,.16)', color: i === 0 ? cor : C.branco, border: i === 0 ? 'none' : '2px solid rgba(255,255,255,.5)'}}>{b}</div>
          ))}
        </div>
        <div style={{display: 'flex', justifyContent: 'center', gap: 14, marginTop: 20}}>
          {REDES.map((r, i) => (
            <div key={r} style={{width: 54, height: 54, borderRadius: '50%', background: 'rgba(255,255,255,.2)', display: 'grid', placeItems: 'center', fontSize: 24,
              ...sobe(Math.min(1, Math.max(0, p.redes * 4 - i)))}}>{r}</div>
          ))}
        </div>
        <div style={{textAlign: 'left', fontSize: 22, fontWeight: 800, marginTop: 28, opacity: p.vitrine}}>Ofertas de hoje</div>
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12, marginTop: 12}}>
          {VITRINE.map((o, i) => {
            const t = Math.min(1, Math.max(0, p.vitrine * 6 - i));
            return (
              <div key={o.foto} style={{position: 'relative', background: C.branco, color: C.tinta, borderRadius: 16, padding: 8, textAlign: 'left', ...sobe(t)}}>
                <div style={{position: 'relative'}}>
                  <Img src={produto(o.foto)} style={{width: '100%', height: 150, objectFit: 'cover', borderRadius: 10, display: 'block'}} />
                  <div style={{position: 'absolute', top: 8, left: 8, background: C.amarelo, color: C.verde, fontSize: 15, fontWeight: 800, padding: '3px 9px', borderRadius: 999}}>{desconto(o.de, o.por)}</div>
                </div>
                <div style={{fontSize: 15, marginTop: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{o.nome}</div>
                <div style={{fontSize: 21, fontWeight: 800}}>{o.por}</div>
                {i === 0 && toqueProduto !== undefined && f >= toqueProduto && f < toqueProduto + 12 && (
                  <div style={{position: 'absolute', inset: 0, borderRadius: 16, outline: `4px solid ${C.amarelo}`}} />
                )}
              </div>
            );
          })}
        </div>
        {p.conversor !== undefined && (
          <div style={{background: C.branco, color: C.tinta, borderRadius: 18, padding: 18, marginTop: 18, textAlign: 'left', opacity: p.conversor}}>
            <div style={{fontSize: 22, fontWeight: 800}}>Achou algo na Shopee?</div>
            <div style={{fontSize: 16, color: C.cinza, marginTop: 4}}>Cole o link do produto e compre pelo meu link.</div>
          </div>
        )}
        <div style={{fontSize: 15, opacity: 0.75 * p.vitrine, marginTop: 22}}>Feito com Appfiliado</div>
      </div>
    </div>
  );
};

// --- Site-MonteOSeu ---------------------------------------------------------------------------------

const MONTE = {montagem: s(12), numeros: s(4.2), final: s(3.6)};
export const DURACAO_SITE_MONTE = MONTE.montagem + MONTE.numeros + MONTE.final;

const Montagem: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const n = Math.round(vai(f, 30, 72, 0, ENDERECO.length));
  const cor = interpolateColors(f, [300, 318], [ROSA, AZUL]);
  const partes: Partes = {
    endereco: f < 30 ? '' : ENDERECO.slice(0, n),
    foto: mola(f, 80, fps, 12),
    nome: f < 104 ? '' : <Digitando texto="Achadinhos da Bia" inicio={104} fim={126} cursor={false} />,
    frase: vai(f, 126, 140),
    botoes: [0, 1, 2].map((i) => mola(f, 148 + i * 12, fps, 13)),
    redes: vai(f, 192, 214),
    vitrine: vai(f, 224, 262),
  };
  const rolagem = vai(f, 250, 292, 0, 330);
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.tinta}}>
      <Fundo tom="creme" />
      <div style={{position: 'absolute', left: 90, right: 90, top: 330}}>
        <Chapeu texto="Meu site" inicio={-14} />
        <Titulo texto={'Seu link na bio\n*pronto em segundos.*'} inicio={-12} tamanho={80} destaque={ESCURO_AMARELO} style={{marginTop: 26}} />
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 690, display: 'flex', justifyContent: 'center', opacity: vai(f, 8, 22), transform: `translateY(${(1 - vai(f, 8, 26)) * 60}px)`}}>
        <Celular escala={0.79} barraClara fundoTela={cor}>
          <PaginaSite p={partes} cor={cor} rolagem={rolagem} />
        </Celular>
      </div>
      <Janela de={28} ate={78} style={{left: 60, top: 900}}><Etiqueta texto="🌐 Um endereço só seu" inicio={28} tom="escuro" /></Janela>
      <Janela de={80} ate={140} style={{right: 60, top: 820}}><Etiqueta texto="📷 Sua foto e o seu nome" inicio={80} /></Janela>
      <Janela de={148} ate={200} style={{left: 60, top: 1080}}><Etiqueta texto="🔗 Botões com os seus links" inicio={148} tom="amarelo" /></Janela>
      <Janela de={192} ate={244} style={{right: 60, top: 1240}}><Etiqueta texto="📱 Suas redes" inicio={192} /></Janela>
      <Janela de={226} ate={292} style={{left: 60, top: 1380}}><Etiqueta texto="🛍️ Vitrine de ofertas" inicio={226} tom="escuro" /></Janela>
      <Janela de={290} ate={MONTE.montagem} style={{right: 60, top: 1180}}>
        <Etiqueta inicio={290} texto={<span style={{display: 'flex', alignItems: 'center', gap: 10}}>🎨 Suas cores
          {[ROSA, AZUL, C.verde, '#7048E8'].map((c) => <span key={c} style={{width: 30, height: 30, borderRadius: '50%', background: c, outline: c === AZUL && f >= 306 ? `3px solid ${C.amarelo}` : 'none', outlineOffset: 2}} />)}
        </span>} />
      </Janela>
      <Toque x={889} y={1214} f={304} />
    </AbsoluteFill>
  );
};

const NUMEROS = [
  {rotulo: 'Cliques nos botões e redes', valor: 1389, icone: '👆'},
  {rotulo: 'Cliques nos produtos', valor: 2716, icone: '🛍️'},
  {rotulo: 'Links convertidos', valor: 342, icone: '🔄'},
];

const Numeros: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme}}>
      <Fundo tom="escuro" />
      <div style={{position: 'absolute', left: 90, right: 90, top: 360}}>
        <Chapeu texto="Nos últimos 30 dias" cor={C.amarelo} />
        <Titulo texto={'E você vê\no que *funciona.*'} inicio={4} tamanho={96} cor={C.creme} style={{marginTop: 26}} />
      </div>
      <div style={{position: 'absolute', left: 90, right: 90, top: 760, display: 'grid', gap: 26}}>
        {NUMEROS.map((n, i) => {
          const t = mola(f, 14 + i * 8, fps, 14);
          return (
            <div key={n.rotulo} style={{display: 'flex', alignItems: 'center', gap: 28, background: 'rgba(246,243,234,.08)', border: '3px solid rgba(246,243,234,.14)', borderRadius: 32,
              padding: '30px 36px', opacity: Math.min(1, t * 1.4), transform: `translateX(${(1 - t) * 80}px)`}}>
              <div style={{fontSize: 58}}>{n.icone}</div>
              <div>
                <div style={{fontSize: 30, color: C.suave, fontWeight: 500}}>{n.rotulo}</div>
                <div style={{fontSize: 78, fontWeight: 800, letterSpacing: '-.03em', color: i === 0 ? C.amarelo : C.creme}}><Conta ate={n.valor} inicio={18 + i * 8} duracao={46} /></div>
              </div>
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', left: 90, top: 1440}}><Etiqueta inicio={60} tom="amarelo" texto="Sub ID próprio: as vendas aparecem em Resultados" tamanho={28} /></div>
    </AbsoluteFill>
  );
};

export const SiteMonteOSeu: React.FC = () => (
  <AbsoluteFill style={{background: C.verde}}>
    <Sequence durationInFrames={MONTE.montagem}><Cena duracao={MONTE.montagem} entrada={false} saida={false}><Montagem /></Cena></Sequence>
    <Sequence from={MONTE.montagem} durationInFrames={MONTE.numeros}><Cena duracao={MONTE.numeros} entrada={false} saida={false}><Numeros /></Cena></Sequence>
    <Sequence from={MONTE.montagem + MONTE.numeros} durationInFrames={MONTE.final}><Cena duracao={MONTE.final} entrada={false} saida={false}><Final frase={'Seu link na bio\n*que vende.*'} linha={CTA.site} /></Cena></Sequence>
    <Sequence from={MONTE.montagem - 9} durationInFrames={18}><Cortina /></Sequence>
    <Sequence from={MONTE.montagem + MONTE.numeros - 9} durationInFrames={18}><Cortina cor={C.verde} /></Sequence>
  </AbsoluteFill>
);

// --- Site-DoStoryAoClique ------------------------------------------------------------------------

const PASSOS = ['Story', 'Perfil', 'Seu site', 'Loja'];
const TROCAS = [100, 196, 352]; // frames em que a tela desliza pra próxima
const STORY = {caminho: 450, final: s(3.6)};
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
            <div style={{height: '100%', width: `${i === 0 ? vai(f, 0, TROCAS[0], 0, 100, (t) => t) : 0}%`, background: C.branco}} />
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

const TelaLoja: React.FC<{inicio: number}> = ({inicio}) => {
  const f = useCurrentFrame();
  const o = OFERTAS[0];
  return (
    <div style={{position: 'absolute', inset: 0, background: C.creme, color: C.tinta, padding: '120px 34px 0'}}>
      <div style={{background: C.branco, borderRadius: 26, padding: 18, boxShadow: '0 12px 30px rgba(23,48,31,.1)'}}>
        <Img src={produto(o.foto)} style={{width: '100%', height: 300, objectFit: 'cover', borderRadius: 18, display: 'block'}} />
        <div style={{fontSize: 22, fontWeight: 800, marginTop: 14}}>{o.nome}</div>
        <div style={{marginTop: 6}}><span style={{color: C.cinza, textDecoration: 'line-through', fontSize: 20}}>{o.de}</span> <span style={{fontSize: 32, fontWeight: 800, color: C.ok}}>{o.por}</span></div>
      </div>
      <div style={{marginTop: 30, fontSize: 24, fontWeight: 800, textAlign: 'center'}}>Indo pra Shopee pelo seu link</div>
      <div style={{height: 12, borderRadius: 999, background: C.borda, marginTop: 16, overflow: 'hidden'}}>
        <div style={{height: '100%', width: `${vai(f, inicio, inicio + 50, 0, 100)}%`, background: C.verde, borderRadius: 999}} />
      </div>
      <div style={{marginTop: 26, display: 'grid', gap: 12, justifyItems: 'center', opacity: vai(f, inicio + 20, inicio + 34)}}>
        <div style={{background: C.verde, color: C.creme, borderRadius: 999, padding: '12px 22px', fontSize: 20, fontWeight: 800}}>👉 {o.link}</div>
        <div style={{background: C.amarelo, color: C.verde, borderRadius: 999, padding: '10px 20px', fontSize: 18, fontWeight: 800}}>Link de afiliado · Sub ID: site</div>
      </div>
    </div>
  );
};

const Caminho: React.FC = () => {
  const f = useCurrentFrame();
  const pos = TROCAS.reduce((acc, t) => acc + vai(f, t, t + 16), 0);
  const atual = Math.round(pos);
  const telas = [
    <TelaStory key="story" />,
    <TelaPerfil key="perfil" />,
    <PaginaSite key="site" cor={C.verde} rolagem={vai(f, 222, 262, 0, 420)} toqueProduto={300}
      p={{endereco: ENDERECO, foto: 1, nome: 'Achadinhos da Bia', frase: 1, botoes: [1, 1, 1], redes: 1, vitrine: 1}} />,
    <TelaLoja key="loja" inicio={TROCAS[2] + 10} />,
  ];
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme}}>
      <Fundo tom="escuro" />
      <div style={{position: 'absolute', left: 90, right: 90, top: 330}}>
        <Chapeu texto="Meu site" cor={C.amarelo} inicio={-14} />
        <Titulo texto={'Do story\n*ao clique.*'} inicio={-12} tamanho={96} cor={C.creme} style={{marginTop: 26}} />
      </div>
      <div style={{position: 'absolute', right: 90, top: 440, display: 'grid', gap: 10, justifyItems: 'end', opacity: vai(f, 12, 26)}}>
        {PASSOS.map((p, i) => (
          <div key={p} style={{display: 'flex', alignItems: 'center', gap: 12, fontSize: 26, fontWeight: 800, color: i === atual ? C.verde : i < atual ? C.suave : 'rgba(246,243,234,.4)',
            background: i === atual ? C.amarelo : 'transparent', borderRadius: 999, padding: '6px 18px', transform: `scale(${i === atual ? 1.06 : 1})`, transformOrigin: 'right center'}}>
            {i < atual ? '✓' : `${i + 1}`} {p}
          </div>
        ))}
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 690, display: 'flex', justifyContent: 'center'}}>
        <Celular escala={0.79} barraClara={atual !== 1 && atual !== 3} fundoTela="#111">
          {telas.map((t, i) => (
            <div key={i} style={{position: 'absolute', top: 0, height: TELA.altura, width: TELA.largura, left: (i - pos) * TELA.largura}}>{t}</div>
          ))}
          <Toque x={130} y={112} f={88} />
          <Toque x={250} y={384} f={184} />
          <Toque x={150} y={560} f={300} />
        </Celular>
      </div>
      <Janela de={20} ate={96} style={{right: 60, top: 860}}><Etiqueta texto="📲 Seu story chama pra bio" inicio={20} /></Janela>
      <Janela de={120} ate={192} style={{right: 60, top: 1020}}><Etiqueta texto="🔗 Seu endereço na bio" inicio={120} tom="amarelo" /></Janela>
      <Janela de={214} ate={300} style={{left: 60, top: 1150}}><Etiqueta texto="🛍️ Vitrine com o seu link" inicio={214} /></Janela>
      <Janela de={262} ate={348} style={{right: 60, top: 1420}}><Etiqueta texto="🔄 E um conversor de links" inicio={262} tom="escuro" /></Janela>
      <div style={{position: 'absolute', left: 60, top: 1520}}><Etiqueta texto="✓ A comissão é sua" inicio={TROCAS[2] + 40} tom="amarelo" tamanho={34} /></div>
      <div style={{position: 'absolute', right: 60, top: 1420}}>
        <Etiqueta inicio={TROCAS[2] + 54} texto={<span>👆 <Conta ate={1389} inicio={TROCAS[2] + 54} duracao={40} /> cliques em 30 dias</span>} />
      </div>
    </AbsoluteFill>
  );
};

export const SiteDoStoryAoClique: React.FC = () => (
  <AbsoluteFill style={{background: C.verde}}>
    <Sequence durationInFrames={STORY.caminho}><Cena duracao={STORY.caminho} entrada={false} saida={false}><Caminho /></Cena></Sequence>
    <Sequence from={STORY.caminho} durationInFrames={STORY.final}><Cena duracao={STORY.final} entrada={false} saida={false}><Final frase={'Da bio pro produto\n*com o seu link.*'} linha={CTA.site} /></Cena></Sequence>
    <Sequence from={STORY.caminho - 9} durationInFrames={18}><Cortina /></Sequence>
  </AbsoluteFill>
);
