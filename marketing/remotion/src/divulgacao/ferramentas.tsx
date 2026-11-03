/** Tema 4: as ferramentas inclusas em todos os planos. Duas versões:
 * - RadarAcheOProduto: "O que divulgar hoje?" -> busca, ordem por comissão (os cartões trocam de
 *   lugar), copiar o link de afiliado e a base de mais de 30 mil produtos.
 * - ConversorColeEConverta: a oferta copiada de outro grupo, colada no Conversor, cada link virando o
 *   seu (o texto fica igual) e a mensagem chegando no seu grupo.
 * Os fatos saem de landing/recursos.py (radar() e conversor()). */
import React from 'react';
import {AbsoluteFill, Img, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, FONTE} from '../appfiliado/marca';
import {Chip, Digitando, produto} from '../appfiliado/ui';
import {Apoio, Cabecalho, CelularNaCena, Cena, Conta, Cortina, DURACAO_FINAL, Final, Fundo, Legendas, POS, Titulo, Toque, mola, s, vai} from './comum';
import {CTA, GRUPO, INCLUSOS, OFERTAS} from './textos';

const ESCURO_AMARELO = '#8A6A00';

// --- Radar: o gancho ------------------------------------------------------------------------------

const Pergunta: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  // cartões de produto soltos em volta da pergunta, entrando devagar (a dúvida de qual escolher)
  const soltos = [
    {foto: 'fone', x: 120, y: 360, giro: -7},
    {foto: 'airfryer', x: 730, y: 360, giro: 7},
    {foto: 'tenis', x: 90, y: 1220, giro: 6},
    {foto: 'secador', x: 425, y: 1270, giro: 0},
    {foto: 'relogio', x: 760, y: 1220, giro: -6},
  ];
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme}}>
      <Fundo tom="escuro" />
      {soltos.map((p, i) => {
        const t = mola(f, 6 + i * 5, fps, 15);
        const flutua = Math.sin((f + i * 20) / 22) * 8;
        return (
          <div key={p.foto} style={{position: 'absolute', left: p.x, top: p.y + flutua, width: 230, padding: 12, borderRadius: 26, background: C.branco,
            boxShadow: '0 24px 40px rgba(0,0,0,.3)', opacity: 0.85 * t, transform: `rotate(${p.giro}deg) scale(${0.7 + 0.3 * t})`}}>
            <Img src={produto(p.foto)} style={{width: 206, height: 170, objectFit: 'cover', borderRadius: 16, display: 'block'}} />
            <div style={{height: 14, borderRadius: 7, background: C.borda, marginTop: 12, width: '80%'}} />
            <div style={{height: 14, borderRadius: 7, background: C.borda, marginTop: 8, width: '50%'}} />
          </div>
        );
      })}
      <div style={{position: 'absolute', left: 90, right: 90, top: 760}}>
        <Titulo texto={'O que divulgar\n*hoje?*'} inicio={-12} tamanho={124} cor={C.creme} alinhar="center" />
        <Apoio texto="Tanto produto. Por onde começar?" inicio={22} alinhar="center" cor={C.suave} tamanho={40} style={{marginTop: 30}} />
      </div>
    </AbsoluteFill>
  );
};

// --- Radar: a busca ------------------------------------------------------------------------------

type ItemRadar = {foto: string; nome: string; preco: string; comissao: number; reais: string; extra?: boolean; vendidos: string};

// a ordem de "Mais vendidos"; em "Maior comissão" eles trocam de lugar
const ITENS: ItemRadar[] = [
  {foto: 'fone', nome: 'Fone Bluetooth TWS Pro', preco: 'R$ 79,90', comissao: 12, reais: 'R$ 9,59', vendidos: '12 mil vendidos'},
  {foto: 'relogio', nome: 'Smartwatch D20 Ultra', preco: 'R$ 89,90', comissao: 10, reais: 'R$ 8,99', vendidos: '20 mil vendidos'},
  {foto: 'mochila', nome: 'Mochila notebook USB', preco: 'R$ 119,90', comissao: 18, reais: 'R$ 21,58', extra: true, vendidos: '4 mil vendidos'},
  {foto: 'secador', nome: 'Escova secadora 3 em 1', preco: 'R$ 149,90', comissao: 7, reais: 'R$ 10,49', vendidos: '6 mil vendidos'},
];
const POR_COMISSAO = [...ITENS].sort((a, b) => b.comissao - a.comissao);

const PAINEL = {x: 90, y: 600, largura: 900};
const CARTAO = {largura: 440, altura: 316, vao: 18, topo: 206};
const QUANDO = {busca: 18, ordem: 104, troca: 112, copiar: 196};

const posicao = (i: number) => ({x: (i % 2) * (CARTAO.largura + CARTAO.vao), y: CARTAO.topo + Math.floor(i / 2) * (CARTAO.altura + CARTAO.vao)});

const CartaoRadar: React.FC<{item: ItemRadar; copiado: boolean}> = ({item, copiado}) => (
  <div style={{width: CARTAO.largura, height: CARTAO.altura, background: C.branco, border: `3px solid ${C.borda}`, borderRadius: 28, padding: 14,
    boxShadow: '0 14px 30px rgba(23,48,31,.08)', display: 'flex', flexDirection: 'column'}}>
    <div style={{position: 'relative'}}>
      <Img src={produto(item.foto)} style={{width: '100%', height: 120, objectFit: 'cover', borderRadius: 18, display: 'block'}} />
      <div style={{position: 'absolute', top: 10, left: 10, background: C.amarelo, color: C.verde, fontWeight: 800, fontSize: 22, padding: '6px 14px', borderRadius: 999}}>
        {item.comissao}% comissão
      </div>
      {item.extra && <div style={{position: 'absolute', bottom: 10, left: 10, background: C.verde, color: C.creme, fontWeight: 800, fontSize: 18, padding: '5px 12px', borderRadius: 999}}>+ comissão extra</div>}
    </div>
    <div style={{fontSize: 24, fontWeight: 800, marginTop: 12, lineHeight: 1.3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{item.nome}</div>
    <div style={{fontSize: 19, color: C.cinza, lineHeight: 1.3}}>{item.vendidos}</div>
    <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 4}}>
      <div style={{fontSize: 27, fontWeight: 800}}>{item.preco}</div>
      <div style={{fontSize: 21, fontWeight: 800, color: C.ok}}>{item.reais} por venda</div>
    </div>
    <div style={{marginTop: 'auto', background: copiado ? C.amarelo : C.verde, color: copiado ? C.verde : C.creme, borderRadius: 14, textAlign: 'center',
      fontWeight: 800, fontSize: 22, padding: '11px 0'}}>{copiado ? '✓ Link copiado' : 'Copiar link'}</div>
  </div>
);

const Busca: React.FC = () => {
  const f = useCurrentFrame();
  const ordenado = f >= QUANDO.troca;
  const troca = vai(f, QUANDO.troca, QUANDO.troca + 26);
  const aparece = (i: number) => vai(f, 52 + i * 6, 66 + i * 6);
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.tinta}}>
      <Fundo tom="creme" />
      <Cabecalho chapeu="Radar de ofertas" titulo={'Ache o produto certo\n*em segundos.*'} inicio={4} tamanho={84} />
      <div style={{position: 'absolute', left: PAINEL.x, top: PAINEL.y, width: PAINEL.largura, height: 960}}>
        <div style={{background: C.branco, border: `3px solid ${C.borda}`, borderRadius: 26, padding: '22px 26px', display: 'flex', alignItems: 'center', gap: 16,
          opacity: vai(f, 6, 18)}}>
          <div style={{fontSize: 32}}>🔎</div>
          <div style={{fontSize: 32, fontWeight: 500, flex: 1}}>
            {f < QUANDO.busca ? <span style={{color: '#A8A08A'}}>Ex.: fone, air fryer, vestido</span> : <Digitando texto="eletrônicos" inicio={QUANDO.busca} fim={QUANDO.busca + 22} />}
          </div>
        </div>
        <div style={{display: 'flex', gap: 12, marginTop: 16, opacity: vai(f, 40, 52)}}>
          <Chip texto="Mais vendidos" ativo={!ordenado} />
          <Chip texto="Maior comissão" ativo={ordenado} />
          <Chip texto="Maior desconto" />
        </div>
        {ITENS.map((item, i) => {
          const antes = posicao(i);
          const depois = posicao(POR_COMISSAO.indexOf(item));
          const x = antes.x + (depois.x - antes.x) * troca;
          const y = antes.y + (depois.y - antes.y) * troca;
          // quem sobe pro topo passa por cima
          const z = depois.y < antes.y ? 3 : 1;
          const levanta = Math.sin(troca * Math.PI) * 0.04;
          const a = aparece(i);
          return (
            <div key={item.foto} style={{position: 'absolute', left: x, top: y + (1 - a) * 40, zIndex: z, opacity: a, transform: `scale(${1 + levanta})`}}>
              <CartaoRadar item={item} copiado={item === POR_COMISSAO[0] && f >= QUANDO.copiar + 2} />
            </div>
          );
        })}
      </div>
      {/* "Maior comissão" (2º chip) e o "Copiar link" do 1º cartão, em coordenadas da tela */}
      <Toque x={PAINEL.x + 340} y={PAINEL.y + 156} f={QUANDO.ordem} />
      <Toque x={PAINEL.x + CARTAO.largura / 2} y={PAINEL.y + CARTAO.topo + CARTAO.altura - 34} f={QUANDO.copiar} />
      <Legendas y={1490} falas={[
        {f: 48, icone: '🔎', texto: 'Busque por palavra ou categoria'},
        {f: QUANDO.ordem + 6, icone: '📈', texto: 'Ordene por maior comissão'},
        {f: QUANDO.copiar + 4, icone: '✓', tom: 'escuro', texto: 'Seu link de afiliado foi copiado'},
        {f: QUANDO.copiar + 54, icone: '📦', tom: 'amarelo', texto: <span>Mais de <Conta de={10000} ate={30000} inicio={QUANDO.copiar + 60} duracao={24} /> produtos</span>},
        {f: QUANDO.copiar + 104, icone: '🔄', texto: 'Atualizados todo dia'},
      ]} />
    </AbsoluteFill>
  );
};

const RADAR = {pergunta: s(2.6), busca: s(11.6), final: DURACAO_FINAL.comInclusos};
export const DURACAO_RADAR = RADAR.pergunta + RADAR.busca + RADAR.final;

export const RadarAcheOProduto: React.FC = () => (
  <AbsoluteFill style={{background: C.verde}}>
    <Sequence durationInFrames={RADAR.pergunta}><Pergunta /></Sequence>
    <Sequence from={RADAR.pergunta} durationInFrames={RADAR.busca}><Cena duracao={RADAR.busca} entrada={false} saida={false}><Busca /></Cena></Sequence>
    <Sequence from={RADAR.pergunta - 9} durationInFrames={18}><Cortina /></Sequence>
    <Sequence from={RADAR.pergunta + RADAR.busca} durationInFrames={RADAR.final}>
      <Cena duracao={RADAR.final} entrada={false} saida={false}><Final frase={'O produto certo\n*com o seu link.*'} linha={CTA.planos} inclusos={INCLUSOS} destaque="Radar de ofertas" /></Cena>
    </Sequence>
    <Sequence from={RADAR.pergunta + RADAR.busca - 9} durationInFrames={18}><Cortina cor={C.verde} /></Sequence>
  </AbsoluteFill>
);

// --- Conversor: as peças -------------------------------------------------------------------------

type Linha = {texto: string; antigo?: string; novo?: string};

// a mesma oferta: no grupo dos outros, com o link de outro afiliado; no seu, com o seu
const MENSAGEM: Linha[] = [
  {texto: '🔥 OFERTAS DO DIA 🔥'},
  {texto: `🎧 ${OFERTAS[0].nome.split(' com ')[0]} por ${OFERTAS[0].por}`, antigo: 's.shopee.com.br/xYz0utr0', novo: OFERTAS[0].link},
  {texto: `🍳 ${OFERTAS[1].nome.split(' com ')[0]} por ${OFERTAS[1].por}`, antigo: 'shope.ee/A1b2C3d4', novo: OFERTAS[1].link},
  {texto: `🧊 ${OFERTAS[2].nome.split(' inox')[0]} por ${OFERTAS[2].por}`, antigo: 's.shopee.com.br/0utroAfil', novo: OFERTAS[2].link},
];
const N_LINKS = MENSAGEM.filter((l) => l.novo).length;

/** Conversa de grupo com uma mensagem de várias linhas (o ConversaZap só tem oferta com foto e texto curto). */
const GrupoComMensagem: React.FC<{nome: string; membros: string; emoji: string; chega: number; hora: string; meus: boolean; autor?: string; segurando?: number; antes?: string}> = ({
  nome, membros, emoji, chega, hora, meus, autor, segurando, antes,
}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = mola(f, chega, fps, 15);
  const aperto = segurando !== undefined ? vai(f, segurando, segurando + 10) : 0;
  return (
    <div style={{position: 'absolute', inset: 0, background: C.zap, display: 'flex', flexDirection: 'column', fontFamily: FONTE}}>
      <div style={{height: 150, background: C.verde, color: C.creme, display: 'flex', alignItems: 'center', gap: 18, padding: '56px 26px 0', flex: 'none'}}>
        <span style={{fontSize: 34, opacity: 0.8}}>‹</span>
        <div style={{width: 64, height: 64, borderRadius: '50%', background: meus ? C.amarelo : '#C9D6CE', display: 'grid', placeItems: 'center', fontSize: 34}}>{emoji}</div>
        <div>
          <div style={{fontSize: 28, fontWeight: 800}}>{nome}</div>
          <div style={{fontSize: 20, color: C.suave}}>{membros}</div>
        </div>
      </div>
      <div style={{flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', padding: '0 22px 40px'}}>
        {antes && (
          <div style={{alignSelf: 'flex-start', background: C.balao, color: C.tinta, borderRadius: '8px 24px 24px 24px', padding: '12px 20px', fontSize: 25,
            marginBottom: 16, boxShadow: '0 4px 10px rgba(0,0,0,.07)'}}>
            {autor && <div style={{fontWeight: 800, color: meus ? '#2F8F6A' : '#B06A2F', fontSize: 20}}>{autor}</div>}
            {antes}
          </div>
        )}
        <div style={{opacity: f < chega ? 0 : Math.min(1, t * 1.5), transform: `translateY(${(1 - t) * 60}px) scale(${1 - 0.03 * aperto})`, transformOrigin: 'left bottom'}}>
          <div style={{background: aperto > 0 ? '#E3EEE6' : C.balao, color: C.tinta, borderRadius: '8px 24px 24px 24px', padding: '14px 20px', width: 500,
            boxShadow: '0 4px 10px rgba(0,0,0,.07)', fontSize: 25, lineHeight: 1.38}}>
            {autor && <div style={{fontWeight: 800, color: '#B06A2F', fontSize: 20}}>{autor}</div>}
            {MENSAGEM.map((l) => (
              <div key={l.texto} style={{marginBottom: l.novo ? 10 : 6}}>
                <div style={{fontWeight: l.novo ? 500 : 800}}>{l.texto}</div>
                {l.novo && <div style={{color: '#2F6FD8'}}>👉 {meus ? l.novo : l.antigo}</div>}
              </div>
            ))}
            <div style={{textAlign: 'right', fontSize: 18, color: '#8C978F'}}>{hora} <span style={{color: '#4FA3E0'}}>✓✓</span></div>
          </div>
        </div>
      </div>
    </div>
  );
};

/** Menu de "copiar" que abre sobre a mensagem segurada. */
const MenuCopiar: React.FC<{inicio: number; copiou: number}> = ({inicio, copiou}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (f < inicio) return null;
  const t = mola(f, inicio, fps, 14);
  const ativo = f >= copiou;
  return (
    <div style={{position: 'absolute', left: 120, top: 560, zIndex: 30, display: 'flex', gap: 6, background: C.branco, color: C.tinta, borderRadius: 20, padding: 8,
      boxShadow: '0 16px 40px rgba(0,0,0,.25)', fontFamily: FONTE, fontSize: 24, fontWeight: 800, opacity: Math.min(1, t * 1.4), transform: `scale(${0.8 + 0.2 * t})`}}>
      <div style={{padding: '12px 20px', borderRadius: 14, color: C.cinza}}>↩ Responder</div>
      <div style={{padding: '12px 20px', borderRadius: 14, background: ativo ? C.amarelo : 'transparent', color: C.verde}}>📋 Copiar</div>
    </div>
  );
};

// --- Conversor: as cenas -------------------------------------------------------------------------

const C1 = {segura: 58, menu: 66, copia: 84};

const OutroGrupo: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.tinta}}>
      <Fundo tom="creme" />
      <Cabecalho chapeu="Conversor de links" titulo={'Achou uma oferta\nboa em *outro grupo?*'} inicio={-12} tamanho={84} />
      <CelularNaCena hora="10:12">
        <GrupoComMensagem nome="Promoções Relâmpago" membros="842 participantes" emoji="⚡" chega={10} hora="10:12" meus={false} autor="~ Carlos" segurando={C1.segura} antes="Bom dia, pessoal! ☀️" />
        <MenuCopiar inicio={C1.menu} copiou={C1.copia} />
      </CelularNaCena>
      <Toque x={522} y={1277} f={C1.segura} />
      <Legendas falas={[
        {f: 28, icone: '⛔', texto: 'Com o link de outro afiliado'},
        {f: C1.copia + 2, icone: '📋', tom: 'escuro', texto: 'Mensagem copiada'},
      ]} />
    </AbsoluteFill>
  );
};

const C2 = {cola: 16, converte: 62, troca: 74, passo: 16, copia: 176};

const LinkQueTroca: React.FC<{antigo: string; novo: string; inicio: number}> = ({antigo, novo, inicio}) => {
  const f = useCurrentFrame();
  const t = vai(f, inicio, inicio + 12);
  const brilho = vai(f, inicio + 6, inicio + 30, 1, 0);
  return (
    <div style={{position: 'relative', height: 44}}>
      <div style={{position: 'absolute', color: '#9A9282', opacity: 1 - t, transform: `translateY(${-t * 14}px)`}}>👉 <span style={{textDecoration: 'line-through'}}>{antigo}</span></div>
      <div style={{position: 'absolute', opacity: t, transform: `translateY(${(1 - t) * 14}px)`}}>
        👉 <span style={{background: `rgba(242,194,48,${0.35 + 0.4 * brilho})`, borderRadius: 8, padding: '0 8px', color: C.verde, fontWeight: 800}}>{novo}</span>
      </div>
    </div>
  );
};

const Converte: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const colado = mola(f, C2.cola, fps, 15);
  const convertido = f >= C2.converte + 4;
  const fimDasTrocas = C2.troca + (N_LINKS - 1) * C2.passo + 12;
  let n = 0;
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme}}>
      <Fundo tom="escuro" />
      <Cabecalho chapeu="Conversor de links" titulo={'Cole, converta\ne *encaminhe.*'} inicio={4} escuro tamanho={92} />
      <div style={{position: 'absolute', left: 90, width: 900, top: 650, background: C.branco, color: C.tinta, borderRadius: 34, padding: 30,
        boxShadow: '0 30px 60px rgba(0,0,0,.3)', opacity: vai(f, 2, 14)}}>
        <div style={{fontSize: 24, fontWeight: 800, color: C.cinza}}>{convertido ? 'Pronto pra encaminhar' : 'Cole o texto ou os links'}</div>
        <div style={{marginTop: 14, background: '#FBF9F3', border: `3px solid ${C.borda}`, borderRadius: 22, padding: '24px 26px', fontSize: 27, lineHeight: 1.45, height: 404}}>
          <div style={{opacity: colado, transform: `translateY(${(1 - colado) * 24}px)`}}>
            {MENSAGEM.map((l) => {
              const inicio = l.novo ? C2.troca + n++ * C2.passo : 0;
              return (
                <div key={l.texto} style={{marginBottom: 10}}>
                  <div style={{fontWeight: l.novo ? 500 : 800}}>{l.texto}</div>
                  {l.novo && l.antigo && <LinkQueTroca antigo={l.antigo} novo={l.novo} inicio={inicio} />}
                </div>
              );
            })}
          </div>
        </div>
        <div style={{display: 'flex', alignItems: 'center', gap: 14, marginTop: 22}}>
          <Chip texto="Manter o texto e trocar os links" ativo />
          <div style={{flex: 1}} />
          <div style={{background: convertido ? C.verde : C.amarelo, color: convertido ? C.creme : C.verde, fontWeight: 800, fontSize: 26, borderRadius: 999, padding: '16px 30px',
            transform: `scale(${(f >= C2.converte - 2 && f < C2.converte + 6) || (f >= C2.copia - 2 && f < C2.copia + 6) ? 0.94 : 1})`}}>
            {!convertido ? 'Converter' : f >= C2.copia + 4 ? '✓ Copiado' : 'Copiar texto'}
          </div>
        </div>
      </div>
      <Toque x={870} y={1186} f={C2.converte} />
      <Toque x={870} y={1186} f={C2.copia} />
      <Legendas y={1300} falas={[
        {f: C2.troca + 2, icone: '✓', tom: 'amarelo', texto: <span><Conta ate={N_LINKS} inicio={C2.troca} duracao={fimDasTrocas - C2.troca} /> links trocados pelo seu</span>},
        {f: fimDasTrocas + 14, icone: '🔗', texto: 'Até 20 links de uma vez'},
        {f: C2.copia + 6, icone: '📋', tom: 'escuro', texto: 'Copiado: é só encaminhar'},
      ]} />
    </AbsoluteFill>
  );
};

const NoSeuGrupo: React.FC = () => (
  <AbsoluteFill style={{fontFamily: FONTE, color: C.tinta}}>
    <Fundo tom="creme" />
    <div style={{position: 'absolute', left: 90, right: 90, top: POS.titulo}}>
      <Titulo texto={'No seu grupo\n*com o seu link.*'} inicio={2} tamanho={92} destaque={ESCURO_AMARELO} />
    </div>
    <CelularNaCena hora="10:13">
      <GrupoComMensagem nome={GRUPO.nome} membros={GRUPO.membros} emoji="🛍️" chega={8} hora="10:13" meus antes="Achadinhos de hoje 👇" />
    </CelularNaCena>
    <Legendas falas={[
      {f: 30, icone: '✓', tom: 'amarelo', texto: 'A comissão cai na sua conta'},
    ]} />
  </AbsoluteFill>
);

const CONV = {outro: s(4.5), converte: s(8.4), seu: s(3.2), final: DURACAO_FINAL.comInclusos};
export const DURACAO_CONVERSOR = CONV.outro + CONV.converte + CONV.seu + CONV.final;

export const ConversorColeEConverta: React.FC = () => {
  const b = CONV.outro;
  const c = b + CONV.converte;
  const d = c + CONV.seu;
  return (
    <AbsoluteFill style={{background: C.verde}}>
      <Sequence durationInFrames={CONV.outro}><OutroGrupo /></Sequence>
      <Sequence from={b} durationInFrames={CONV.converte}><Cena duracao={CONV.converte} entrada={false} saida={false}><Converte /></Cena></Sequence>
      <Sequence from={b - 9} durationInFrames={18}><Cortina /></Sequence>
      <Sequence from={c} durationInFrames={CONV.seu}><Cena duracao={CONV.seu} entrada={false} saida={false}><NoSeuGrupo /></Cena></Sequence>
      <Sequence from={c - 9} durationInFrames={18}><Cortina cor={C.verde} /></Sequence>
      <Sequence from={d} durationInFrames={CONV.final}>
        <Cena duracao={CONV.final} entrada={false} saida={false}><Final frase={'Qualquer oferta\n*com o seu link.*'} linha={CTA.planos} inclusos={INCLUSOS} destaque="Conversor de links" /></Cena>
      </Sequence>
      <Sequence from={d - 9} durationInFrames={18}><Cortina /></Sequence>
    </AbsoluteFill>
  );
};
