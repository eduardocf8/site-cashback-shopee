GRUPO_ORIGEM = "OLAPROMOS"

GRUPOS_DESTINO = [
    "Ofertas @vegrassi"
]

HEADLESS = False
INTERVALO = 500
PROCESSAR_HISTORICO_AO_INICIAR = True

# O bot nao baixa mais imagens do grupo origem.
# Ele cola o texto com link afiliado e aguarda a previa do proprio link no WhatsApp.
AGUARDAR_PREVIA_LINK = True
TIMEOUT_PREVIA_LINK_MS = 30000
ESPERA_MINIMA_PREVIA_LINK_MS = 6000
TIMEOUT_IMAGEM_PREVIA_LINK_MS = 30000

# Processa apenas links da Shopee/Shopee afiliados/encurtadores usados pelo grupo.
PROCESSAR_APENAS_SHOPEE = True
# API aberta da Shopee Afiliados.
# Preencha com os dados da pagina "Abrir API".
SHOPEE_API_APP_ID = ""
SHOPEE_API_SECRET = ""
SHOPEE_API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
SHOPEE_API_SUB_IDS = []
SHOPEE_API_TIMEOUT_SEGUNDOS = 30

# Versão sem API/IA paga: o texto é reestruturado localmente por regras.
USAR_IA = False

# Mantém uma linha em branco entre cada bloco da oferta.
ESPACAR_BLOCOS_OFERTA = True

# Se True, varia cabeçalho/chamada/fechamento. Se False, mantém textos mais fixos.
VARIAR_TEXTO_OFERTA = True
