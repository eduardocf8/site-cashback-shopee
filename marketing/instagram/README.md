# cash-b no Instagram — histórico e decisões

Este arquivo documenta o que já foi decidido e feito pro Instagram do
cash-b (@usecashb), pra qualquer conversa futura conseguir continuar sem
precisar reconstruir esse contexto do zero. Ver também `BRAND.md` na raiz
do repo pra identidade visual geral do site.

## Contexto

O objetivo final é um bot que publica automaticamente no Instagram
(stories diários + posts semanais no feed), usando a Instagram Graph API,
puxando dados reais do site (tabela `Oferta`, ver app `ofertas/`). Antes de
ligar a automação, o perfil precisou ser "semeado" manualmente com conteúdo
institucional, pra não ficar vazio quando o bot começar a postar.

## Roadmap do bot (fases)

1. **Configuração da conta e credenciais** — ✅ concluído. Conta do
   Instagram (`usecashb`) convertida pra profissional (Empresa), vinculada
   a uma Página do Facebook. App criado no Meta for Developers usando o
   caso de uso **"Gerenciar mensagens e conteúdo no Instagram"** (é o
   único, entre os ~20 casos de uso disponíveis, que expõe a configuração
   "API do Instagram com o Login do Instagram" — não aparece nos 6 "em
   destaque" da tela de criação, só ao filtrar por "Tudo"). Esse fluxo
   **não exige Página do Facebook nem revisão de app** pra uso na própria
   conta (Standard Access é suficiente quando só quem tem função no app
   usa a API).
   - Credenciais (App ID do Instagram, App Secret, Access Token de longa
     duração, Instagram Business Account ID) ficam como variáveis de
     ambiente no Render (`INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`,
     `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`) — **nunca**
     no repositório. O access token dura 60 dias e precisa de renovação
     (tratar isso na Fase 4).
2. **Definir conteúdo e frequência** — ✅ concluído. Calendário definido:
   - **Stories (todo dia)**: seg–sex destaque de 3–5 ofertas do dia
     (puxado da tabela `Oferta`); sábado dica de economia (rotativo);
     domingo lembrete de cashback (mensagem de marca).
   - **Posts no feed (2x por semana)**: quarta = post institucional
     (benefícios, curiosidades, como funciona, como usar); sexta = resumo
     das melhores ofertas da semana.
2.5. **Semear o perfil (manual, antes do bot)** — ✅ concluído (esta pasta).
   8 posts institucionais criados e aprovados pra postar manualmente antes
   de ligar a automação, pra o perfil não começar vazio.
3. **Templates de imagem parametrizados** — pendente. Vai reaproveitar o
   mesmo motor de geração (ver abaixo), mas lendo dados reais da tabela
   `Oferta` (nome, preço, desconto) em vez de texto fixo.
4. **Integração com a API do Instagram** — pendente. App Django novo
   (ex: `instagram_bot/`) que gera a imagem, publica via Graph API
   (`graph.instagram.com`, host correto pro Login do Instagram) e cuida da
   renovação do access token antes de expirar.
5. **Agendamento** — pendente. Mesmo padrão já usado pra sincronização
   diária (`/tarefas/executar/` chamado pelo GitHub Actions).
6. **Modo de revisão** — pendente. Rodar um tempo gerando as imagens sem
   publicar automaticamente, só pra aprovar antes de ativar 100%.
7. **Monitoramento** — pendente.

## Posts de semeadura (pasta `posts-semeadura/`)

8 imagens 1080×1080, prontas pra postar manualmente no feed antes da
automação começar. Conteúdo institucional (não puxa dado nenhum do banco):

| Arquivo | Tema |
|---|---|
| `01-o-que-e-cashb.png` | Apresentação da marca |
| `02-como-funciona.png` | Passo a passo do cashback (3 passos) |
| `03-venda-direta-indireta.png` | Link de produto x botão "Ir para a Shopee" |
| `04-do-clique-ao-pix.png` | Status do pedido: pendente → validado → liberado |
| `05-saque-pix.png` | Como sacar via PIX |
| `06-sem-pegadinha.png` | Sem mensalidade, sem letra miúda |
| `07-quanto-economizar.png` | Proposta de valor, sem prometer % específico |
| `08-cadastre-se.png` | Chamada pra ação (cash-b.com) |

Aprovados em 2026-08-01. Postar na ordem acima, indo 2–3 por dia até o
perfil ficar razoavelmente populado, antes de ligar a automação.

## Como as imagens são geradas

Script `gerar_posts_semeadura.py`: renderiza HTML/CSS via Playwright
(Chromium headless) a 1080×1080, usando as mesmas fontes e cores de
`static/css/brand.css` (Familjen Grotesk + JetBrains Mono, embutidas como
`data:` URI a partir dos arquivos woff2 do próprio site — sem chamada de
rede). Reaproveita o efeito `.mark` (grifo lima) do site pra destaque de
palavra-chave.

Pra rodar de novo (precisa do Chromium do Playwright disponível):

```bash
python3 marketing/instagram/gerar_posts_semeadura.py
```

Gera os 8 PNGs em `posts-semeadura/`, sobrescrevendo os existentes. Esse
script é a base que a Fase 3 (templates parametrizados com dados reais de
ofertas) vai estender.

## Decisões de conteúdo (não repetir)

- **Não afirmar valor de saque mínimo inexistente.** O site tem um valor
  mínimo de saque (`SAQUE_VALOR_MINIMO`, R$ 20 por padrão) — por isso o
  post `05-saque-pix.png` evita a frase "sem valor mínimo", que seria
  informação incorreta.
- **Não prometer percentual de cashback específico** em posts genéricos
  (`07-quanto-economizar.png`) — o percentual é configurável
  (`SHOPEE_CASHBACK_PERCENTUAL`) e pode mudar; melhor comunicar a
  proposta de valor sem número fixo que pode ficar desatualizado ou
  incorreto.
- **Conteúdo institucional espalhado ao longo da semana, não só fim de
  semana** — ideia do dono do produto: se só ofertas aparecem no feed
  durante a semana e conteúdo de marca só no fim de semana via stories,
  quem visita o perfil no meio da semana só vê preço/desconto e pode não
  entender a proposta. Por isso 1 dos 2 posts semanais do feed é sempre
  institucional (quarta-feira).
