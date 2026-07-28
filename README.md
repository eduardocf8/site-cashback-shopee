# Cashback Shopee

Site de cashback para compras na Shopee feitas através de links de afiliado gerados pela API oficial da Shopee.

## Status do projeto

- ✅ **Fase 1** — Projeto Django rodando, com cadastro e login de usuário (incluindo CPF com validação)
- ⬜ Fase 2 — Geração de link de afiliado Shopee com subID
- ⬜ Fase 3 — Sincronização diária de status de pedidos
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

## Estrutura do projeto

- `cashback_shopee/` — configurações gerais do site (settings, urls)
- `accounts/` — cadastro, login e dados do usuário (CPF, etc.)
