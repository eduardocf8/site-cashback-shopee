# Cashback Shopee

Site de cashback para compras na Shopee feitas através de links de afiliado gerados pela API oficial da Shopee.

## Status do projeto

- ✅ **Fase 1** — Projeto Django rodando, com cadastro e login de usuário (incluindo CPF com validação)
- ✅ **Fase 2** — Geração de link de afiliado Shopee com subID (produto específico ou página inicial)
- ✅ **Fase 3** — Sincronização de pedidos com a Shopee (comando `sincronizar_pedidos`)
- ✅ **Fase 4** — Regra de liberação de saldo, mês da validação + 2 (comando `liberar_saldo`)
- ✅ **Fase 5** — Painel do usuário ("Minha conta"): saldo por status, histórico de pedidos e de links
- ✅ **Fase 6** — Saque de saldo via PIX pela Asaas (sandbox), com aprovação manual no `/admin/`
- ⬜ Fase 7 — Deploy em produção

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

## Estrutura do projeto

- `cashback_shopee/` — configurações gerais do site (settings, urls)
- `accounts/` — cadastro, login, dados do usuário (CPF, chave PIX) e o painel "Minha conta"
- `links/` — geração de links de afiliado Shopee com subID (API oficial) e a página inicial
- `pedidos/` — sincronização de pedidos/comissões com a Shopee e liberação de saldo
- `saques/` — solicitação e pagamento de saques via PIX pela Asaas
