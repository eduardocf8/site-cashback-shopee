/** Textos fixos e números dos vídeos de divulgação do Appfiliado. Os preços são os mensais do plano
 * Standard em landing/planos.py (PRECOS); mudou lá, muda aqui. Os dados das telas são os da conta
 * fictícia "Achadinhos da Bia", os mesmos dos prints do site. */

export const SITE = 'appfiliado.com.br';

export const PRECO = {
  bot: 'R$ 49,90',
  site: 'R$ 22,90',
};

export const CTA = {
  bot: `Bot de WhatsApp · a partir de ${PRECO.bot}/mês`,
  site: `Meu site · a partir de ${PRECO.site}/mês`,
  planos: `Planos a partir de ${PRECO.site}/mês`,
};

/** As ferramentas que vêm em todos os planos (as mesmas da faixa "Em todos os planos" da landing,
 * landing/views.py INCLUSOS). Vão no encerramento dos vídeos. */
export const INCLUSOS = [
  {icone: 'resultados', nome: 'Resultados e metas'},
  {icone: 'radar', nome: 'Radar de ofertas'},
  {icone: 'conversor', nome: 'Conversor de links'},
  {icone: 'bot', nome: 'Lia no WhatsApp'},
];

export const GRUPO = {nome: 'Achadinhos da Bia', membros: '1.248 participantes'};
export const ENDERECO = 'achadinhosdabia.appfiliado.com.br';

export type Oferta = {foto: string; nome: string; de: string; por: string; link: string; vendidos?: string; cupom?: string};

export const OFERTAS: Oferta[] = [
  {foto: 'fone', nome: 'Fone Bluetooth TWS com cancelamento de ruído', de: 'R$ 199,90', por: 'R$ 79,90', link: 's.shopee.com.br/8Kz1aQ', vendidos: '12 mil vendidos'},
  {foto: 'airfryer', nome: 'Air Fryer 4L com timer e painel touch', de: 'R$ 459,90', por: 'R$ 329,90', link: 's.shopee.com.br/4Lp9Xw', vendidos: '3 mil vendidos'},
  {foto: 'garrafa', nome: 'Garrafa térmica 1L inox parede dupla', de: 'R$ 89,90', por: 'R$ 49,90', link: 's.shopee.com.br/2Vb7Tr', vendidos: '8 mil vendidos'},
  {foto: 'tenis', nome: 'Tênis esportivo leve com amortecimento', de: 'R$ 249,90', por: 'R$ 139,90', link: 's.shopee.com.br/7Hn2Lp', vendidos: '5 mil vendidos'},
  {foto: 'relogio', nome: 'Smartwatch D20 Ultra com monitor cardíaco', de: 'R$ 159,90', por: 'R$ 89,90', link: 's.shopee.com.br/9Qe4Ds', vendidos: '20 mil vendidos'},
  {foto: 'secador', nome: 'Escova secadora 3 em 1 íons', de: 'R$ 239,90', por: 'R$ 149,90', link: 's.shopee.com.br/5Rt8Kc', vendidos: '6 mil vendidos'},
  {foto: 'mochila', nome: 'Mochila notebook impermeável USB', de: 'R$ 199,90', por: 'R$ 119,90', link: 's.shopee.com.br/3Mx6Vb', vendidos: '4 mil vendidos'},
  {foto: 'luminaria', nome: 'Luminária de mesa LED recarregável', de: 'R$ 99,90', por: 'R$ 54,90', link: 's.shopee.com.br/6Ty1Gh', vendidos: '9 mil vendidos'},
];
