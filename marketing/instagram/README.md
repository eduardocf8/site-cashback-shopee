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

8 imagens 1080×1080 (arquivo real 2160×2160, renderizado em dobro pra
ficar nítido), prontas pra postar manualmente no feed antes da automação
começar. Conteúdo institucional (não puxa dado nenhum do banco). Artes e
legendas aprovadas em 2026-08-01.

Cronograma: 1 post por dia, na ordem abaixo (é a mesma ordem que conta uma
narrativa se alguém rolar o grid inteiro — não embaralhar).

### Dia 1 — `01-o-que-e-cashb.png`
> O cash-b é simples: você compra na Shopee do jeito que já compra, e recebe parte do dinheiro de volta. 💸 Sem mensalidade, sem pegadinha — só cashback de verdade caindo no seu saldo. 💚
> Ainda não conhece? Link na bio.
> #cashback #shopee #cashbackshopee #economia #dinheirodevolta

### Dia 2 — `02-como-funciona.png`
> Não tem mistério: 🔗 gera o link (ou vai direto pra Shopee), 🛍️ compra normalmente, e 💰 recebe parte de volta assim que a Shopee confirma o pedido. 3 passos, sem burocracia.
> Testa você mesmo — link na bio.
> #cashback #shopee #comofunciona #economia

### Dia 3 — `03-venda-direta-indireta.png`
> Sabia que converter o link do produto específico pode render mais cashback? ⚡ Quando a Shopee tem campanha de comissão extra ativa, só quem usa o link direto tem acesso ao bônus. Já quem prefere só entrar e comprar o que quiser, também garante cashback — sem escolher nada antes.
> Duas formas, o mesmo cashback de verdade. ✅
> #cashback #shopee #dicas

### Dia 4 — `04-do-clique-ao-pix.png`
> Depois da compra, seu cashback passa por 3 fases: ⏳ pendente (aguardando a Shopee confirmar), ✅ validado (compra confirmada, aguardando o prazo) e 💸 liberado (já pode sacar). Acompanha tudo direto no seu painel.
> #cashback #shopee #transparencia

### Dia 5 — `05-saque-pix.png`
> Saldo liberado é saldo seu. 💸 Cadastra sua chave PIX e pede o saque — sem burocracia, direto na sua conta. 🏦
> #cashback #pix #shopee #dinheirodevolta

### Dia 6 — `06-sem-pegadinha.png`
> 🚫 Sem mensalidade. 🚫 Sem letra miúda. 🚫 Sem "cashback" que nunca cai na conta. Você compra, a Shopee confirma, você recebe. Simples assim. ✅
> #cashback #semmensalidade #shopee

### Dia 7 — `07-quanto-economizar.png`
> Você não precisa mudar nada no seu jeito de comprar — só ganhar mais no final. 📈 Toda compra que você já ia fazer na Shopee pode voltar parte do dinheiro pro seu bolso. 💰
> Comece a economizar sem esforço — link na bio.
> #cashback #economia #shopee #dinheirodevolta

### Dia 8 — `08-cadastre-se.png`
> 🚀 Cadastro grátis, sem custo nenhum. Compra na Shopee do jeito que já compra e começa a receber cashback de verdade.
> 👉 cash-b.com
> #cashback #shopee #cadastrese

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
