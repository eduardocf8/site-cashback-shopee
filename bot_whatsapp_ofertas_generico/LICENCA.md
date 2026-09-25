# Licença (assinatura) do bot

O bot é um arquivo baixado que roda offline no computador de quem compra -
diferente de um curso hospedado numa plataforma (Hotmart, Kiwify etc.), a
própria plataforma de pagamento **não tem como desligar o bot sozinha**
quando alguém cancela a assinatura ou o pagamento falha. Por isso o bot
consulta, periodicamente, um servidor próprio que sabe (através dos
webhooks recebidos da plataforma de pagamento) se aquela chave ainda está
com a assinatura em dia.

Essa pasta (`bot_whatsapp_ofertas_generico`) já tem o lado do **bot**
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

## Peça que falta construir: o backend

1. **Um modelo de licença** guardando, por chave (ou por email do
   comprador): status (ativa/cancelada/atrasada), plano, data de
   expiração/próxima cobrança.
2. **Um endpoint de webhook**, configurado na plataforma de pagamento
   (Kiwify/Hotmart/Pepper/etc.), que recebe os eventos de compra aprovada,
   assinatura cancelada, pagamento atrasado, reembolso etc., e atualiza o
   modelo de licença de acordo. Cada plataforma tem seu próprio formato de
   payload e nomes de evento - isso precisa ser mapeado por plataforma.
3. **Geração e entrega da chave**: ao receber o evento de "compra
   aprovada", gerar uma chave única e enviá-la para o comprador (por
   email, ou usando a própria função de "conteúdo entregue
   automaticamente" da plataforma).
4. **O endpoint de validação** descrito acima, que só lê o status já
   salvo no banco (não precisa consultar a plataforma de pagamento em
   tempo real a cada checagem do bot).

Como o projeto já tem um site em Django, o caminho mais direto é um novo
app (`licencas`, por exemplo) com esse modelo + as views de webhook e de
validação.

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
