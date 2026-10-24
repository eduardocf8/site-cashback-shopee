"""Orientação para liberar a API da Shopee (AppID e Secret), usada na landing, no painel e no PDF de boas-vindas."""

URL_FORMULARIO = ("https://help.shopee.com.br/portal/webform/bbce78695c364ba18c9cbceb74ec9091"
                  "?entryPoint=1&lastArticleID=&isPlatinum=1")
URL_OPEN_API = "https://affiliate.shopee.com.br/open_api"

# Respostas do formulário "Quero ativar a API", na ordem em que aparecem.
CAMPOS_FORMULARIO = [
    ("Você já é Afiliado da Shopee?", "Sim"),
    ("Problemas pra entrar ou não lembra com qual conta se inscreveu?", "Não, estou com outras dificuldades / dúvidas"),
    ("ID de Afiliado", "o seu ID de Afiliado da Shopee"),
    ("Telefone", "o número cadastrado no Programa de Afiliados"),
    ("Tema", "Tenho dúvidas/ dificuldades com meu cadastro / conta"),
    ("Cenário", "Quero ativar a API"),
]

PASSOS = [
    ("Tenha o cadastro de afiliado aprovado", "Você precisa ser afiliado da Shopee (Programa de Afiliados) antes de pedir a API."),
    ("Envie a solicitação no formulário da Shopee", "Preencha o formulário de ajuda da Shopee escolhendo \"Quero ativar a API\" e envie. Ao final aparece a mensagem \"Seu caso será enviado para análise\"."),
    ("Aguarde a análise", "A Shopee tem até 5 dias úteis pra responder, mas nem sempre manda e-mail. Consulte a sua solicitação todos os dias."),
    ("Clique em Aplicar", "Entre na página Open API do portal de afiliados. Quando o botão \"Aplicar\" aparecer, a API foi liberada: clique nele e a Shopee cria o seu AppID e o seu Secret."),
    ("Informe no Appfiliado", "Em Configurações do painel, cole o AppID e o Secret. Pronto: as ferramentas passam a funcionar."),
]

RESUMO = ("Pra usar as ferramentas do Appfiliado, a sua conta de afiliado precisa ter a API da Shopee liberada. "
          "É um pedido simples feito à Shopee, que responde em até 5 dias úteis.")
