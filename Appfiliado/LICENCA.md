# Licença (assinatura) do bot

O bot é um arquivo baixado que roda offline no computador de quem compra -
diferente de um curso hospedado numa plataforma (Hotmart, Kiwify etc.), a
própria plataforma de pagamento **não tem como desligar o bot sozinha**
quando alguém cancela a assinatura ou o pagamento falha. Por isso o bot
consulta, periodicamente, um servidor próprio que sabe (através dos
webhooks recebidos da plataforma de pagamento) se aquela chave ainda está
com a assinatura em dia.

Essa pasta (`Appfiliado`) já tem o lado do **bot**
pronto: tela de ativação, checagem periódica enquanto o app está aberto, e
tolerância de alguns dias offline. Falta implementar o **servidor** que o
bot consulta - o que está descrito abaixo.

## O que o bot espera do servidor

Endpoint único, configurado em `settings.licenca_servidor_url`:

```
POST {licenca_servidor_url}
Content-Type: application/json

{"chave": "ABC123..."}
```

Resposta esperada (HTTP 200), em JSON:

```json
{
  "valido": true,
  "motivo": "",
  "plano": "mensal",
  "expira_em": "2026-11-25"
}
```

- `valido` (obrigatório): `true` se a assinatura dessa chave está em dia,
  `false` caso contrário (cancelada, pagamento atrasado, chave que nunca
  existiu, etc.).
- `motivo` (opcional, mas recomendado quando `valido` é `false`): texto
  legível que o bot mostra pro usuário (ex: "Assinatura cancelada em
  20/09/2026." ou "Chave de licença não encontrada.").
- `plano` e `expira_em` (opcionais): só usados para guardar no cache local
  e podem ficar vazios.

Se o servidor responder com um erro HTTP (4xx/5xx), o bot tenta ler
`motivo` do corpo da resposta (se vier em JSON) e trata como "licença
inválida" - **não** como falha de conexão, então não entra na tolerância
offline. Só é tratado como falha de conexão (e cai na tolerância offline)
quando o bot realmente não conseguir nem chegar ao servidor (sem internet,
timeout, DNS, etc.).

## Backend: já implementado (app `licencas`, projeto Django da cash-b)

O backend mora no mesmo projeto Django do site principal (`site-cashback-shopee`),
num app separado chamado `licencas` - só reaproveita a infraestrutura já paga
(hospedagem, banco, envio de email), o Appfiliado continua sem nenhuma marca ou
menção à cash-b visível pro cliente final. Histórico completo: `ROADMAP.md`, Fase 66.

Desde a Fase 66 a plataforma de pagamento é a **Zouti** (não mais a Kiwify) e a
licença é uma **conta com módulos**: uma chave por e-mail, que vale pra todos os
serviços do Appfiliado (bot de WhatsApp, Meu site, vitrine, vídeos, Instagram).

Arquivos: `licencas/models.py` (`ContaAppfiliado`, `Assinatura`, `ProdutoZouti`,
`EventoWebhookZouti`), `licencas/services.py` (interpreta os eventos, monta a
resposta da validação), `licencas/views.py` (webhook + validação),
`licencas/admin.py`.

### Webhook da Zouti

- URL: `/licencas/webhook/zouti/`, cadastrada no painel da Zouti em
  **Integrações > Webhooks**. Segredo do webhook em `ZOUTI_WEBHOOK_SECRET`.
- Assinatura no cabeçalho `x-zouti-signature: t=<ms>,v1=<hmac_sha256>` do corpo
  bruto. Ainda não confirmada contra um disparo real - o "Testar Webhook" do
  painel diz na hora (Admin > Eventos de webhook da Zouti > "assinatura válida").
- Eventos usados: `SUBSCRIPTION_*` (criada, ativada, renovada, cancelada,
  atrasada), `ORDER_REFUNDED`/`PAYMENT_REFUNDED` e `ORDER_DISPUTED`/`PAYMENT_DISPUTED`.
- Quais módulos cada produto libera fica em **Admin > Produtos da Zouti** (pelo
  `prod_...`) - muda na hora, sem deploy.
- Toda requisição é salva crua em `EventoWebhookZouti`; evento repetido
  (`x-zouti-event-id`) não é reprocessado.

### Endpoint de validação (o que o bot chama)

- URL: `/licencas/validar/`. Os campos abaixo (`valido`, `motivo`, `plano`,
  `expira_em`) continuam com o mesmo significado: **`valido` = pode abrir o bot
  de WhatsApp**. Vêm também dois campos novos, que a versão do app com módulos
  deve usar:

```json
{
  "valido": true,
  "motivo": "",
  "plano": "Mensal",
  "expira_em": "2026-11-25",
  "conta_ativa": true,
  "modulos": ["whatsapp", "site"]
}
```

- `conta_ativa`: a conta tem pelo menos um módulo liberado (o app abre).
- `modulos`: códigos liberados agora - `whatsapp`, `site`, `vitrine`, `videos`,
  `instagram`. O que não estiver na lista aparece com cadeado no app.

### Email da chave

- Enviado uma vez por conta, na primeira assinatura que passa a dar acesso.
  Assinar outro serviço depois não gera chave nova. Dá pra reenviar pelo admin.
- Remetente em `APPFILIADO_EMAIL_REMETENTE` - trocar pra
  `contato@appfiliado.com.br` depois de autenticar o domínio no Brevo.

### O que falta

- Configurar a Zouti (produtos, webhook, segredo) e conferir os primeiros
  eventos reais no admin antes do primeiro cliente pagante.
- `licenca.py` ainda só lê os campos antigos - ler `conta_ativa` e `modulos`
  entra junto com o novo layout do app.

## Comportamento do lado do bot (já implementado)

- **Tela de ativação obrigatória** ao abrir o app (`LicencaDialog` em
  `app.py`): se já existe uma chave salva, tenta validar sozinho; senão,
  pede pra colar a chave.
- **Checagem periódica** a cada 6 horas enquanto o app está aberto
  (`licenca_timer`); se a licença deixar de ser válida com o bot rodando,
  ele para o bot automaticamente e reabre a tela de ativação.
- **Tolerância offline de 5 dias**: se o bot não conseguir nem consultar o
  servidor (sem internet, servidor fora do ar), continua liberado desde
  que a última validação bem-sucedida tenha sido há no máximo 5 dias -
  evita travar o bot por uma queda de internet de algumas horas. Esse
  prazo é a constante `DIAS_TOLERANCIA_OFFLINE` em `licenca.py`.
- Botão **"Licença"** na tela principal, pra trocar de chave ou conferir o
  status a qualquer momento (ex: depois de assinar de novo com outro
  email).
