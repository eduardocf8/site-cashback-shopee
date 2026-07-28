# Cashback Shopee

Site de cashback para compras na Shopee feitas através de links de afiliado gerados pela API oficial da Shopee.

## Status do projeto

- ✅ **Fase 1** — Projeto Django rodando, com cadastro e login de usuário (incluindo CPF com validação)
- ✅ **Fase 2** — Geração de link de afiliado Shopee com subID (produto específico ou página inicial)
- ✅ **Fase 3** — Sincronização de pedidos com a Shopee (comando `sincronizar_pedidos`)
- ⬜ Fase 4 — Regra de liberação de saldo (mês N+2)
- ⬜ Fase 5 — Painel do usuário (extrato e saldo)
- ⬜ Fase 6 — Pagamento via PIX (Asaas)
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

## Estrutura do projeto

- `cashback_shopee/` — configurações gerais do site (settings, urls)
- `accounts/` — cadastro, login e dados do usuário (CPF, etc.)
- `links/` — geração de links de afiliado Shopee com subID (API oficial)
- `pedidos/` — sincronização de pedidos/comissões com a Shopee
