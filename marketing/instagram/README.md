# cash-b no Instagram — histórico e decisões

Este arquivo documenta o que já foi decidido e feito pro Instagram do
cash-b (@usecashb), pra qualquer conversa futura conseguir continuar sem
precisar reconstruir esse contexto do zero. Ver também `BRAND.md` na raiz
do repo pra identidade visual geral do site.

## Contexto

O bot (app Django `instagram_bot/`) publica automaticamente no Instagram
(stories diários + posts semanais no feed), usando a Instagram Graph API,
puxando dados reais do site (tabela `Oferta`, ver app `ofertas/`). Ele já
está construído e rodando em modo simulação (`INSTAGRAM_BOT_ATIVO=False`)
enquanto o perfil é "semeado" manualmente com os posts institucionais desta
pasta, pra não ficar vazio quando a automação for ligada de verdade — ver
"Como ligar o bot" abaixo.

## Onde cada coisa mora no código (app `instagram_bot/`)

- `models.py` — `RegistroPublicacao`: log de cada publicação (real ou
  simulada), visível no Django Admin.
- `conteudo.py` — bancos de texto (`DICAS`, `LEMBRETES`,
  `POSTS_INSTITUCIONAIS`) e a função que decide o que publicar em cada dia
  da semana.
- `templates_imagem.py` — geração de imagem via Pillow.
- `instagram_client.py` — chamadas à Instagram Graph API
  (`graph.instagram.com`).
- `services.py` — orquestração: decide o que falta publicar hoje, gera a
  imagem, salva em `MEDIA_ROOT`, publica (ou simula) e registra o resultado.
  Chamado a partir de `cashback_shopee/views.py` (`executar_tarefas_agendadas`,
  o mesmo endereço `/tarefas/executar/` que já roda a sincronização diária).

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
   - **Stories**: seg–sex, `NUMERO_STORIES_OFERTAS_POR_DIA` (5) stories de
     oferta espalhados ao longo do dia (cron dedicado,
     `.github/workflows/stories-oferta.yml`, chama
     `/tarefas/postar-story-oferta/` várias vezes ao dia) - 1 oferta por
     story, 1 categoria (nível 1) diferente por vez, entre as categorias
     mais vendidas, sem repetir produto (mesmo nome vindo de lojas
     diferentes conta como repetido - ver `ofertas/services.py`,
     `selecionar_top_ofertas_sem_duplicar`/`categorias_mais_vendidas`, e
     `instagram_bot/services.py`, `publicar_story_oferta_do_momento`). De
     propósito **não** é 1 story só com várias ofertas juntas: o perfil
     não é só sobre ofertas, então evita "bombardear" o feed de stories.
     Sábado dica de economia (rotativo); domingo lembrete de cashback
     (mensagem de marca) - esses dois continuam na tarefa diária única.
   - **Posts no feed (2x por semana)**: quarta = post institucional
     (benefícios, curiosidades, como funciona, como usar); sexta = resumo
     das melhores ofertas da semana.
2.5. **Semear o perfil (manual, antes do bot)** — ✅ concluído (esta pasta).
   8 posts institucionais criados e aprovados pra postar manualmente antes
   de ligar a automação, pra o perfil não começar vazio. **Em andamento**:
   você está postando esses 8 manualmente aos poucos (ver cronograma acima).
3. **Templates de imagem parametrizados** — ✅ concluído. App Django
   `instagram_bot/`, módulo `templates_imagem.py`: gera as imagens via
   **Pillow** (não Playwright/Chromium — mais leve pro plano gratuito da
   Render, testado e as fontes `.woff2` funcionam direto nele, inclusive os
   eixos de peso variável Bold/Regular). Dois layouts:
   - `gerar_imagem_texto_simples(...)` — statement centralizado (dica,
     lembrete), reaproveita o layout dos posts de semeadura.
   - `gerar_imagem_oferta_story(...)` — layout "hero" pra 1 oferta só
     ocupando o story inteiro (imagem grande + nome + preço + selo de
     desconto, no estilo do cartão de oferta do site), busca a imagem do
     produto via `requests` a partir de `Oferta.imagem_url`. Reserva
     margem de segurança no topo e no rodapé pra não ficar atrás do
     ícone/nome da conta nem da barra de resposta do próprio Instagram
     (ver "Ajuste de layout do story de oferta" no troubleshooting).
   Os posts institucionais de quarta-feira usam os mesmos 8 temas da
   semeadura, mas **geram uma arte nova via Pillow a cada rotação** (2
   variações de texto/legenda por tema, 16 no total) em vez de reusar os
   PNGs de `posts-semeadura/` - assim o bot não republica pro mesmo público
   exatamente a mesma arte que já foi postada na mão (ver `conteudo.py`,
   banco `POSTS_INSTITUCIONAIS`). Os PNGs de semeadura continuam guardados
   como histórico da marca, só não são mais usados pelo bot.
   O post semanal de ofertas (sexta) é um **carrossel**: uma capa +
   8 ofertas (uma por slide) - carrossel tende a gerar mais salvamento que
   um post único, o que ajuda o alcance mesmo pra quem não segue a conta.
4. **Integração com a API do Instagram** — ✅ concluído.
   `instagram_bot/instagram_client.py` fala com `graph.instagram.com`
   (host certo pro fluxo "Login do Instagram", sem Página do Facebook):
   cria o container de mídia, publica, e tem uma função de renovar o
   token de longa duração (`renovar_token_de_longa_duracao`, ainda não
   chamada automaticamente — ver nota sobre renovação de token abaixo).
   As imagens geradas são salvas em `MEDIA_ROOT` e servidas publicamente
   em `/media/instagram/...` (a API do Instagram busca a imagem sozinha a
   partir de uma URL pública, não aceita upload direto).
5. **Agendamento** — ✅ concluído. Reaproveita a mesma tarefa diária que já
   existia (`/tarefas/executar/`, chamada pelo GitHub Actions) — não foi
   criado nenhum agendamento novo. `instagram_bot/conteudo.py` decide o
   que publicar hoje a partir do dia da semana.
6. **Modo de revisão** — ✅ concluído, é o estado atual. Interruptor
   `INSTAGRAM_BOT_ATIVO` (variável de ambiente, `False` por padrão):
   enquanto `False`, o bot gera a imagem, salva em `RegistroPublicacao`
   com `modo_simulacao=True`, mas **não chama a API de verdade**. Ver
   "Como ligar o bot" abaixo.
6.1. **Aprovação por e-mail** — ✅ concluído. Além do interruptor mestre,
   tem `INSTAGRAM_REQUER_APROVACAO` (`True` por padrão). Com o bot ligado
   e essa variável em `True`, cada story/post gerado fica com
   `status=pendente_aprovacao` e dispara um e-mail (via
   `instagram_bot/aprovacao.py`) pro endereço em `INSTAGRAM_APROVADOR_EMAIL`,
   com a imagem anexada, a legenda, e dois links ("Aprovar e publicar" /
   "Rejeitar"). Cada link tem um token assinado (mesmo esquema do e-mail
   de confirmação de cadastro, `accounts/tokens.py`) que expira em 36h.
   Clicar em "Aprovar" chama a API do Instagram na hora; clicar em
   "Rejeitar" só marca `status=rejeitado` e não publica nada. Com
   `INSTAGRAM_REQUER_APROVACAO=False`, publica direto, sem passar por
   aprovação (fluxo antigo).
7. **Monitoramento** — ✅ concluído. Toda publicação (real ou simulada)
   vira uma linha em `RegistroPublicacao`, visível no Django Admin
   (`/admin/instagram_bot/registropublicacao/`) — mostra sucesso/erro,
   se foi simulação, a legenda e a URL da imagem gerada.

## Como ligar o bot

O bot já está pronto e rodando em modo simulação (não publica de verdade,
só registra o que faria). Quando terminar de postar os 8 posts de
semeadura manualmente:

1. No Render, vá em **Environment** e adiciona/edita `INSTAGRAM_BOT_ATIVO=True`.
2. Também defina `INSTAGRAM_APROVADOR_EMAIL` (seu e-mail) - é pra onde vai
   o pedido de aprovação de cada story/post.
3. `INSTAGRAM_REQUER_APROVACAO` já vem `True` por padrão, então a partir
   da próxima execução da tarefa diária, cada conteúdo gerado chega no seu
   e-mail (imagem anexada + legenda) com um link de "Aprovar e publicar" e
   um de "Rejeitar" - só publica no Instagram (`usecashb`) depois que você
   clicar em aprovar. Se preferir publicar direto sem revisar, defina
   `INSTAGRAM_REQUER_APROVACAO=False`.
4. Confere pelo Django Admin (`RegistroPublicacao`) o status de cada
   publicação (`pendente_aprovacao`, `publicado`, `rejeitado`, `erro`).

Pra desligar de novo (ex: se algo sair errado), é só voltar
`INSTAGRAM_BOT_ATIVO=False` — sem precisar mexer em código nenhum.

## Renovação do token de acesso (manual por enquanto)

O access token do Instagram dura 60 dias. `instagram_client.py` já tem a
função `renovar_token_de_longa_duracao()` pronta, mas ela **não é chamada
automaticamente** — automatizar isso exigiria o app conseguir escrever a
variável de ambiente `INSTAGRAM_ACCESS_TOKEN` no Render sozinho (precisaria
de uma chave de API do Render, mais uma credencial sensível pra gerenciar),
e expor o valor novo do token nos logs seria um risco de segurança. Por
enquanto, o processo é manual: antes dos 60 dias vencerem, repetir o passo
"Gerar token" no painel da Meta (ver Fase 1 acima) e atualizar
`INSTAGRAM_ACCESS_TOKEN` no Render.

**Lembrete automático (✅ concluído)**: `instagram_bot/lembrete_token.py`
roda junto da tarefa diária (`executar_tarefas_agendadas`) e manda um
e-mail pro `INSTAGRAM_APROVADOR_EMAIL` quando faltarem 10 dias ou menos
pro token vencer (repete a cada 3 dias até renovar, pra não deixar passar
batido). O controle de quando o token foi renovado pela última vez fica no
model `EstadoTokenInstagram` (Django Admin, `instagram_bot`) — depois de
gerar e atualizar o token novo no Render, é só abrir esse registro no
Admin e rodar a ação "Marcar token como renovado hoje" (senão o lembrete
continua chegando).

## Automação de comentários e DM

Virou um app à parte (`automacao_instagram/`), com seu próprio histórico de
decisões — ver `automacao_instagram/README.md`. Só pra registrar aqui a
separação: `instagram_bot/` publica conteúdo (stories/posts do calendário),
`automacao_instagram/` reage a comentários (responde/manda DM) - são apps
independentes, cada um com seu próprio token/conta configurável.

## Troubleshooting (incidentes já resolvidos)

Histórico de problemas reais encontrados ao ligar o bot de publicação de
verdade pela primeira vez (2026-08-05) - registrado aqui pra não perder
tempo reinvestigando algo parecido no futuro.

### "Only photo or video can be accepted as media type" ao aprovar/publicar

Apareceu na primeira publicação real (story e post no feed, os dois com o
mesmo erro). Investigação eliminou, nessa ordem, until achar a causa real:

1. **Formato da arte** — o bot salvava em PNG; a Instagram Graph API só
   aceita JPEG. Corrigido (`instagram_bot/services.py` agora salva/serve
   sempre `.jpg`) - mas não era a causa raiz sozinha, o erro continuou.
2. **Domínio da URL da imagem** — a URL usava o domínio de quem
   disparava a publicação (`cash-b.com`, atrás de Cloudflare) em vez do
   endereço direto do Render. Corrigido pra sempre usar
   `RENDER_EXTERNAL_HOSTNAME` (bypassa qualquer proxy/CDN na frente do
   domínio customizado) - também não era a causa raiz, mas é mais robusto
   deixar assim de qualquer forma.
3. **Causa raiz real**: `INSTAGRAM_BUSINESS_ACCOUNT_ID` no Render estava
   com o ID errado (não era o mesmo ID associado ao
   `INSTAGRAM_ACCESS_TOKEN`) - publicar num ig-user-id que não bate com o
   token gera esse erro genérico de mídia, em vez de um erro claro de
   permissão. Conferido e corrigido usando o **Depurador de Token de
   Acesso** (link abaixo): o campo "ID do usuário no escopo do
   aplicativo" mostra o ID de verdade associado ao token.

**Ferramentas de diagnóstico que ajudaram** (guarda esse link, vale a pena
pra qualquer erro parecido no futuro):
- **Depurador de Compartilhamento** —
  `https://developers.facebook.com/tools/debug/sharing/?q=<URL>` — mostra
  exatamente o que o rastreador da Meta vê ao buscar uma URL (código de
  resposta, dimensões da imagem, hash). Prova se o problema é de
  alcançabilidade/formato ou não.
- **Depurador de Token de Acesso** —
  `https://developers.facebook.com/tools/debug/accesstoken/` — cola o
  access token e mostra ID do usuário/conta associado, escopos
  concedidos, validade e expiração. É o jeito mais rápido de conferir se
  `INSTAGRAM_BUSINESS_ACCOUNT_ID` bate com o token de verdade.

**Melhorias que ficaram** dessa investigação (valem independente do bug
específico):
- `instagram_client._chamar()` agora inclui `code`/`error_subcode`/`type`/
  `fbtrace_id` na mensagem de erro, não só o texto genérico da Meta -
  esses códigos numéricos ajudam bem mais a identificar a causa real do
  que a mensagem sozinha (que costuma ser genérica e cobrir várias causas
  diferentes).
- Ação **"Tentar publicar de novo"** no Django Admin
  (`RegistroPublicacao`) - reprocessa um registro com status Erro
  (reconverte a arte pra JPEG se ainda estiver em PNG) sem precisar de
  código nem estar no computador (funciona pelo navegador do celular).

### Erro genérico "code=2, An unexpected error has occurred. Please retry your request later."

Pode aparecer mesmo com tudo certo (token válido, ID certo, formato
certo) - é o erro transitório genérico da própria Meta. Costuma resolver
sozinho numa nova tentativa depois de um tempo; se persistir por várias
tentativas seguidas, pode ser as próprias tentativas repetidas
disparando alguma proteção temporária do lado da Meta - nesse caso, é
melhor esperar mais (a próxima execução automática do dia seguinte, por
exemplo) em vez de insistir.

**Atualização (ver incidente abaixo, 2026-08-07)**: esse mesmo erro
genérico também pode ser só `INSTAGRAM_BUSINESS_ACCOUNT_ID` errado de
novo - não é só instabilidade transitória da Meta. Antes de esperar,
confere primeiro no Depurador de Token de Acesso.

### `INSTAGRAM_BUSINESS_ACCOUNT_ID` errado de novo, mascarado como erro genérico (2026-08-07)

Um dia depois do incidente acima (2026-08-05), o bot voltou a falhar -
dessa vez em **todas** as execuções automáticas do dia (várias chamadas
distintas, `fbtrace_id` diferente em cada uma), com a mensagem genérica
"code=2, type=OAuthException" (não o erro claro de mídia de antes).
Pareceu, a princípio, o caso "instabilidade transitória da Meta" descrito
acima - mas persistir o dia inteiro, em chamadas independentes, não bate
com esse padrão.

**Causa raiz**: `INSTAGRAM_BUSINESS_ACCOUNT_ID` no Render tinha sido
corrigido errado no incidente anterior - `271062287872382357` em vez de
`271062878872382357` (dois dígitos trocados de posição no meio do
número). Confirmado comparando com o "ID do usuário no escopo do
aplicativo" no Depurador de Token de Acesso. Ou seja: o mesmo tipo de
erro (ID incorreto) pode aparecer tanto como o erro claro de mídia
("Only photo or video...") quanto como esse erro genérico de OAuth -
depende de qual validação a API do Instagram bate primeiro.

**Melhoria que ficou**: `instagram_client.verificar_configuracao()` -
antes de qualquer publicação real (`publicar_imagem`/`publicar_carrossel`,
chamadas tanto pelo fluxo normal quanto por "Tentar publicar de novo"),
compara o `INSTAGRAM_BUSINESS_ACCOUNT_ID` configurado com o ID retornado
por uma chamada `GET /me` usando o próprio `INSTAGRAM_ACCESS_TOKEN`. Se
não bater, falha com uma mensagem específica e direta (ID configurado x
ID esperado) em vez de deixar a Meta devolver um erro genérico que
mascara a causa - da próxima vez que os dois valores ficarem
dessincronizados, o campo `erro` do `RegistroPublicacao` já vai apontar
exatamente isso, sem precisar repetir essa investigação inteira.

### Erro "code=9004, error_subcode=2207052" (media could not be fetched) - self-deadlock de 1 worker só (2026-08-07)

Depois de corrigir o `INSTAGRAM_BUSINESS_ACCOUNT_ID` (incidente acima), a
publicação continuou falhando - agora com "Only photo or video can be
accepted as media type" de novo, mas com `code=9004,
error_subcode=2207052`, que a própria Meta documenta como "a mídia não
pôde ser buscada nessa URI" (fetch da imagem falhou, não é erro de
formato).

**Causa raiz**: o serviço web no Render roda com `gunicorn
cashback_shopee.wsgi:application --timeout 120`, sem `--workers` nem
`--threads` (então cai no padrão: 1 worker síncrono). O fluxo de
publicação faz uma chamada de dentro de uma requisição (aprovar por
e-mail, ou o cron chamando `/tarefas/postar-story-oferta/`) pra API do
Instagram; a API do Instagram, pra criar o container de mídia, busca a
imagem de volta na própria URL pública do site (`RENDER_EXTERNAL_HOSTNAME`)
- ou seja, faz uma requisição de volta pro mesmo servidor. Com 1 worker
só, ele está ocupado esperando a resposta da Meta e não sobra ninguém
pra atender essa busca - a Meta espera, não consegue, e devolve esse
erro. É o mesmo tipo de deadlock que o comentário de
`_reconverter_para_jpeg` (ver acima) já descrevia pra um outro caminho de
código - só que esse aqui pegava o fluxo principal de publicação.

**Correção**: Start Command no Render trocado pra
`gunicorn cashback_shopee.wsgi:application --workers 1 --threads 4 --worker-class gthread --timeout 120`
- `gthread` mantém o mesmo processo (mesmo consumo de memória base), mas
libera até 4 requisições concorrentes dentro dele, então uma thread pode
atender a busca da imagem enquanto a outra espera a resposta da Meta.
Não é uma mudança versionada no repositório (não tem `Procfile` nem
`render.yaml` - o Start Command é só configuração manual no dashboard do
Render, em Settings). Confirmado resolvido: aprovação de story funcionou
e publicou normalmente depois da troca.

### Ajuste de layout do story de oferta do momento (2026-08-07)

Depois da primeira publicação real bem-sucedida, dois problemas visuais
apareceram no layout antigo (`gerar_imagem_ofertas`, pensado pra
empilhar vários cartões pequenos, mas na prática sempre chamado com 1
oferta só pro story):

1. O conteúdo ficava todo colado no topo do story, desperdiçando o resto
   da tela vertical (1080×1920) - sem motivo pra isso quando é só 1
   oferta.
2. A arte começava encostada na borda superior, sem nenhuma margem de
   segurança - o ícone e o nome da conta (UI do próprio Instagram, não
   faz parte da arte) ficavam sobrepostos ao conteúdo.

Substituído por `gerar_imagem_oferta_story(oferta)` (ver "Onde cada coisa
mora no código" acima): layout "hero" de 1 oferta só, no estilo do
cartão de oferta do site (`ofertas/templates/ofertas/lista.html`,
`.oferta-cartao`) - imagem grande, selo de desconto sobre a imagem, nome
e preço em destaque. O bloco inteiro é centralizado dentro de uma área
que já reserva 260px de margem de segurança no topo e no rodapé (onde a
UI do Instagram cobre a arte), em vez de conteúdo fixo colado nas
bordas.

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
