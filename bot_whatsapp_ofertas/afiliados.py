import hashlib
import json
import re
import time
from datetime import datetime
import urllib.error
import urllib.parse
import urllib.request

from config import (
    SHOPEE_API_APP_ID,
    SHOPEE_API_SECRET,
    SHOPEE_API_SUB_IDS,
    SHOPEE_API_TIMEOUT_SEGUNDOS,
    SHOPEE_API_URL,
)
from categorias_shopee import produto_pertence_as_categorias


class ConversorAfiliados:
    def __init__(self, play=None, headless=False, app_config=None):
        self.api_url = SHOPEE_API_URL
        self.app_id = str(
            getattr(app_config, "shopee_api_app_id", SHOPEE_API_APP_ID) or ""
        ).strip()
        self.secret = str(
            getattr(app_config, "shopee_api_secret", SHOPEE_API_SECRET) or ""
        ).strip()
        self.sub_ids = list(
            getattr(app_config, "shopee_api_sub_ids", SHOPEE_API_SUB_IDS) or []
        )
        self.timeout = getattr(
            app_config,
            "shopee_api_timeout_segundos",
            SHOPEE_API_TIMEOUT_SEGUNDOS,
        )
        self._contexto_navegador = None
        self._contexto_externo = False
        self._logger = print
        self._cache_links_resolvidos = {}

    def definir_contexto_navegador(self, contexto, externo=False):
        """
        Recebe o contexto (browser) do Playwright ja aberto para o WhatsApp
        Web, para poder abrir links em uma aba nova usando um navegador de
        verdade. Isso e necessario porque a Shopee bloqueia requisicoes
        "simples" (sem fingerprint de navegador real) para resolver links
        curtos (s.shopee.com.br), mostrando uma pagina de "navegador nao
        suportado" em vez de seguir para o produto.

        externo=True indica que o contexto pertence a um navegador que NAO foi
        aberto pelo bot (modo CDP: o usuario abriu o Chrome). Nesse caso o
        conversor NAO deve fechar esse contexto em fechar(), senao fecharia o
        navegador do proprio usuario.
        """
        self._contexto_navegador = contexto
        self._contexto_externo = bool(externo)

    def definir_logger(self, logger):
        """Usa o log do bot (visivel na interface) em vez de print (so aparece no console)."""
        if callable(logger):
            self._logger = logger

    def _log(self, mensagem):
        try:
            self._logger(mensagem)
        except Exception:
            print(mensagem)

    def converter_link(self, link):
        if "shopee" in (link or "") or "shoope.top" in (link or ""):
            return self.converter_shopee(link)

        return link

    def converter_shopee(self, link_original):
        print("Convertendo link Shopee pela API...")

        if not self.app_id or not self.secret:
            raise Exception(
                "Configure SHOPEE_API_APP_ID e SHOPEE_API_SECRET no config.py."
            )

        link_produto = self.normalizar_url_origem(link_original)

        print("URL enviada para API Shopee:")
        print(link_produto)

        payload = self.montar_payload_generate_short_link(link_produto)
        resposta = self.executar_payload_graphql(payload)

        link_afiliado = self.extrair_short_link(resposta)

        if not link_afiliado:
            raise Exception(f"API Shopee nao retornou shortLink: {resposta}")

        print("Link afiliado gerado pela API:")
        print(link_afiliado)

        return link_afiliado

    def executar_payload_graphql(self, payload):
        timestamp = str(int(time.time()))
        signature = self.gerar_assinatura(timestamp, payload)

        headers = {
            "Authorization": (
                f"SHA256 Credential={self.app_id}, "
                f"Timestamp={timestamp}, "
                f"Signature={signature}"
            ),
            "Content-Type": "application/json",
        }

        request = urllib.request.Request(
            self.api_url,
            data=payload.encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detalhe = e.read().decode("utf-8", errors="replace")
            raise Exception(f"Erro HTTP da API Shopee ({e.code}): {detalhe}") from e
        except urllib.error.URLError as e:
            raise Exception(f"Erro de conexao com a API Shopee: {e}") from e

    def executar_query_graphql(self, query):
        payload = json.dumps(
            {"query": query},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        resposta = self.executar_payload_graphql(payload)
        dados = json.loads(resposta)
        erros = dados.get("errors")
        if erros:
            raise Exception(f"Erro retornado pela API Shopee: {erros}")
        return dados.get("data") or {}

    def obter_indicadores_por_sub_id(self, inicio, fim):
        inicio_ts = int(inicio.timestamp())
        fim_ts = int(fim.timestamp())
        conversoes = self.obter_relatorio_conversoes(inicio_ts, fim_ts)
        resultado = self.agrupar_indicadores(conversoes)
        resultado["resumo_status_pedidos"] = self.calcular_resumo_status_pedidos(conversoes)
        return resultado

    def calcular_resumo_status_pedidos(self, conversoes):
        """
        Conta quantos PEDIDOS (não conversões) existem em cada status
        (COMPLETED, PENDING, UNPAID, CANCELLED etc.), usado para diagnosticar
        divergências entre o total do bot e o total mostrado no site da
        Shopee. Uma conversão pode ter mais de um pedido.
        """

        contagem = {}
        for conversao in conversoes:
            pedidos = conversao.get("orders") if isinstance(conversao, dict) else None
            if not isinstance(pedidos, list):
                continue
            for pedido in pedidos:
                if not isinstance(pedido, dict):
                    continue
                status = str(pedido.get("orderStatus") or "").strip().upper() or "DESCONHECIDO"
                contagem[status] = contagem.get(status, 0) + 1

        return contagem

    def _para_numero(self, valor):
        """Converte valores monetarios/quantidade da API para float de forma
        tolerante (aceita '12,34', '12.34', '1.234,56', numeros, None)."""
        if valor is None:
            return 0.0
        if isinstance(valor, (int, float)):
            return float(valor)
        texto = str(valor).strip()
        if not texto:
            return 0.0
        # Remove qualquer coisa que nao seja digito, virgula, ponto ou sinal.
        texto = re.sub(r"[^\d.,-]", "", texto)
        if not texto:
            return 0.0
        # Se tem virgula e ponto, assume ponto como milhar e virgula decimal.
        if "," in texto and "." in texto:
            texto = texto.replace(".", "").replace(",", ".")
        elif "," in texto:
            texto = texto.replace(",", ".")
        try:
            return float(texto)
        except ValueError:
            return 0.0

    def obter_conversoes_por_produto(self, inicio, fim):
        """
        Retorna os produtos convertidos no periodo, agregados por produto E
        por categoria de origem (Sub ID classificado - mesma classificacao
        usada na aba Indicadores, via classificar_sub_id_relatorio), com
        quantidade vendida, preco unitario (ultimo visto), comissao total
        e data da ultima compra. Usa o conversionReport (orders > items).

        Um mesmo produto pode aparecer em mais de uma linha se foi vendido
        atraves de mais de uma categoria de origem no periodo.

        Estrutura de retorno:
            {
              "produtos": [
                 {"item_id", "nome", "loja", "categoria", "quantidade",
                  "preco", "comissao", "ultima_compra" (datetime|None)},
                 ...
              ],
              "totais": {"produtos", "quantidade", "comissao"},
              "inicio", "fim",
              "debug": {"conversoes": N, "itens": M},
            }
        """
        inicio_ts = int(inicio.timestamp())
        fim_ts = int(fim.timestamp())
        conversoes = self.obter_relatorio_conversoes(inicio_ts, fim_ts, incluir_itens=True)

        agregados = {}
        total_itens = 0

        for conversao in conversoes:
            if not isinstance(conversao, dict):
                continue
            pedidos = conversao.get("orders")
            if not isinstance(pedidos, list):
                continue

            # purchaseTime esta no nivel da conversao (unix seconds).
            ts_compra = conversao.get("purchaseTime")
            data_compra = None
            try:
                if ts_compra:
                    data_compra = datetime.fromtimestamp(int(ts_compra))
            except (ValueError, OSError, OverflowError):
                data_compra = None

            # Mesma extracao/classificacao usada em agrupar_indicadores: se a
            # conversao tiver mais de um Sub ID (raro), o item conta uma vez
            # em cada categoria correspondente - igual ja acontece hoje na
            # aba Indicadores, para manter os dois relatorios consistentes.
            sub_ids = self.extrair_sub_ids_relatorio(conversao)
            if not sub_ids:
                sub_ids = ["sem_subid"]
            categorias = [self.classificar_sub_id_relatorio(sub_id) for sub_id in sub_ids]

            for pedido in pedidos:
                if not isinstance(pedido, dict):
                    continue

                # Mesma regra da aba Indicadores: pedidos CANCELLED/UNPAID nao
                # contam (venda nao paga ou cancelada). Assim os totais deste
                # relatorio batem com o painel de Indicadores. A constante
                # STATUS_PEDIDO_INVALIDOS e a mesma usada la.
                status_pedido = str(pedido.get("orderStatus") or "").strip().upper()
                if status_pedido in self.STATUS_PEDIDO_INVALIDOS:
                    continue

                itens = pedido.get("items")
                if not isinstance(itens, list):
                    continue
                for item in itens:
                    if not isinstance(item, dict):
                        continue
                    total_itens += 1
                    item_id = str(item.get("itemId") or "").strip()
                    nome = str(item.get("itemName") or "").strip() or "(sem nome)"
                    loja = str(item.get("shopName") or "").strip()
                    # Chave de agregacao: itemId (ou nome) + categoria.
                    chave_produto = item_id or nome

                    qtd = self._para_numero(item.get("qty")) or 1
                    preco = self._para_numero(item.get("itemPrice"))
                    comissao = self._para_numero(item.get("itemTotalCommission"))

                    for categoria in categorias:
                        chave = (chave_produto, categoria)
                        registro = agregados.get(chave)
                        if registro is None:
                            registro = {
                                "item_id": item_id,
                                "nome": nome,
                                "loja": loja,
                                "categoria": categoria,
                                "quantidade": 0.0,
                                "preco": preco,
                                "comissao": 0.0,
                                "ultima_compra": data_compra,
                            }
                            agregados[chave] = registro

                        registro["quantidade"] += qtd
                        registro["comissao"] += comissao
                        if preco:
                            registro["preco"] = preco
                        if data_compra and (
                            registro["ultima_compra"] is None
                            or data_compra > registro["ultima_compra"]
                        ):
                            registro["ultima_compra"] = data_compra

        produtos = list(agregados.values())
        total_qtd = sum(p["quantidade"] for p in produtos)
        total_comissao = sum(p["comissao"] for p in produtos)

        return {
            "produtos": produtos,
            "totais": {
                "produtos": len(produtos),
                "quantidade": total_qtd,
                "comissao": total_comissao,
            },
            "inicio": inicio,
            "fim": fim,
            "debug": {"conversoes": len(conversoes), "itens": total_itens},
        }

    def obter_relatorio_conversoes(self, inicio_ts, fim_ts, incluir_itens=False):
        campos_disponiveis = self.obter_campos_tipo("ConversionReport")
        campos = self.selecionar_campos(
            campos_disponiveis,
            (
                "purchaseTime",
                "conversionId",
                "utmContent",
                "grossCommission",
                "netCommission",
                "cappedCommission",
                "totalCommission",
                "sellerCommission",
                "orderAmount",
                "itemPrice",
                "purchaseAmount",
                "salesAmount",
            ),
        )

        if not campos:
            raise Exception(
                "A API Shopee não informou campos disponíveis para ConversionReport."
            )

        # "orders" é um campo aninhado (lista de pedidos, cada um com seu
        # próprio orderStatus) - orderId/orderStatus NÃO existem no nível
        # raiz do ConversionReport, por isso a checagem por nome exato de
        # selecionar_campos nunca os encontrava. Adicionamos manualmente a
        # sub-seleção.
        #
        # incluir_itens=True acrescenta o detalhamento por produto
        # (itemName/qty/itemPrice/itemTotalCommission), usado na aba
        # "Relatório de conversões". Fica desligado por padrão para NÃO
        # arriscar quebrar a aba Indicadores (que só precisa de orderStatus):
        # se a API de alguma conta rejeitar algum subcampo de items, a query
        # inteira falharia.
        if "orders" in campos_disponiveis:
            if incluir_itens:
                bloco_orders = (
                    "orders{orderId orderStatus "
                    "items{itemId itemName shopName itemPrice qty "
                    "itemTotalCommission attributionType}}"
                )
            else:
                bloco_orders = "orders{orderId orderStatus}"
            campos = list(campos) + [bloco_orders]

        try:
            return self.executar_relatorio_paginado(
                "conversionReport",
                "purchaseTimeStart",
                "purchaseTimeEnd",
                inicio_ts,
                fim_ts,
                campos,
            )
        except Exception as e:
            # Se pediu itens e a API rejeitou algum subcampo de items, tenta de
            # novo sem itens para pelo menos não deixar a tela vazia/erro.
            if incluir_itens:
                self._log(
                    f"A API rejeitou o detalhamento por item ({e}); "
                    "tentando novamente sem os itens dos pedidos."
                )
                return self.obter_relatorio_conversoes(inicio_ts, fim_ts, incluir_itens=False)
            raise

    def executar_relatorio_paginado(
        self,
        nome_relatorio,
        parametro_inicio,
        parametro_fim,
        inicio_ts,
        fim_ts,
        campos,
    ):
        todos = []
        scroll_id = ""
        visitados = set()

        for _ in range(50):
            if scroll_id in visitados:
                break
            visitados.add(scroll_id)

            parametros = (
                f'{parametro_inicio}:{inicio_ts},'
                f'{parametro_fim}:{fim_ts},'
                'limit:500,'
                f'scrollId:{json.dumps(scroll_id, ensure_ascii=False)}'
            )
            data = self.executar_relatorio_com_campos(nome_relatorio, parametros, campos)
            relatorio = data.get(nome_relatorio) or {}
            nodes = relatorio.get("nodes") or []
            if isinstance(nodes, list):
                todos.extend(nodes)

            page_info = relatorio.get("pageInfo") or {}
            novo_scroll_id = str(page_info.get("scrollId") or "").strip()
            has_next = bool(page_info.get("hasNextPage"))
            if not has_next or not novo_scroll_id:
                break
            scroll_id = novo_scroll_id

        return todos

    def executar_relatorio_com_campos(self, nome_relatorio, parametros, campos):
        campos_atuais = list(campos)
        ultimo_erro = None

        while campos_atuais:
            query = (
                "query{"
                f"{nome_relatorio}({parametros})"
                "{nodes{"
                f"{' '.join(campos_atuais)}"
                "}pageInfo{scrollId hasNextPage}}"
                "}"
            )
            try:
                return self.executar_query_graphql(query)
            except Exception as e:
                ultimo_erro = e
                campo_invalido = self.extrair_campo_graphql_invalido(str(e))
                if not campo_invalido or campo_invalido not in campos_atuais:
                    break
                campos_atuais.remove(campo_invalido)

        raise Exception(f"Não consegui consultar {nome_relatorio}: {ultimo_erro}")

    def extrair_campo_graphql_invalido(self, mensagem):
        match = re.search(r'Cannot query field "([^"]+)"', mensagem)
        return match.group(1) if match else ""

    def obter_campos_tipo(self, nome_tipo):
        query = (
            "query{"
            f'__type(name:"{nome_tipo}")'
            "{fields{name}}"
            "}"
        )
        try:
            data = self.executar_query_graphql(query)
            tipo = data.get("__type") or {}
            fields = tipo.get("fields") or []
            campos = {
                field.get("name")
                for field in fields
                if isinstance(field, dict) and field.get("name")
            }
            if campos:
                return campos
        except Exception:
            pass

        if nome_tipo == "ConversionReport":
            return {
                "purchaseTime",
                "utmContent",
                "netCommission",
                "grossCommission",
                "cappedCommission",
                "totalCommission",
                "sellerCommission",
                "orders",
            }
        return set()

    def selecionar_campos(self, disponiveis, desejados):
        return [campo for campo in desejados if campo in disponiveis]

    def buscar_ofertas_shopee(self, app_config=None, limite=None, pagina=1, shop_id_forcado=None):
        config = app_config
        limite = int(limite or getattr(config, "shopee_ofertas_quantidade_por_ciclo", 10) or 10)
        limite = max(1, min(50, limite))
        pagina = max(1, int(pagina or 1))

        link_colecao = str(getattr(config, "shopee_ofertas_link_colecao", "") or "").strip()
        colecao_id = self.extrair_id_colecao(link_colecao)
        ofertas, tem_mais_paginas = self.executar_busca_product_offer_v2(
            config, limite, pagina=pagina, shop_id_forcado=shop_id_forcado
        )
        parametros_usados = getattr(self, "ultima_busca_ofertas_parametros", "") or ""
        ofertas_normalizadas = [self.normalizar_oferta_shopee(oferta) for oferta in ofertas]
        ofertas_filtradas = [
            oferta
            for oferta in ofertas_normalizadas
            if self.oferta_passa_filtros(oferta, config)
        ]

        return {
            "ofertas": ofertas_filtradas[:limite],
            "total_recebido": len(ofertas),
            "total_filtrado": len(ofertas_filtradas),
            "campos": self.listar_campos_amostra(ofertas),
            "colecao_link": link_colecao,
            "colecao_id": colecao_id,
            "colecao_parametro_aplicado": bool(link_colecao and "matchid" in parametros_usados.lower()),
            "parametros_usados": parametros_usados,
            "pagina": pagina,
            "tem_mais_paginas": tem_mais_paginas,
        }

    def campos_produto_shopee(self):
        return [
            "itemId",
            "productId",
            "shopId",
            "productName",
            "itemName",
            "name",
            "offerName",
            "price",
            "priceMin",
            "priceMax",
            "priceDiscount",
            "priceDiscountRate",
            "pixPrice",
            "pricePix",
            "cashPrice",
            "priceCash",
            "finalPrice",
            "salePrice",
            "discountPrice",
            "installmentPrice",
            "installmentPriceMin",
            "originalPrice",
            "normalPrice",
            "discountRate",
            "commissionRate",
            "sellerCommissionRate",
            "shopeeCommissionRate",
            "commission",
            "productCatIds",
            "ratingStar",
            "imageUrl",
            "image",
            "imageLink",
            "imageURL",
            "itemImage",
            "itemImageUrl",
            "productImage",
            "productImageUrl",
            "thumbnail",
            "thumbnailUrl",
            "imageList",
            "images",
            "productImages",
            "coverImage",
            "coverImageUrl",
            "productLink",
            "productUrl",
            "offerLink",
            "itemUrl",
            "url",
            "link",
            "rating",
            "sales",
            "sold",
            "historicalSold",
            "shopName",
        ]

    def executar_busca_product_offer_v2(self, config, limite, pagina=1, shop_id_forcado=None):
        args = self.obter_argumentos_query("productOfferV2")
        campos = self.campos_produto_shopee()

        candidatos_parametros = self.montar_parametros_ofertas(
            config, limite, pagina=pagina, shop_id_forcado=shop_id_forcado
        )
        tentativas = self.montar_tentativas_product_offer_v2(args, candidatos_parametros)
        ultimo_erro = None
        self.ultima_busca_ofertas_parametros = ""

        for parametros in tentativas:
            try:
                data = self.executar_product_offer_v2_com_campos(parametros, campos)
                resultado = data.get("productOfferV2") or {}
                self.ultima_busca_ofertas_parametros = parametros
                tem_mais_paginas = self.extrair_tem_mais_paginas(resultado)
                return self.extrair_nodes_ofertas(resultado), tem_mais_paginas
            except Exception as e:
                ultimo_erro = e

        raise Exception(f"Não consegui consultar ofertas da Shopee: {ultimo_erro}")

    def extrair_ids_produto(self, link):
        """
        Extrai shopId e itemId de um link de produto da Shopee. Reconhece os
        dois formatos de URL usados pela Shopee:
          - https://shopee.com.br/produto-nome-i.SHOPID.ITEMID
          - https://shopee.com.br/product/SHOPID/ITEMID
        Expande o link antes, caso seja um link curto (s.shopee.com.br, shope.ee etc.).
        """

        link_normalizado = self.normalizar_url_origem(link)
        return self._extrair_ids_de_url(link_normalizado)

    def _extrair_ids_de_url(self, url):
        if not url:
            return None, None

        match = re.search(r"[-.]i\.(\d+)\.(\d+)(?:[/?#].*)?$", url)
        if match:
            return match.group(1), match.group(2)

        match = re.search(r"/product/(\d+)/(\d+)(?:[/?#].*)?$", url)
        if match:
            return match.group(1), match.group(2)

        return None, None

    def _extrair_ids_de_parametro_next(self, url):
        """
        Paginas de verificacao/erro da Shopee (ex: /verify/traffic/error)
        costumam trazer o destino real do produto dentro do parametro
        "next" da propria URL (com a URL do produto codificada). Extrai o
        shopId/itemId direto dai, sem precisar carregar essa URL de novo.
        """

        destino = self._extrair_url_de_parametro_next(url)
        if not destino:
            return None, None
        destino_para_ids = self.remover_parametros_desnecessarios(destino)
        return self._extrair_ids_de_url(destino_para_ids)

    def _extrair_url_de_parametro_next(self, url):
        """Extrai a URL bruta (com todos os parametros) do parametro "next" de uma URL."""

        try:
            partes = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(partes.query)
            destino = (query.get("next") or [None])[0]
            if not destino:
                return None
            return self.limpar_link(destino)
        except Exception:
            return None

    def _eh_pagina_de_erro_shopee(self, url):
        """Detecta as paginas de bloqueio/erro conhecidas da Shopee (nao sao o produto de verdade)."""

        url_lower = (url or "").lower()
        return "unsupported.html" in url_lower or "/verify/" in url_lower

    def obter_oferta_por_link(self, link_original):
        """
        Busca a imagem/dados de UM produto especifico a partir do link
        capturado no grupo origem do WhatsApp, tentando, em ordem:

          1) Extrair o itemId direto do link (funciona quando o link
             capturado ja e a URL final do produto, sem encurtador) e
             consultar a API productOfferV2. So encontra o produto se ele
             estiver na base de OFERTAS/COMISSAO da Shopee nesse momento.
          2) Buscar a imagem direto na pagina publica do produto via
             requisicao simples (funciona para links diretos que nao caem
             na checagem de "navegador nao suportado" da Shopee).
          3) Abrir o link em uma aba do navegador de verdade (o mesmo usado
             pelo WhatsApp Web) e ler a URL final + imagem depois de
             carregar. Necessario para links curtos da Shopee
             (s.shopee.com.br e encurtadores de terceiros que apontam para
             ele), porque a Shopee bloqueia requisicoes simples nesse
             endereco com uma pagina de "navegador nao suportado". Se a
             pagina final for uma pagina de verificacao/erro da Shopee, o
             itemId ainda e extraido do parametro "next" dessa URL.

        Retorna uma tupla (oferta_normalizada_ou_None, motivo), onde motivo
        e uma das strings: "api_offer", "pagina_produto", "navegador",
        "sem_item_id", "sem_imagem".
        """

        shop_id, item_id = self.extrair_ids_produto(link_original)

        if item_id:
            oferta = self._buscar_oferta_por_ids(shop_id, item_id)
            if oferta and oferta.get("imagem"):
                return oferta, "api_offer"

        imagem_pagina = self._extrair_imagem_pagina_produto(link_original)
        if imagem_pagina:
            return {"imagem": imagem_pagina}, "pagina_produto"

        resultado_navegador = self._resolver_link_via_navegador(link_original)
        if resultado_navegador:
            url_final, imagem_navegador = resultado_navegador

            if not item_id and url_final:
                shop_id, item_id = self._extrair_ids_de_url(url_final)
                if not item_id:
                    shop_id, item_id = self._extrair_ids_de_parametro_next(url_final)

                if item_id:
                    oferta = self._buscar_oferta_por_ids(shop_id, item_id)
                    if oferta and oferta.get("imagem"):
                        return oferta, "api_offer"

            if imagem_navegador:
                return {"imagem": imagem_navegador}, "navegador"

        if not item_id:
            return None, "sem_item_id"
        return None, "sem_imagem"

    def _resolver_link_via_navegador(self, link):
        """
        Abre o link em uma aba nova do navegador ja usado pelo WhatsApp Web
        (ver definir_contexto_navegador) e le a URL final (depois de
        qualquer redirecionamento, incluindo os que so acontecem via
        JavaScript) e a imagem principal do produto (tag og:image).

        Retorna (url_final, imagem_url) ou None se nao houver navegador
        disponivel ou a navegacao falhar.
        """

        if not self._contexto_navegador:
            return None

        pagina = None
        try:
            pagina = self._contexto_navegador.new_page()
            # Alguns sites (a Shopee entre eles) bloqueiam paginas abertas por
            # automacao checando "navigator.webdriver". O Playwright deixa
            # essa marca ligada por padrao; escondemos ela so nessa aba
            # dedicada a resolver links, sem mexer na aba do WhatsApp Web.
            pagina.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )
            pagina.goto(link, wait_until="domcontentloaded", timeout=25000)
            # Dá um tempo para redirecionamentos feitos via JavaScript
            # (comuns em links curtos) terminarem de acontecer.
            pagina.wait_for_timeout(2500)

            url_final = pagina.url
            imagem_url = pagina.evaluate(
                """
                () => {
                    const meta = document.querySelector('meta[property="og:image"]')
                        || document.querySelector('meta[name="og:image"]');
                    return meta ? meta.getAttribute('content') : null;
                }
                """
            )
            self._log(f"Navegador abriu o link e chegou em: {url_final}")
            if not imagem_url:
                self._log("Pagina carregada pelo navegador nao tinha tag de imagem (og:image).")
            return url_final, imagem_url
        except Exception as e:
            self._log(f"Nao consegui resolver o link pelo navegador: {e}")
            return None
        finally:
            if pagina is not None:
                try:
                    pagina.close()
                except Exception:
                    pass

    def _buscar_oferta_por_ids(self, shop_id, item_id):
        args = self.obter_argumentos_query("productOfferV2")
        campos = self.campos_produto_shopee()

        parametros = {"itemId": item_id, "limit": 1}
        if shop_id:
            parametros["shopId"] = shop_id

        tentativas = self.montar_tentativas_product_offer_v2(args, parametros)
        ultimo_erro = None
        for tentativa in tentativas:
            try:
                data = self.executar_product_offer_v2_com_campos(tentativa, campos)
                resultado = data.get("productOfferV2") or {}
                nodes = self.extrair_nodes_ofertas(resultado)
                if nodes:
                    return self.normalizar_oferta_shopee(nodes[0])
                return None
            except Exception as e:
                ultimo_erro = e

        self._log(f"Nao consegui consultar a API de ofertas para esse produto: {ultimo_erro}")
        return None

    def _extrair_imagem_pagina_produto(self, link_original):
        try:
            link = self.normalizar_url_origem(link_original)
            if not link.lower().startswith(("http://", "https://")):
                return None

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            }
            requisicao = urllib.request.Request(link, headers=headers, method="GET")
            with urllib.request.urlopen(requisicao, timeout=self.timeout) as resposta:
                html = resposta.read().decode("utf-8", errors="ignore")

            match = re.search(
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )
            if not match:
                # A ordem dos atributos no HTML pode vir invertida.
                match = re.search(
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                    html,
                    re.IGNORECASE,
                )
            if match:
                return match.group(1)
            return None
        except Exception as e:
            self._log(f"Nao consegui buscar imagem na pagina do produto: {e}")
            return None

    def extrair_tem_mais_paginas(self, resultado):
        if not isinstance(resultado, dict):
            return None
        page_info = resultado.get("pageInfo")
        if isinstance(page_info, dict) and "hasNextPage" in page_info:
            return bool(page_info.get("hasNextPage"))
        return None

    def montar_parametros_ofertas(self, config, limite, pagina=1, shop_id_forcado=None):
        tipo_busca = str(getattr(config, "shopee_ofertas_tipo_busca", "geral") or "geral")

        palavra = str(getattr(config, "shopee_ofertas_palavra_chave", "") or "").strip()
        shop_id = str(getattr(config, "shopee_ofertas_shop_id", "") or "").strip()
        categoria_id = str(getattr(config, "shopee_ofertas_categoria_id", "") or "").strip()

        # "Tipo de busca" define qual desses três campos vale: só o campo
        # correspondente ao tipo escolhido é realmente usado na busca, os
        # outros são ignorados mesmo que tenham algo preenchido (evita
        # comportamento confuso de campos "esquecidos" preenchidos de uma
        # configuração anterior).
        if tipo_busca != "palavra_chave":
            palavra = ""
        if tipo_busca != "loja":
            shop_id = ""
        if tipo_busca != "categoria":
            categoria_id = ""

        # shop_id_forcado vem da "aproximação de coleção" quando o link
        # informado é de uma LOJA: nesse caso a busca do ciclo é dessa loja,
        # independentemente do tipo de busca configurado.
        if shop_id_forcado:
            shop_id = str(shop_id_forcado).strip()

        ordenacao = str(getattr(config, "shopee_ofertas_ordenacao", "mais_vendidos") or "mais_vendidos")
        sort_type = self.sort_type_shopee(ordenacao)
        if sort_type == 1 and not palavra:
            # sortType=1 (relevância) só é aceito pela API quando existe keyword.
            sort_type = 2

        # NOTA: não usamos mais listType/matchId (DETAIL_COLLECTION=6) para
        # coleção - a Shopee descontinuou esse filtro na API (ele não retorna
        # os produtos da coleção). A coleção agora é aproximada por
        # loja/keyword/categoria (ver _buscar_ofertas_colecao_para_ciclo).
        parametros = {
            "limit": limite,
            "page": pagina,
            "keyword": palavra,
            "shopId": shop_id,
            "productCatId": categoria_id,
            "sortType": sort_type,
        }

        return {chave: valor for chave, valor in parametros.items() if valor not in ("", None)}

    def extrair_id_colecao(self, link):
        texto = str(link or "").strip()
        if not texto:
            return ""
        match = re.search(r"(?:collection|collectionId|collection_id|bundle|cat)\D+(\d{4,})", texto, re.I)
        if match:
            return match.group(1)
        numeros = re.findall(r"\d{6,}", texto)
        return numeros[-1] if numeros else ""

    def extrair_shop_id_de_link(self, link):
        """
        Tenta extrair o shopId de um link da Shopee quando ele aponta para uma
        LOJA (e nao para uma colecao curada). Cobre os formatos comuns:
          - /shop/123456...              -> 123456
          - .../produto-i.SHOPID.ITEMID  -> SHOPID (padrao de link de produto)
          - ?shopid=123456 / &shop_id=   -> 123456
        Retorna "" se nao for possivel identificar uma loja com seguranca.
        Colecoes curadas (/collections/NNN) NAO tem shopId e retornam "".
        """
        texto = str(link or "").strip()
        if not texto:
            return ""

        # Colecao curada explicita: nao ha loja associada.
        if re.search(r"/collections?/", texto, re.I):
            return ""

        m = re.search(r"/shop/(\d{3,})", texto, re.I)
        if m:
            return m.group(1)

        # Link de produto: ...-i.SHOPID.ITEMID
        m = re.search(r"-i\.(\d+)\.\d+", texto, re.I)
        if m:
            return m.group(1)

        m = re.search(r"[?&](?:shopid|shop_id)=(\d+)", texto, re.I)
        if m:
            return m.group(1)

        return ""

    def sort_type_shopee(self, ordenacao):
        # Valores oficiais do sortType na API productOfferV2:
        # 1 = relevância (só vale quando há keyword), 2 = mais vendidos,
        # 3 = maior preço, 4 = menor preço, 5 = maior comissão.
        # Não existe sortType nativo para "maior desconto"; nesse caso pedimos
        # por mais vendidos e a reordenação por desconto é feita depois,
        # em bot_runner, com os dados já recebidos da API.
        return {
            "recentes": 2,
            "mais_vendidos": 2,
            "maior_comissao": 5,
            "maior_desconto": 2,
        }.get(ordenacao, 2)

    def montar_tentativas_product_offer_v2(self, args, parametros):
        tentativas = []
        if args:
            input_arg = next((arg for arg in args if self.eh_tipo_input(arg.get("type"))), None)
            if input_arg:
                input_type = self.nome_base_tipo_graphql(input_arg.get("type"))
                input_fields = self.obter_campos_input(input_type)
                filtrados = {
                    chave: valor
                    for chave, valor in parametros.items()
                    if not input_fields or chave in input_fields
                }
                tentativas.append(f'{input_arg["name"]}:{{{self.graphql_args(filtrados)}}}')

            arg_names = {arg.get("name") for arg in args}
            diretos = {
                chave: valor
                for chave, valor in parametros.items()
                if chave in arg_names
            }
            if diretos:
                tentativas.append(self.graphql_args(diretos))

        tentativas.append(self.graphql_args(parametros))
        pagina = parametros.get("page") or parametros.get("pageNo") or parametros.get("pageNum") or 1
        tentativas.append(self.graphql_args({"limit": parametros.get("limit", 3), "page": pagina}))
        tentativas.append("")

        unicas = []
        for tentativa in tentativas:
            if tentativa not in unicas:
                unicas.append(tentativa)
        return unicas

    def executar_product_offer_v2_com_campos(self, parametros, campos):
        campos_atuais = list(campos)
        ultimo_erro = None
        incluir_page_info = True

        while campos_atuais:
            args = f"({parametros})" if parametros else ""
            page_info = "pageInfo{page limit hasNextPage}" if incluir_page_info else ""
            campos_query = " ".join(campos_atuais)
            query = f"query{{productOfferV2{args}{{nodes{{{campos_query}}}{page_info}}}}}"
            try:
                return self.executar_query_graphql(query)
            except Exception as e:
                ultimo_erro = e
                campo_invalido = self.extrair_campo_graphql_invalido(str(e))
                if campo_invalido == "pageInfo" and incluir_page_info:
                    incluir_page_info = False
                    continue
                if campo_invalido and campo_invalido in campos_atuais:
                    campos_atuais.remove(campo_invalido)
                    continue
                break

        raise Exception(ultimo_erro)

    def obter_argumentos_query(self, nome_query):
        query = (
            "query{__schema{queryType{fields{name args{name type{kind name ofType{kind name ofType{kind name ofType{kind name}}}}}}}}}"
        )
        try:
            data = self.executar_query_graphql(query)
            fields = (((data.get("__schema") or {}).get("queryType") or {}).get("fields") or [])
            for field in fields:
                if field.get("name") == nome_query:
                    return field.get("args") or []
        except Exception:
            pass
        return []

    def obter_campos_input(self, nome_tipo):
        if not nome_tipo:
            return set()
        query = f'query{{__type(name:"{nome_tipo}"){{inputFields{{name}}}}}}'
        try:
            data = self.executar_query_graphql(query)
            fields = ((data.get("__type") or {}).get("inputFields") or [])
            return {field.get("name") for field in fields if field.get("name")}
        except Exception:
            return set()

    def eh_tipo_input(self, tipo):
        while tipo:
            if tipo.get("kind") == "INPUT_OBJECT":
                return True
            tipo = tipo.get("ofType")
        return False

    def nome_base_tipo_graphql(self, tipo):
        atual = tipo
        nome = ""
        while atual:
            nome = atual.get("name") or nome
            atual = atual.get("ofType")
        return nome

    def graphql_args(self, parametros):
        partes = []
        for chave, valor in parametros.items():
            if valor in ("", None):
                continue
            partes.append(f"{chave}:{self.graphql_value(valor)}")
        return ",".join(partes)

    def graphql_value(self, valor):
        if isinstance(valor, bool):
            return "true" if valor else "false"
        if isinstance(valor, (int, float)):
            return str(valor)
        texto = str(valor).strip()
        if re.fullmatch(r"\d+", texto):
            return texto
        return json.dumps(texto, ensure_ascii=False)

    def extrair_nodes_ofertas(self, resultado):
        if isinstance(resultado, list):
            return [item for item in resultado if isinstance(item, dict)]
        if not isinstance(resultado, dict):
            return []
        nodes = resultado.get("nodes")
        if isinstance(nodes, list):
            return [item for item in nodes if isinstance(item, dict)]
        for valor in resultado.values():
            if isinstance(valor, list):
                return [item for item in valor if isinstance(item, dict)]
        return []

    def normalizar_oferta_shopee(self, oferta):
        nome = self.primeiro_texto(oferta, ("productName", "itemName", "name", "offerName"))
        link = self.primeiro_texto(oferta, ("productLink", "productUrl", "offerLink", "itemUrl", "url", "link"))
        imagem = self.primeira_url_imagem_recursiva(
            oferta,
            (
                "imageUrl",
                "image",
                "imageLink",
                "imageURL",
                "itemImage",
                "itemImageUrl",
                "productImage",
                "productImageUrl",
                "thumbnail",
                "thumbnailUrl",
                "imageList",
                "images",
                "productImages",
                "coverImage",
                "coverImageUrl",
            ),
        )
        preco, preco_pix, preco_parcelado = self.extrair_precos_oferta(oferta)
        comissao = self.extrair_primeiro_numero(oferta, ("commissionRate", "sellerCommissionRate", "commission"))
        desconto = self.extrair_primeiro_numero(oferta, ("priceDiscountRate", "discountRate", "priceDiscount"))
        vendas = self.extrair_primeiro_numero(oferta, ("sales", "sold", "historicalSold"))
        avaliacao = self.extrair_primeiro_numero(oferta, ("ratingStar", "rating", "itemRating"))
        if 0 < comissao < 1:
            comissao *= 100
        if 0 < desconto < 1:
            desconto *= 100

        return {
            "item_id": self.primeiro_texto(oferta, ("itemId", "productId")),
            "shop_id": self.primeiro_texto(oferta, ("shopId",)),
            "nome": nome,
            "link": link,
            "imagem": imagem,
            "preco": preco,
            "preco_pix": preco_pix,
            "preco_parcelado": preco_parcelado,
            "comissao": comissao,
            "desconto": desconto,
            "vendas": int(vendas or 0),
            "avaliacao": avaliacao,
            "loja": self.primeiro_texto(oferta, ("shopName",)),
            "raw": oferta,
        }

    def extrair_precos_oferta(self, oferta):
        preco = self.extrair_primeiro_numero(oferta, ("price", "priceMin", "priceMax", "itemPrice"))
        candidatos_pix_explicitos = self.extrair_numeros_por_campos(
            oferta,
            (
                "pixPrice",
                "pricePix",
                "cashPrice",
                "priceCash",
                "paymentPrice",
                "bankTransferPrice",
                "instantPaymentPrice",
                "pixDiscountPrice",
                "priceWithPix",
                "pixFinalPrice",
            ),
        )
        candidatos_preco_final = self.extrair_numeros_por_campos(
            oferta,
            (
                "finalPrice",
                "salePrice",
                "discountPrice",
                "priceMin",
            ),
        )
        candidatos_parcelado_explicitos = self.extrair_numeros_por_campos(
            oferta,
            (
                "installmentPrice",
                "installmentPriceMin",
                "installmentFinalPrice",
                "creditCardPrice",
                "cardPrice",
                "priceWithInstallment",
                "parcelPrice",
            ),
        )
        candidatos_preco_de = self.extrair_numeros_por_campos(
            oferta,
            (
                "normalPrice",
                "originalPrice",
                "listPrice",
                "priceBeforeDiscount",
                "beforeDiscountPrice",
                "regularPrice",
            ),
        )
        todos_precos = self.extrair_numeros_por_campos(
            oferta,
            (
                "pixPrice",
                "pricePix",
                "cashPrice",
                "priceCash",
                "finalPrice",
                "salePrice",
                "discountPrice",
                "priceMin",
                "price",
                "itemPrice",
                "installmentPrice",
                "installmentPriceMin",
                "installmentFinalPrice",
                "creditCardPrice",
                "cardPrice",
                "priceWithInstallment",
                "parcelPrice",
                "originalPrice",
                "normalPrice",
                "listPrice",
                "priceBeforeDiscount",
                "beforeDiscountPrice",
                "regularPrice",
            ),
        )

        preco_pix = min(candidatos_pix_explicitos) if candidatos_pix_explicitos else 0.0
        preco_parcelado = max(candidatos_parcelado_explicitos) if candidatos_parcelado_explicitos else 0.0

        if not preco and candidatos_preco_final:
            preco = min(candidatos_preco_final)

        if not preco_pix and candidatos_pix_explicitos:
            preco_pix = min(candidatos_pix_explicitos)

        if not preco_parcelado and preco_pix and candidatos_preco_final:
            final_maior = max(candidatos_preco_final)
            if final_maior > preco_pix:
                preco_parcelado = final_maior

        if todos_precos and not preco:
            menor = min(todos_precos)
            preco = menor

        if preco_pix and preco_parcelado and preco_pix > preco_parcelado:
            preco_pix, preco_parcelado = preco_parcelado, preco_pix

        if preco_pix and preco_parcelado and abs(preco_pix - preco_parcelado) < 0.01:
            preco_pix = 0.0

        if preco_parcelado and candidatos_preco_de and preco_parcelado in candidatos_preco_de and not preco_pix:
            preco_parcelado = 0.0

        return preco, preco_pix, preco_parcelado

    def primeiro_texto(self, objeto, nomes):
        if not isinstance(objeto, dict):
            return ""
        for nome in nomes:
            valor = objeto.get(nome)
            if valor not in ("", None):
                return str(valor).strip()
        return ""

    def primeiro_texto_recursivo(self, objeto, nomes):
        if isinstance(objeto, dict):
            for nome in nomes:
                valor = objeto.get(nome)
                if valor not in ("", None):
                    return str(valor).strip()
            for valor in objeto.values():
                texto = self.primeiro_texto_recursivo(valor, nomes)
                if texto:
                    return texto
        elif isinstance(objeto, list):
            for item in objeto:
                texto = self.primeiro_texto_recursivo(item, nomes)
                if texto:
                    return texto
        return ""

    def primeira_url_imagem_recursiva(self, objeto, nomes):
        if isinstance(objeto, dict):
            for nome in nomes:
                if nome in objeto:
                    url = self.extrair_url_imagem_de_valor(objeto.get(nome))
                    if url:
                        return url
            for valor in objeto.values():
                url = self.primeira_url_imagem_recursiva(valor, nomes)
                if url:
                    return url
        elif isinstance(objeto, list):
            for item in objeto:
                url = self.primeira_url_imagem_recursiva(item, nomes)
                if url:
                    return url
        return ""

    def extrair_url_imagem_de_valor(self, valor):
        if isinstance(valor, dict):
            for chave in (
                "url",
                "src",
                "imageUrl",
                "image",
                "imageLink",
                "thumbnailUrl",
                "imageList",
                "images",
                "productImages",
                "productImageUrl",
                "coverImageUrl",
            ):
                if chave in valor:
                    url = self.extrair_url_imagem_de_valor(valor.get(chave))
                    if url:
                        return url
            for item in valor.values():
                url = self.extrair_url_imagem_de_valor(item)
                if url:
                    return url
            return ""

        if isinstance(valor, list):
            for item in valor:
                url = self.extrair_url_imagem_de_valor(item)
                if url:
                    return url
            return ""

        texto = str(valor or "").strip()
        if not texto:
            return ""

        if texto.startswith("//"):
            texto = "https:" + texto

        if texto.lower().startswith(("http://", "https://")):
            return texto

        match = re.search(r"(https?:)?//[^\s'\"),]+", texto)
        if match:
            url = match.group(0)
            if url.startswith("//"):
                url = "https:" + url
            return url

        return ""

    def oferta_passa_filtros(self, oferta, config):
        if not oferta.get("nome"):
            return False

        comissao_minima = self.config_numero(config, "shopee_ofertas_comissao_minima")
        desconto_minimo = self.config_numero(config, "shopee_ofertas_desconto_minimo")
        vendas_minimas = self.config_numero(config, "shopee_ofertas_vendas_minimas")
        preco_minimo = self.config_numero(config, "shopee_ofertas_preco_minimo")
        preco_maximo = self.config_numero(config, "shopee_ofertas_preco_maximo")
        avaliacao_minima = self.config_numero(config, "shopee_ofertas_avaliacao_minima")

        if comissao_minima and oferta.get("comissao", 0) < comissao_minima:
            return False
        if desconto_minimo and oferta.get("desconto", 0) < desconto_minimo:
            return False
        if vendas_minimas and oferta.get("vendas", 0) < vendas_minimas:
            return False
        if preco_minimo and oferta.get("preco", 0) < preco_minimo:
            return False
        if preco_maximo and oferta.get("preco", 0) > preco_maximo:
            return False
        if avaliacao_minima and oferta.get("avaliacao", 0) < avaliacao_minima:
            return False

        tipo_busca = str(getattr(config, "shopee_ofertas_tipo_busca", "geral") or "geral")
        categorias_selecionadas = getattr(config, "shopee_ofertas_categorias", None) or []
        if tipo_busca != "categoria":
            categorias_selecionadas = []
        if not produto_pertence_as_categorias(oferta.get("nome"), categorias_selecionadas):
            return False

        return True

    def config_numero(self, config, nome):
        return self.converter_numero(getattr(config, nome, 0) or 0) or 0.0

    STATUS_PEDIDO_INVALIDOS = {"CANCELLED", "UNPAID"}

    def _comissao_conversao_valida(self, conversao, comissao):
        """
        Camada de segurança: o relatório CSV baixado direto do painel da
        Shopee confirma que, quando um pedido está Cancelado/Não pago, a
        comissão dele já vem zerada (em todas as colunas, não só na
        "líquida"). Se TODOS os pedidos dentro de uma conversão já estão
        nesse estado, forçamos a comissão para 0 aqui também - útil caso a
        API ainda não tenha refletido essa atualização no campo de
        comissão no momento da consulta. Se houver mistura de status
        (alguns válidos, outros não) ou não tivermos essa informação,
        mantemos o valor retornado pela API sem alterar, para não
        arriscar um desconto indevido sem dado suficiente.
        """

        pedidos = conversao.get("orders") if isinstance(conversao, dict) else None
        if not isinstance(pedidos, list) or not pedidos:
            return comissao

        status_pedidos = [
            str((pedido or {}).get("orderStatus") or "").strip().upper()
            for pedido in pedidos
            if isinstance(pedido, dict)
        ]
        if status_pedidos and all(status in self.STATUS_PEDIDO_INVALIDOS for status in status_pedidos):
            return 0.0

        return comissao

    # Mapeia os Sub IDs "crus" retornados pela Shopee para as categorias de
    # origem usadas nos relatorios (aba Indicadores, grafico e email diario).
    # Regras definidas pelo negocio:
    # - comeca com "user"      -> "cash-b" (link gerado por usuario da cash-b)
    # - e so traco(s) ("-")    -> "redes sociais" (link sem subid dedicado)
    # - contem "siteconversor" -> "siteconversor"
    # - contem "grupoofertas"  -> "grupoofertas"
    # Sub IDs que nao batem com nenhuma regra continuam aparecendo com o
    # proprio valor, para nao esconder origem nao mapeada ainda.
    def classificar_sub_id_relatorio(self, sub_id):
        texto = str(sub_id or "").strip()
        if not texto or texto == "sem_subid":
            return "sem_subid"

        if re.fullmatch(r"-+", texto):
            return "redes sociais"

        minusculo = texto.lower()
        if minusculo.startswith("user"):
            return "cash-b"
        if "siteconversor" in minusculo:
            return "siteconversor"
        if "grupoofertas" in minusculo:
            return "grupoofertas"

        return texto

    def agrupar_indicadores(self, conversoes):
        grupos = {}
        for conversao in conversoes:
            sub_ids = self.extrair_sub_ids_relatorio(conversao)
            if not sub_ids:
                sub_ids = ["sem_subid"]

            comissao = self.extrair_primeiro_numero(
                conversao,
                (
                    "netCommission",
                    "grossCommission",
                    "cappedCommission",
                    "totalCommission",
                    "sellerCommission",
                    "commission",
                    "commissionAmount",
                    "estCommission",
                ),
            )
            comissao = self._comissao_conversao_valida(conversao, comissao)
            valor = self.extrair_primeiro_numero(
                conversao,
                ("orderAmount", "purchaseAmount", "salesAmount", "itemPrice", "actualAmount"),
            )

            for sub_id in sub_ids:
                categoria = self.classificar_sub_id_relatorio(sub_id)
                item = grupos.setdefault(
                    categoria,
                    {"sub_id": categoria, "vendas": 0, "comissao": 0.0, "valor": 0.0},
                )
                item["vendas"] += 1
                item["comissao"] += comissao
                item["valor"] += valor

        linhas = sorted(
            grupos.values(),
            key=lambda item: (item["vendas"], item["comissao"], item["sub_id"]),
            reverse=True,
        )

        return {
            "linhas": linhas,
            "totais": {
                "vendas": sum(item["vendas"] for item in linhas),
                "comissao": sum(item["comissao"] for item in linhas),
                "valor": sum(item["valor"] for item in linhas),
            },
            "debug": {
                "conversoes": len(conversoes),
                "campos_conversao": self.listar_campos_amostra(conversoes),
            },
        }

    def extrair_sub_ids_relatorio(self, conversao):
        encontrados = []
        for nome in (
            "utmContent",
        ):
            valor = conversao.get(nome) if isinstance(conversao, dict) else None
            if valor:
                encontrados.extend(self.normalizar_sub_id_valor(valor))

        limpos = []
        for valor in encontrados:
            valor = str(valor or "").strip()
            if valor and valor not in limpos:
                limpos.append(valor)
        return limpos

    def normalizar_sub_id_valor(self, valor):
        if isinstance(valor, list):
            resultados = []
            for item in valor:
                resultados.extend(self.normalizar_sub_id_valor(item))
            return resultados
        if isinstance(valor, dict):
            resultados = []
            for item in valor.values():
                resultados.extend(self.normalizar_sub_id_valor(item))
            return resultados

        texto = str(valor or "").strip()
        if not texto:
            return []

        for separador in ("|", ";", ","):
            if separador in texto:
                return [
                    parte.strip()
                    for parte in texto.split(separador)
                    if parte.strip()
                ]

        return [texto]

    def listar_campos_amostra(self, linhas):
        for linha in linhas or []:
            if isinstance(linha, dict):
                return sorted(linha.keys())
        return []

    def extrair_primeiro_numero(self, objeto, nomes):
        if isinstance(objeto, dict):
            for nome in nomes:
                if nome in objeto:
                    numero = self.converter_numero(objeto.get(nome))
                    if numero is not None:
                        return numero
            for valor in objeto.values():
                numero = self.extrair_primeiro_numero(valor, nomes)
                if numero is not None:
                    return numero
        elif isinstance(objeto, list):
            total = 0.0
            achou = False
            for item in objeto:
                numero = self.extrair_primeiro_numero(item, nomes)
                if numero is not None:
                    total += numero
                    achou = True
            if achou:
                return total

        return 0.0

    def extrair_numeros_por_campos(self, objeto, nomes):
        encontrados = []
        if isinstance(objeto, dict):
            for nome in nomes:
                if nome in objeto:
                    encontrados.extend(self.numeros_de_valor(objeto.get(nome)))
            for valor in objeto.values():
                encontrados.extend(self.extrair_numeros_por_campos(valor, nomes))
        elif isinstance(objeto, list):
            for item in objeto:
                encontrados.extend(self.extrair_numeros_por_campos(item, nomes))

        limpos = []
        for numero in encontrados:
            if numero and numero > 0 and numero not in limpos:
                limpos.append(numero)
        return limpos

    def numeros_de_valor(self, valor):
        if isinstance(valor, dict):
            numeros = []
            for item in valor.values():
                numeros.extend(self.numeros_de_valor(item))
            return numeros
        if isinstance(valor, list):
            numeros = []
            for item in valor:
                numeros.extend(self.numeros_de_valor(item))
            return numeros
        numero = self.converter_numero(valor)
        return [numero] if numero is not None else []

    def converter_numero(self, valor):
        if isinstance(valor, (int, float)):
            return float(valor)
        if isinstance(valor, str):
            texto = valor.strip().replace("R$", "").replace(" ", "")
            if "," in texto and "." in texto:
                texto = texto.replace(".", "").replace(",", ".")
            else:
                texto = texto.replace(",", ".")
            try:
                return float(texto)
            except ValueError:
                return None
        return None

    def normalizar_url_origem(self, link_original):
        """
        Prepara a URL do produto para ser enviada a API de conversao
        (generateShortLink). NAO remove parametros da URL (utm_source,
        mmp_pid etc.): testes confirmaram que a Shopee precisa desses
        parametros para gerar um link de afiliado valido - removendo-os,
        o link gerado cai na pagina de erro "navegador nao aceito" mesmo
        para quem clica com um navegador normal, e nao so para bots.
        """
        link = self.limpar_link(link_original)

        if self.eh_link_encurtado(link):
            link_expandido = self.expandir_link_encurtado(link)
            if link_expandido:
                link = self.limpar_link(link_expandido)

        return link

    def limpar_link(self, link):
        link = str(link or "").strip()
        link = link.replace("\u202a", "").replace("\u202c", "")
        link = link.strip(" \t\r\n\"'<>[](){}")
        link = re.sub(r"[.,;:!?]+$", "", link)
        return link

    def eh_link_encurtado(self, link):
        host = urllib.parse.urlparse(link).netloc.lower()
        return (
            "s.shopee.com.br" in host
            or "shope.ee" in host
            or "shoope.top" in host
        )

    def expandir_link_encurtado(self, link, tentativas=4):
        """
        Segue o redirecionamento de um link encurtado ate chegar na URL real
        do produto (com todos os parametros originais, necessarios para a
        Shopee gerar um link de afiliado valido).

        A Shopee bloqueia requisicoes "simples" (sem fingerprint de
        navegador real) para varios dos seus links curtos, mostrando uma
        pagina de erro ("navegador nao aceito" ou uma pagina de
        verificacao) em vez de seguir para o produto. Por isso, SEMPRE que
        houver um navegador disponivel (ver definir_contexto_navegador),
        usamos ele primeiro para resolver o link - e so caimos para uma
        requisicao simples (urllib) se o navegador nao estiver disponivel
        ou falhar.
        """

        if link in self._cache_links_resolvidos:
            return self._cache_links_resolvidos[link]

        resultado = self._expandir_link_encurtado_sem_cache(link, tentativas=tentativas)

        if len(self._cache_links_resolvidos) > 500:
            self._cache_links_resolvidos.clear()
        self._cache_links_resolvidos[link] = resultado

        return resultado

    def _expandir_link_encurtado_sem_cache(self, link, tentativas=4):
        if self._contexto_navegador:
            resultado_navegador = self._resolver_link_via_navegador(link)
            if resultado_navegador:
                url_final, _ = resultado_navegador
                if url_final:
                    if not self._eh_pagina_de_erro_shopee(url_final):
                        return url_final

                    # Caiu numa pagina de bloqueio/verificacao da Shopee; o
                    # destino real do produto costuma vir no parametro
                    # "next" dessa mesma URL.
                    url_next = self._extrair_url_de_parametro_next(url_final)
                    if url_next:
                        return url_next

        return self._expandir_link_encurtado_via_urllib(link, tentativas=tentativas)

    def _expandir_link_encurtado_via_urllib(self, link, tentativas=4):
        """
        Segue o redirecionamento de um link encurtado via requisicao HTTP
        simples. Alem do redirecionamento HTTP padrao (301/302, que o
        urllib ja segue sozinho), tambem procuramos redirecionamento via
        JavaScript ou <meta http-equiv="refresh"> no HTML de cada pagina,
        ate um limite de saltos. Usado como ultimo recurso, quando nao ha
        navegador disponivel para resolver o link (ver expandir_link_encurtado).
        """

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        }

        link_atual = link
        ultimo_link_resolvido = None

        for _ in range(max(1, tentativas)):
            try:
                request = urllib.request.Request(link_atual, headers=headers, method="GET")
                opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
                with opener.open(request, timeout=self.timeout) as response:
                    link_resolvido = response.geturl()
                    try:
                        corpo = response.read(300000).decode("utf-8", errors="ignore")
                    except Exception:
                        corpo = ""
            except Exception as e:
                self._log("Nao consegui expandir link encurtado; vou tentar a URL original.")
                self._log(str(e))
                return ultimo_link_resolvido

            ultimo_link_resolvido = link_resolvido
            proximo = self._extrair_redirecionamento_html(corpo, link_resolvido)

            if not proximo or proximo == link_resolvido or proximo == link_atual:
                return link_resolvido

            link_atual = proximo

        return ultimo_link_resolvido

    def _extrair_redirecionamento_html(self, html, url_base):
        """Procura um redirecionamento via meta refresh ou JavaScript no HTML da pagina."""

        if not html:
            return None

        match = re.search(
            r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^"\']*url=([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r'(?:window\.location(?:\.href)?|location\.href|location\.replace)\s*'
                r'[=(]\s*["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )

        if not match:
            return None

        destino = match.group(1).strip()
        if not destino:
            return None

        try:
            return urllib.parse.urljoin(url_base, destino)
        except Exception:
            return None

    def remover_parametros_desnecessarios(self, link):
        parsed = urllib.parse.urlparse(link)

        if not parsed.scheme or not parsed.netloc:
            return link

        host = parsed.netloc.lower()
        if "shopee.com.br" not in host and "shopee.com" not in host:
            return link

        return urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            "",
            "",
            "",
        ))

    def montar_payload_generate_short_link(self, link_original):
        url = json.dumps(link_original, ensure_ascii=False)

        sub_ids = self.validar_sub_ids()

        sub_ids_graphql = ""
        if sub_ids:
            sub_ids_graphql = ",subIds:" + json.dumps(sub_ids, ensure_ascii=False)

        query = (
            "mutation{"
            "generateShortLink(input:{"
            f"originUrl:{url}"
            f"{sub_ids_graphql}"
            "}){"
            "shortLink"
            "}"
            "}"
        )

        return json.dumps(
            {"query": query},
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def validar_sub_ids(self):
        sub_ids = [
            str(sub_id).strip()
            for sub_id in self.sub_ids
            if str(sub_id).strip()
        ]

        if len(sub_ids) > 5:
            raise Exception("A API Shopee aceita no máximo 5 Sub IDs.")

        invalidos = [
            sub_id
            for sub_id in sub_ids
            if not re.fullmatch(r"[A-Za-z0-9]{1,100}", sub_id)
        ]

        if invalidos:
            raise Exception(
                "Sub ID inválido. Use apenas letras sem acento e números, sem espaços ou símbolos. "
                f"Revise: {', '.join(invalidos)}"
            )

        return sub_ids

    def gerar_assinatura(self, timestamp, payload):
        fator = f"{self.app_id}{timestamp}{payload}{self.secret}"
        return hashlib.sha256(fator.encode("utf-8")).hexdigest()

    def extrair_short_link(self, resposta):
        dados = json.loads(resposta)

        erros = dados.get("errors")
        if erros:
            raise Exception(f"Erro retornado pela API Shopee: {erros}")

        data = dados.get("data") or {}
        resultado = data.get("generateShortLink") or {}

        return (resultado.get("shortLink") or "").strip()

    def fechar(self):
        if self._contexto_navegador is not None:
            # Se o contexto pertence a um navegador que o usuario abriu (modo
            # CDP), NAO fechamos - senao fecharia o navegador dele. Apenas
            # soltamos a referencia.
            if not getattr(self, "_contexto_externo", False):
                try:
                    self._contexto_navegador.close()
                except Exception:
                    pass
            self._contexto_navegador = None
