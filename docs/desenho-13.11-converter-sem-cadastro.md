# Desenho técnico — 13.11 "Usar a cash-b sem cadastro"

Rascunho de 18/10/2026, pra estar pronto antes da decisão de 24/10 (7 dias de dados do
funil, de 17/10 a 23/10). Nada aqui está implementado ainda.

## Resumo

Hoje, quem não tem conta e clica numa oferta (ou no "Ir pra Shopee", no link de story, ou
no conversor) é mandado pro cadastro. Nos primeiros dados, ninguém dessas pessoas se
cadastrou, e sem cadastro não existe link de afiliado: **a cash-b não ganha a comissão
dessa compra**.

A proposta: deixar a pessoa ir pra Shopee **com o link de afiliado da cash-b mesmo sem
conta**. A comissão passa a entrar sempre. O cashback continua exigindo conta: ele fica
"guardado" no navegador e é ligado à conta se a pessoa se cadastrar (ou entrar) em até
30 dias. Se ela nunca se cadastrar, a comissão inteira fica com a cash-b.

É o que a Méliuz faz (benchmark de 16/10, ROADMAP Fase 13).

## Decisões que são do dono

1. **Tela-ponte ou ida direta?** Recomendo a **tela-ponte**: quem não tem conta vê uma
   tela rápida "Ative seu cashback de X%" com o botão **Continuar com Google** (1 clique)
   em destaque e, embaixo, **Ir pra Shopee sem cadastro**. Quem escolhe ir sem cadastro
   ainda pode receber o cashback depois (regra dos 30 dias). A ida direta (sem tela) ganha
   alguns cliques a mais, mas quase ninguém cria conta depois. A tela-ponte também resolve
   parte do problema do navegador do Instagram, porque a conta é criada **antes** da
   compra, no mesmo navegador.
2. **Prazo pra ligar a compra à conta:** 30 dias a partir do clique (sugestão).
3. **Compra feita sem conta e nunca ligada:** a comissão fica inteira com a cash-b. Isso
   precisa estar escrito nos Termos de Uso.
4. **Por onde começar:** pelas **ofertas** (onde vieram 100% das tentativas), depois
   "Ir pra Shopee" e story, e por último o conversor (que mostra o link na tela, então é
   o mais fácil de abusar).

## Como funciona (fluxo)

```
Visitante sem conta clica numa oferta
  └─ é robô (prévia de link, buscador)? → manda direto pra página do produto, sem gerar
     link nem gastar chamada da API da Shopee
  └─ tela-ponte "Ative seu cashback"
       ├─ Continuar com Google / Criar conta → fluxo atual (já volta pra oferta logado)
       └─ Ir sem cadastro
            ├─ cria um cookie "cashb_visitante" (id aleatório, 30 dias) se não existir
            ├─ gera um Click SEM usuário, com esse id de visitante
            │   subIds da Shopee: "anon" + id do clique (o id do clique é o que a
            │   sincronização usa pra achar o clique, então nada muda lá)
            └─ redireciona pra Shopee com o link de afiliado da cash-b

Dias depois, a Shopee reporta a compra
  └─ a sincronização acha o Click pelo id → Pedido com click e SEM usuário
     (cashback calculado normalmente, mas não aparece pra ninguém e não entra no saldo)

Se a pessoa se cadastrar OU entrar na conta (em até 30 dias, no mesmo navegador)
  └─ todos os cliques sem usuário com o mesmo id de visitante passam pra ela,
     e os pedidos desses cliques também → aparecem em "Meus pedidos" com o cashback
  └─ se ela trocou de navegador (ex.: clicou no Instagram e se cadastrou no Safari):
     o formulário "Compra não apareceu?" (Fase 64) cobre: o pedido existe e não tem dono,
     o admin vincula com 1 clique
```

## Mudanças no código

### Modelo (`links/models.py`, migração)

- `Click.usuario`: passa a aceitar vazio (`null=True, blank=True`).
- `Click.visitante_id` (novo, 32 caracteres, com índice): o id do cookie do visitante.
- `Click.vinculado_em` (novo, data/hora, vazio): quando o clique anônimo foi ligado a
  uma conta. Serve pra medir quantos se cadastram depois.
- `Click.sub_id_usuario()`: devolve `"anon"` quando não há usuário. A Shopee só aceita
  letras e números, e "anon" passa.
- `__str__`: tratar usuário vazio.

### Cookie do visitante (`links/visitante.py`, novo)

- `obter_ou_criar_visitante(request, response)`: lê ou cria o cookie
  `cashb_visitante` (token aleatório, 30 dias, HttpOnly, SameSite=Lax, Secure). É
  separado da sessão de propósito, porque a sessão é recriada no login e expira
  diferente.
- É um cookie **necessário pro serviço** (liga a compra ao cashback que a pessoa pediu),
  não de publicidade. Por isso não depende do banner de consentimento, mas precisa
  aparecer na Política de Cookies.

### Gerar o clique (`links/services.py::gerar_click`)

- Aceita `usuario=None` + `visitante_id`. O resto (item_id_alvo, link curto) não muda.
- **Reaproveitar clique:** o mesmo visitante clicando de novo na mesma oferta em até 24h
  reusa o Click anterior, sem nova chamada à API da Shopee.
- **Limite por IP** pra cliques anônimos (ex.: 20 por hora, com `accounts/ratelimit.py`).
  Cada clique chama a API da Shopee, e um robô que passasse pelo filtro gastaria o
  limite dela.

### Telas de entrada

- `accounts/funil.py::exigir_login_medindo` ganha um modo "ponte": em vez de
  redirecionar pro cadastro, mostra a tela-ponte (template novo
  `links/ponte_cashback.html`) com o cashback estimado da oferta (já existe o cálculo
  usado nos cards).
- Rota nova `links/ir-sem-cadastro/` (POST, com CSRF, não GET), que recebe qual oferta
  ou link e faz o fluxo anônimo. Ser POST evita que robôs e prévias de link gerem
  cliques só por abrir a URL.
- Aplicar em `ofertas/views.py` (3 rotas de oferta) e depois `links/views.py::ir_para_shopee`
  e `instagram_bot/views.py::ir_para_story_de_oferta`.
- Conversor (`links/views.py::home`): última fase. Mostra o link pra quem não tem conta
  com o aviso "Crie sua conta em até 30 dias pra receber o cashback desta compra".

### Ligar os cliques à conta (`links/visitante.py::vincular_cliques_do_visitante`)

- Roda no sinal `user_logged_in` do Django. Ele dispara no cadastro por formulário, no
  Google e no login comum, então cobre também quem já tinha conta mas estava deslogado.
- Faz, numa transação:
  - `Click` sem usuário, com o mesmo `visitante_id`, de no máximo 30 dias →
    `usuario = pessoa`, `vinculado_em = agora`;
  - `Pedido` desses cliques ainda sem usuário → `usuario = pessoa`. O valor do cashback
    já está calculado, porque a sincronização calcula quando há clique. A sincronização
    seguinte mantém o vínculo sozinha, porque o usuário agora vem do próprio clique.
- Mensagem pra pessoa: "Encontramos X compra(s) feitas antes do cadastro; o cashback já
  está em Meus pedidos".

### Sincronização (`pedidos/services.py`)

Quase nada muda, porque o clique é encontrado pelo id, com ou sem usuário:

- `_montar_defaults`: com clique anônimo, `usuario` fica vazio (já é assim:
  `click.usuario`). O cashback é calculado, mas não conta pra ninguém (`CASHBACK_REAL` no
  analytics já zera pedido sem usuário).
- Avisos de pedido validado e bônus de indicação: já ignoram pedido sem usuário. Conferir
  com teste.
- Limitação aceitável: se o pedido já estava validado quando a pessoa se cadastrar, ela
  não recebe o e-mail de "pedido validado" nem o bônus de indicação naquele pedido (mesma
  regra da Fase 64).

### Reclamação de compra (`pedidos/reclamacoes.py`, Fase 64)

- Hoje `vincular` recusa pedido com clique. Passa a aceitar clique **sem usuário** e, ao
  vincular, também preenche `click.usuario`. Isso cobre quem clicou no navegador do
  Instagram e se cadastrou em outro.

### Outros pontos que leem `click.usuario` (revisar com teste)

- `pedidos/analytics.py` e `pedidos/admin.py`: separar "anônimo nunca vinculado" na
  origem. O "Gerados no site" continua contando por clique, mas o analytics precisa
  mostrar a comissão de compras anônimas como receita pura.
- `paginas/prova_social.py`: "compras com cashback" deve contar só pedido com usuário.
- `accounts/comunicacoes.py`, `accounts/management/commands/funil_cadastros.py`,
  `pedidos/management/commands/simular_campanha.py`, admin de Click: tratar usuário
  vazio.
- Meta Pixel/CAPI: o evento "GerouLinkCashback" do clique anônimo só sai com
  consentimento (já é a regra do `enviar_evento`).

### Medição (`accounts/funil.py` e Analytics)

- Etapas novas no `EventoFunil`: **foi_sem_cadastro** (clicou em "Ir sem cadastro") e
  **vinculou** (cliques anônimos ligados à conta depois).
- Cards novos no Analytics:
  - cliques anônimos por dia;
  - compras de cliques anônimos;
  - comissão de compras anônimas nunca vinculadas (receita que antes não existia);
  - % de quem foi sem cadastro e se cadastrou em 30 dias.

### Textos e documentos legais

- **Termos de Uso:** compra feita sem conta só gera cashback se a conta for criada ou
  acessada em até 30 dias, no mesmo navegador, ou se o pedido for informado em "Compra
  não apareceu?". Depois disso, a comissão fica com a cash-b.
- **Política de Cookies e Privacidade:** cookie `cashb_visitante` (necessário, 30 dias, id
  aleatório, sem dado pessoal).
- **FAQ:** "Preciso ter conta pra usar?".
- Seguir o VOZ.md: sem "toda compra", porque categorias sem comissão não dão cashback.

## Riscos e como ficam cobertos

| Risco | Cobertura |
|---|---|
| Robôs gerando cliques e gastando a API da Shopee | Ida sem cadastro só por POST, filtro de robôs, limite por IP, reaproveitar clique de 24h |
| Navegador do Instagram perde o cookie | Tela-ponte (conta criada antes da compra) + "Compra não apareceu?" |
| Pessoa reclama do cashback de uma compra sem conta | Regra dos 30 dias nos Termos e na própria tela-ponte |
| Quebrar quem já usa logado | Fluxo de quem está logado não muda; tudo atrás de uma chave `CONVERTER_SEM_CADASTRO` nas variáveis do Render (liga e desliga sem deploy) |
| Contas de teste/fraude pra pegar cashback de compras alheias | O vínculo exige o mesmo cookie (mesmo navegador); pela reclamação, o admin aprova um por um |

## Ordem de entrega (cada item = 1 PR, com merge separado)

1. **Base, invisível:** modelo + migração, `gerar_click` anônimo, cookie, vínculo no
   login, sincronização e reclamação aceitando clique anônimo, chave desligada. Com testes.
2. **Ofertas com tela-ponte** (chave ligada) + medição nova + Termos/Cookies/FAQ.
3. **"Ir pra Shopee" e link de story** com a mesma tela-ponte.
4. **Conversor sem cadastro**, se os números do item 2 forem bons.

Estimativa: o PR 1 é o maior (cerca de 1 sessão de trabalho, com testes). Os PRs 2 a 4
são menores. Com aprovação em 24/10, as ofertas podem estar no ar em poucos dias.

## Como saber se deu certo (1 a 2 semanas depois do PR 2)

- Comissão vinda de cliques anônimos (dinheiro que antes era zero).
- Cadastros totais **não caem**: a tela-ponte continua oferecendo o Google em destaque.
- % de quem foi sem cadastro e se cadastrou depois.
