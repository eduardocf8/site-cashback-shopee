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
menção à cash-b visível pro cliente final.

Arquivos: `licencas/models.py` (`Licenca`, `EventoWebhookKiwify`),
`licencas/services.py` (interpreta o evento e decide o status),
`licencas/views.py` (webhook + endpoint de validação), `licencas/admin.py`
(pra ver licenças e webhooks recebidos direto no admin do Django).

### Webhook da Kiwify (confirmado com payload real de teste)

- URL: `/licencas/webhook/kiwify/`
- A Kiwify manda `POST` com o corpo em JSON e a assinatura na própria URL:
  `?signature=<hex>`, onde `<hex>` é `HMAC-SHA1(chave=Token do webhook,
  mensagem=corpo bruto da requisição)`. Confirmado testando contra um
  payload real (bate 100%) - não está documentado publicamente pela
  Kiwify, então não mude sem testar de novo.
- O Token vem do painel da Kiwify: **Webhooks > (o webhook do Appfiliado) >
  Token** - configura em `KIWIFY_WEBHOOK_TOKEN` no `.env`.
- Campo que identifica o tipo de evento: `webhook_event_type` (ex:
  `"order_approved"` confirmado; outros valores ainda não vistos em
  produção). Por isso `services.interpretar_evento` prioriza os campos
  `order_status` e `Subscription.status`, que são mais estáveis, e só usa
  `webhook_event_type` como reforço (contém "refund", "chargeback" etc.).
- Qualquer status de assinatura que a Kiwify mande e a gente ainda não
  tenha mapeado **bloqueia por padrão** (não libera "por garantia") - fica
  registrado com `motivo` pedindo conferência manual, visível no admin.
- Toda requisição recebida é salva crua em `EventoWebhookKiwify` (mesmo as
  com assinatura inválida), pra dar pra depurar formatos novos sem precisar
  reproduzir o evento de novo.

### Endpoint de validação (o que o bot chama)

- URL: `/licencas/validar/` - mesmo contrato descrito abaixo, sem mudança.

### Email da chave

- Enviado só na primeira vez que uma assinatura (`Subscription.id`) é
  vista (evento `order_approved`) - renovações não reenviam a chave.
- Remetente configurado em `APPFILIADO_EMAIL_REMETENTE` (`.env`) - por
  enquanto usa o domínio verificado da cash-b só como transporte técnico
  (`Appfiliado <contato@cash-b.com>`), sem nenhuma menção a cash-b no
  corpo do email. Trocar assim que o Appfiliado tiver domínio próprio.

### O que falta

- ✅ `licenca_servidor_url` já vem preenchido por padrão em `settings.py`
  apontando pra `https://site-cashback-shopee.onrender.com/licencas/validar/`
  - testado de ponta a ponta em 2026-09-28/29 com uma licença real criada
  direto no admin. Sem isso, todo cliente novo cairia em "Servidor de
  licenças não configurado" sem conseguir resolver sozinho.
- ✅ `licencas/tests.py` cobre com testes automatizados (17 testes,
  incluindo ponta a ponta via HTTP com assinatura HMAC real) a lógica de
  decisão para cancelamento, reembolso (por `webhook_event_type` e por
  `order_status`), chargeback, atraso de pagamento e pagamento recusado -
  além dos casos de segurança (status desconhecido bloqueia por padrão,
  evento sem nenhum sinal reconhecido bloqueia por padrão). Também cobre
  que o mesmo registro de `Licenca` é reaproveitado (não duplicado) ao
  longo do ciclo de vida da assinatura e que o email só é enviado uma vez,
  na criação.
- **Ainda falta**: os testes acima confirmam que o *nosso código* decide
  certo dado um payload no formato que a gente espera - mas só o evento de
  compra aprovada (`order_approved`) já foi confirmado contra um payload
  real da Kiwify. Falta ver no admin (`/admin/licencas/`) os primeiros
  eventos reais de cancelamento/reembolso/chargeback/atraso chegando e
  conferir se `webhook_event_type`/`order_status`/`Subscription.status`
  batem com o que `services.interpretar_evento` espera. Vale testar isso
  (ex: assinar com um cartão de teste e depois cancelar, ou usar os
  eventos de teste do painel da Kiwify) antes de vender pra clientes de
  verdade, já que é justamente o mecanismo que impede uso sem pagamento.

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
