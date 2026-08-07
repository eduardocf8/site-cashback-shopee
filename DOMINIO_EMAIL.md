# Domínio e e-mail do cash-b — histórico e decisões

Este arquivo documenta a configuração do domínio próprio (`cash-b.com`) e
do e-mail `contato@cash-b.com`, feita fora do repositório (painéis do
GoDaddy, Cloudflare e Brevo, sem nenhum código envolvido) - por isso não
tem commit nenhum registrando isso, só esse arquivo mesmo.

## Domínio

- **Registrador**: GoDaddy (`cash-b.com` foi comprado lá).
- **DNS**: gerenciado no **Cloudflare**, não no GoDaddy - o GoDaddy só é o
  registrador, os registros (A/CNAME/MX/TXT etc.) ficam e são editados no
  painel do Cloudflare. O Render está configurado com esse domínio
  customizado, apontando pro serviço web do site.

⚠️ **Atenção** (achado numa investigação de bug, ver
`marketing/instagram/README.md`, seção Troubleshooting): como o
Cloudflare fica na frente do domínio customizado, qualquer coisa que
precise ser buscada por um rastreador/bot externo (não um navegador
comum) pode esbarrar em proteção contra bot do Cloudflare - foi o caso do
rastreador da Meta tentando buscar uma imagem pra publicar no Instagram.
A solução usada lá foi **não depender do domínio customizado** pra esse
tipo de acesso máquina-a-máquina, usando direto o endereço do Render
(`RENDER_EXTERNAL_HOSTNAME`, que não passa pelo Cloudflare). Vale lembrar
disso se aparecer algum problema parecido (algum serviço externo não
conseguindo acessar algo em `cash-b.com` mesmo funcionando num navegador
normal).

## E-mail (`contato@cash-b.com`)

- **Envio**: via **Brevo** (API HTTP, não SMTP - ver
  `cashback_shopee/brevo_email_backend.py`), já usado pelo site pra:
  recuperação de senha, confirmação de e-mail no cadastro, e-mails de
  status (pedido validado, saldo liberado, saque pago), formulário "Fale
  conosco", e aprovação de posts do bot do Instagram
  (`INSTAGRAM_APROVADOR_EMAIL`). Configurado via `BREVO_API_KEY` e
  `DEFAULT_FROM_EMAIL=cash-b <contato@cash-b.com>` (`.env`/Render).
- **Recebimento**: `contato@cash-b.com` não é uma caixa de entrada própria
  - é configurado no Cloudflare (Email Routing) pra **redirecionar** pro
    Gmail pessoal. Ou seja, e-mails mandados pra `contato@cash-b.com`
    chegam na prática na caixa de entrada do Gmail, via encaminhamento.
- **DMARC**: registrado (configuração de autenticação/anti-spoofing do
  domínio, evita que e-mails enviados "como" `cash-b.com` sejam
  rejeitados/marcados como spam, e ajuda a proteger contra alguém se
  passar pelo domínio).

Os valores exatos dos registros de DNS (SPF/DKIM/DMARC/MX, e a regra de
encaminhamento do Email Routing) ficam só no painel do Cloudflare e nas
configurações de domínio remetente da Brevo - esse arquivo documenta a
configuração e o "porquê", não os valores literais (evita esse arquivo
ficar desatualizado se algum registro for renovado/trocado, e não expõe
detalhe de configuração de segurança no repositório).

## Onde mexer se precisar

- **DNS/domínio**: painel do Cloudflare (não GoDaddy - lembrar disso, é
  fácil esquecer e ir procurar no lugar errado).
- **Envio de e-mail (Brevo)**: painel da Brevo, seção de domínios
  remetentes/autenticação, e a variável `BREVO_API_KEY` no Render.
- **Recebimento (redirecionamento pro Gmail)**: Cloudflare → Email
  Routing.
