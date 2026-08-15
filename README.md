# cash-b

Site de cashback para compras na Shopee feitas através de links de afiliado gerados pela API oficial da Shopee. Domínio: **cash-b.com**.

> Este README cobre as Fases 1–7 (a base do site). O que veio depois (jurídico/LGPD, conta do usuário, SEO, aba de Ofertas, bot do Instagram) está documentado em [`ROADMAP.md`](ROADMAP.md) e [`BRAND.md`](BRAND.md) — comece por eles se for continuar o projeto numa conversa nova.

## Status do projeto

- ✅ **Fase 1** — Projeto Django rodando, com cadastro e login de usuário (incluindo CPF com validação)
- ✅ **Fase 2** — Geração de link de afiliado Shopee com subID (produto específico ou página inicial)
- ✅ **Fase 3** — Sincronização de pedidos com a Shopee (comando `sincronizar_pedidos`)
- ✅ **Fase 4** — Regra de liberação de saldo, mês da validação + 2 (comando `liberar_saldo`)
- ✅ **Fase 5** — Painel do usuário ("Minha conta"): saldo por status, histórico de pedidos e de links
- ✅ **Fase 6** — Saque de saldo via PIX pela Asaas (sandbox), com aprovação manual no `/admin/`
- ✅ **Fase 7** — Deploy em produção (Render) com tarefas diárias automáticas
- ✅ **Fases 8–11** — jurídico/LGPD, suporte, conta do usuário, polimento técnico — ver [`ROADMAP.md`](ROADMAP.md)
- ⬜ **Fase 12** — crescimento (programa de indicação) — ainda não iniciada

O site está no ar em **https://cash-b.com**.

## Funcionalidades

### Para quem visita e usa o site

- **Página inicial** com explicação de como o cashback funciona, painel de benefícios com animação ao rolar a página, e comparação entre gerar o link de um produto específico (venda direta) ou usar o botão geral (venda indireta).
- **Botão "Ir para a Shopee"** no topo: se você já estiver logado, vai direto pro seu link de afiliado; se não estiver, pede login primeiro e te leva pra Shopee automaticamente depois, sem precisar clicar de novo.
- **Cadastro e login** de usuário, com validação de CPF, confirmação de e-mail (token que expira em 3 dias) e recuperação/troca de senha.
- **Conversor de link de produto**: cole o link de um produto da Shopee (inclusive links curtos `shp.ee`) e receba de volta um link de afiliado rastreado — disponível na própria página inicial.
- **Aba de Ofertas**: catálogo com os produtos mais vendidos da Shopee por categoria, sincronizado diariamente, com busca, ordenação e filtro — cada oferta já sai com o link de afiliado convertido no clique.
- **Painel "Minha conta"**, com:
  - Saldo separado por status: pendente, validado, liberado e cancelado (com explicação de cada um).
  - Histórico de pedidos, saques e links gerados, paginado e filtrável por status/tipo.
  - Edição de dados cadastrais (nome, e-mail, CPF) e troca de senha estando logado.
  - Cadastro da sua chave PIX (CPF, e-mail, telefone ou chave aleatória).
  - Botão pra solicitar saque do saldo liberado (quando atingir o valor mínimo).
- **Páginas institucionais**: Termos de Uso, Política de Privacidade (LGPD), Política de Cookies, Regras do Cashback, FAQ e Fale Conosco (formulário que manda e-mail de verdade).
- **PWA**: dá pra instalar o site como app no celular (Android/iOS).
- **SEO básico**: meta description por página, sitemap.xml e robots.txt.

### Regras de negócio por trás do site

- **Cálculo de cashback**: soma a comissão que a Shopee paga por item comprado (`itemTotalCommission`), aplicando o percentual repassado ao usuário (`SHOPEE_CASHBACK_PERCENTUAL`).
- **Liberação de saldo**: pedidos validados ficam disponíveis pra saque no 1º dia do mês seguinte a dois meses após a validação (ex: validou em março, libera em 1º de maio).
- **Saque via PIX**: o usuário solicita o saque do saldo liberado disponível; a solicitação fica pendente até você aprovar manualmente — só então o sistema chama a Asaas (ou o Inter, em pausa — ver `saques/inter_client.py`) pra pagar de verdade. Valor mínimo configurável (`SAQUE_VALOR_MINIMO`).
- **E-mails automáticos**: usuário recebe e-mail quando um pedido é validado, quando o cashback é liberado e quando um saque é pago.

### Para quem administra o site (você)

Tudo isso fica em `/admin/`:

- Gerenciar usuários, links gerados, pedidos, saques e ofertas.
- Ver o status bruto que a Shopee retornou pra cada pedido (útil pra conferência).
- Aprovar (e pagar de fato via PIX) ou cancelar solicitações de saque, com um clique.
- Acompanhar o motivo de cancelamento de pedidos, quando a Shopee informa.

E por trás dos panos, tarefas rodam sozinhas todo dia (via GitHub Actions, sem custo) pra: sincronizar pedidos com a Shopee, liberar saldo, verificar saques pendentes, sincronizar a aba de Ofertas e (opcionalmente) publicar no Instagram. Também dá pra rodar cada uma manualmente:
```bash
python manage.py sincronizar_pedidos
python manage.py liberar_saldo
python manage.py verificar_saques
```

### Instagram (marketing) — dois apps separados

- **`instagram_bot/`** — publica sozinho no Instagram (@usecashb): stories diários com ofertas e posts semanais no feed, gerados via Pillow com a identidade visual da cash-b. Roda em modo simulação até ser ligado de propósito (`INSTAGRAM_BOT_ATIVO`), com aprovação por e-mail opcional antes de cada publicação. Ver `marketing/instagram/README.md`.
- **`automacao_instagram/`** — ferramenta à parte (não é de marketing da cash-b em si): responde comentários com palavra-chave num post e/ou manda DM automaticamente, com suporte a múltiplas contas/automações e login próprio. Ver `automacao_instagram/README.md`.

## Como rodar localmente

1. Crie e ative o ambiente virtual (só precisa criar uma vez):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Aplique as migrações do banco de dados (cria as tabelas):
   ```bash
   python manage.py migrate
   ```
4. Rode o servidor:
   ```bash
   python manage.py runserver
   ```
5. Acesse no navegador: http://127.0.0.1:8000

Toda vez que for trabalhar no projeto, basta ativar o ambiente virtual (`source venv/bin/activate`) e rodar `python manage.py runserver`.

## Criar um usuário administrador (para acessar /admin/)

```bash
python manage.py createsuperuser
```

## Configurando suas credenciais da API Shopee (Fase 2)

As credenciais nunca ficam no código nem são enviadas ao GitHub — elas moram só no seu computador, num arquivo `.env`.

1. Copie o arquivo de modelo:
   ```bash
   cp .env.example .env
   ```
   (no Windows: `copy .env.example .env`)
2. Abra o `.env` num editor de texto e preencha:
   ```
   SHOPEE_AFFILIATE_APP_ID=seu_app_id_aqui
   SHOPEE_AFFILIATE_SECRET=seu_secret_aqui
   ```
3. Teste se a conexão está funcionando:
   ```bash
   python manage.py testar_shopee
   ```
   - Se aparecer "Sucesso! Link gerado: ...", está tudo certo.
   - Se aparecer um erro vindo da Shopee, copie a mensagem para ajustarmos juntos (pode ser algo simples, como o formato de um campo).
4. Depois disso, é só usar o site normalmente: faça login, vá em "Gerar link de cashback na Shopee" e gere um link de um produto específico ou da página inicial.

## Sincronizando pedidos com a Shopee (Fase 3)

O comando abaixo consulta a Shopee e atualiza o status dos pedidos (pendente/validado/cancelado) e o valor de cashback de cada usuário. Esse é o "job diário" mencionado na ideia original — por enquanto ele precisa ser rodado manualmente; a automação (rodar sozinho todo dia) fica para quando o site estiver hospedado (Fase 7).

```bash
python manage.py sincronizar_pedidos
```

Por padrão ele busca os últimos 60 dias. Para mudar: `python manage.py sincronizar_pedidos --dias 90`.

Você pode conferir os pedidos sincronizados em `/admin/` (seção "Pedidos"), incluindo o valor bruto de status que a Shopee retornou — isso ajuda a ajustar o mapeamento de status caso algum pedido real apareça com um status que ainda não reconhecemos.

O percentual de comissão repassado como cashback ainda não foi definido — está em `SHOPEE_CASHBACK_PERCENTUAL` no `.env` (100 = repassa 100% da comissão que a Shopee paga).

## Liberando o saldo dos pedidos validados (Fase 4)

Pedidos validados ficam disponíveis para saque no 1º dia do mês seguinte a dois meses depois da validação (ex: validou em março, libera em 1º de maio). Para efetivamente mudar o status desses pedidos de "validado" para "liberado":

```bash
python manage.py liberar_saldo
```

Assim como o `sincronizar_pedidos`, por enquanto esse comando precisa ser rodado manualmente (a automação fica pra Fase 7).

## Configurando o pagamento de saques via PIX com a Asaas (Fase 6)

O saque funciona assim: o usuário pede o saque do saldo liberado dentro do site → a solicitação fica pendente → você revisa e aprova no `/admin/` → só então o sistema chama a Asaas pra fazer a transferência PIX de verdade. Nada é pago automaticamente sem sua aprovação.

### 1. Criar a conta sandbox na Asaas

1. Acesse https://www.asaas.com/ e crie uma conta (é gratuito).
2. Ao criar a conta, você já ganha acesso a um ambiente de testes ("sandbox") separado do ambiente real — é nele que vamos trabalhar por enquanto, sem mexer com dinheiro de verdade.
3. Para acessar o sandbox diretamente: https://sandbox.asaas.com/ (o login costuma ser o mesmo da conta que você criou, mas se pedir para criar uma conta específica do sandbox, siga o fluxo indicado na tela).

### 2. Gerar a chave de API

1. Dentro do sandbox, procure por "Integrações" (ou "Configurações" > "Integrações" > "API") no menu.
2. Gere/copie a chave de API. Ela começa com `$aact_hmlg_` (chaves de sandbox sempre começam assim — as de produção começam com `$aact_prod_`, nunca confunda as duas).

### 3. Configurar no projeto

No seu arquivo `.env`:
```
ASAAS_API_KEY=$aact_hmlg_sua_chave_aqui
```
(a `ASAAS_API_URL` já vem configurada por padrão para o sandbox, não precisa mexer.)

### 4. Testar o fluxo

1. Rode `python manage.py migrate` (esse app é novo, tem migração pra aplicar).
2. Na Asaas sandbox, crie uma chave PIX de teste pelo menu "Pix" > "Minhas chaves" (a chave aleatória é a mais rápida de gerar). Você também pode usar uma chave fictícia oficial do Banco Central — veja https://docs.asaas.com/docs/testando-transferencias.
3. Faça login no nosso site, vá em "Minha conta" e cadastre essa chave em "Cadastrar chave PIX" (escolha o tipo certo: E-mail, CPF, Telefone ou Aleatória).
4. Quando tiver saldo liberado (R$ 20,00 ou mais, valor configurável em `SAQUE_VALOR_MINIMO` no `.env`), clique em "Solicitar saque".
5. No `/admin/`, entre em "Saques", marque a solicitação e rode a ação "Aprovar e pagar via PIX (Asaas)".
6. Se der certo, o status muda para "Pago". Se der erro, o status vira "Falhou" e o motivo fica registrado no campo "Resposta asaas" daquele saque — me manda a mensagem que ajusto com você.

Se algum saque ficar muito tempo em "Processando" (raro, mas pode acontecer em processamento bancário), rode `python manage.py verificar_saques` para reconsultar o status na Asaas.

## Colocando o site no ar (Fase 7)

Vamos usar a **Render** (tem plano gratuito) pra hospedar o site, com um banco de dados Postgres (o SQLite que usamos localmente não funciona em produção lá, porque o plano gratuito não guarda arquivos entre reinicializações).

**Sobre o plano gratuito**: o site "dorme" depois de uns 15 minutos sem acesso e demora uns 30-60 segundos pra "acordar" no primeiro acesso seguinte — tranquilo numa fase inicial. O banco de dados gratuito expira 30 dias após ser criado, mas você tem mais 14 dias de prazo pra fazer upgrade sem perder nada (44 dias no total) — a Render avisa por e-mail antes disso acontecer.

**Importante sobre dinheiro real**: depois do deploy, a Shopee continua sendo a de verdade (como já é hoje), mas os saques continuam batendo na Asaas **sandbox** (não gera pagamento real) até você trocar `ASAAS_API_KEY`/`ASAAS_API_URL` pelas credenciais de produção da Asaas — o que é assunto pra quando você decidir abrir o site pra usuários de verdade, não precisa fazer isso agora.

### 1. Criar a conta na Render e o banco de dados

1. Acesse https://render.com/ e crie uma conta (dá pra usar login do GitHub).
2. No painel, clique em **"New +"** → **"PostgreSQL"**.
3. Dê um nome (ex: `cashback-shopee-db`), escolha o plano **Free** e crie.
4. Quando o banco estiver pronto, copie o valor de **"Internal Database URL"** (vamos usar em breve) — não confunda com o "External Database URL" ainda.

### 2. Criar o Web Service

1. No painel, clique em **"New +"** → **"Web Service"**.
2. Conecte sua conta do GitHub (se ainda não conectou) e selecione o repositório `site-cashback-shopee`.
3. Escolha a branch que você quer publicar (a mesma que estamos usando pra desenvolver).
4. Preencha:
   - **Runtime**: Python 3
   - **Build Command**:
     ```
     pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
     ```
   - **Start Command**:
     ```
     gunicorn cashback_shopee.wsgi:application --timeout 120
     ```
     (o `--timeout 120` dá uma margem extra pra sincronizações com muitos pedidos não serem interrompidas no meio.)
   - **Health Check Path**: `/healthz/`
     (sem isso, a Render só confere se a porta abriu antes de trocar pra instância nova
     em cada deploy, o que pode considerá-la "pronta" antes do banco estar de fato
     acessível — os primeiros acessos depois do deploy caem num 502/500 por alguns
     segundos. Com o health check configurado, a Render só desliga a instância antiga
     quando a nova responder 200 de verdade nesse endereço.)
   - **Plan**: Free
5. **Não clique em criar ainda** — antes, desça até "Environment Variables" e configure a próxima seção.

### 3. Configurar as variáveis de ambiente

Adicione cada uma dessas (nomes exatamente iguais aos do seu `.env` local, mas com valores de produção):

| Variável | Valor |
|---|---|
| `DJANGO_SECRET_KEY` | Um texto longo e aleatório (a própria Render tem um botão "Generate" pra isso) |
| `DJANGO_DEBUG` | `False` |
| `DATABASE_URL` | Cole aqui a "Internal Database URL" que você copiou no passo 1 |
| `SHOPEE_AFFILIATE_APP_ID` | O mesmo valor do seu `.env` local |
| `SHOPEE_AFFILIATE_SECRET` | O mesmo valor do seu `.env` local |
| `SHOPEE_CASHBACK_PERCENTUAL` | O mesmo valor do seu `.env` local |
| `ASAAS_API_KEY` | O mesmo valor do seu `.env` local (ainda o de sandbox) |
| `SAQUE_VALOR_MINIMO` | O mesmo valor do seu `.env` local |
| `TAREFAS_TOKEN` | Um texto longo e aleatório, só seu (não precisa ser igual a nenhum outro) — vamos usar no passo 5 |

Não precisa configurar `DJANGO_ALLOWED_HOSTS` — a Render já informa o endereço do site automaticamente pro Django através de uma variável própria dela.

Agora sim, clique em **"Create Web Service"**. A Render vai buildar e publicar o site — acompanhe o log; o primeiro deploy demora alguns minutos.

### 4. Criar seu usuário administrador

O plano gratuito não dá acesso a um terminal dentro da Render, então vamos criar o superusuário conectando do seu computador direto no banco de produção, só uma vez:

1. Na página do banco de dados na Render, copie agora o **"External Database URL"** (esse sim, diferente do interno).
2. No terminal do seu computador (com o `venv` ativado), rode, substituindo pela URL copiada:

   PowerShell:
   ```
   $env:DATABASE_URL="cole_a_external_database_url_aqui"
   python manage.py createsuperuser
   ```
   Cmd:
   ```
   set DATABASE_URL=cole_a_external_database_url_aqui
   python manage.py createsuperuser
   ```
3. Preencha usuário, e-mail e senha normalmente.
4. Feche esse terminal (ou abra um novo) depois — isso evita continuar usando o banco de produção sem querer nos próximos comandos locais.

### 5. Automatizar as tarefas diárias (sincronizar pedidos, liberar saldo, verificar saques)

Criei um endereço protegido por senha no site, `/tarefas/executar/`, que roda as três tarefas de uma vez. Ele só funciona se receber o `TAREFAS_TOKEN` certo:

```
https://seusite.onrender.com/tarefas/executar/?token=SEU_TAREFAS_TOKEN_AQUI
```

Já deixei configurado um agendamento gratuito no GitHub Actions (`.github/workflows/tarefas-diarias.yml`) pra acessar esse endereço todo dia às 03:00 (horário de Brasília) - de madrugada de propósito, já que essa tarefa mexe com saldo e saques de gente de verdade. Falta só você configurar o segredo com a URL completa:

1. No GitHub, abra o repositório → **Settings** → **Secrets and variables** → **Actions**.
2. Clique em **"New repository secret"**.
3. Nome: `TAREFAS_URL`
4. Valor: a URL completa de cima, com o seu endereço da Render e o `TAREFAS_TOKEN` que você configurou no passo 3.
5. Salve.

Pra testar sem esperar até de madrugada: vá em **Actions** (no menu do repositório) → **"Tarefas diárias do site"** → **"Run workflow"** → confirme. Se ficar verde, funcionou; se ficar vermelho, clique no resultado pra ver a mensagem de erro.

As publicações diárias do Instagram (opcional, ver Fase 12) usam o mesmo segredo `TAREFAS_URL`, mas rodam num workflow separado (`.github/workflows/instagram-diario.yml`) às 11:00 (horário de Brasília) - horário de bom alcance, diferente da tarefa acima que roda de madrugada de propósito.

### 6. Conferir se está tudo certo

Acesse `https://seusite.onrender.com` (ou o endereço que a Render te deu) e teste: cadastro/login, gerar link, `/admin/` com o superusuário criado no passo 4.

## Estrutura do projeto

- `cashback_shopee/` — configurações gerais do site (settings, urls)
- `accounts/` — cadastro, login, dados do usuário (CPF, chave PIX) e o painel "Minha conta"
- `links/` — geração de links de afiliado Shopee com subID (API oficial) e a página inicial
- `pedidos/` — sincronização de pedidos/comissões com a Shopee e liberação de saldo
- `saques/` — solicitação e pagamento de saques via PIX pela Asaas
