"""O que o assistente "sabe": o texto das páginas públicas do site, renderizado pelas
mesmas views que o site usa.

Renderizar a view (em vez de copiar o texto das páginas para um arquivo à parte) é o
que garante que o assistente nunca contradiz o site: os pisos de cashback, o saque
mínimo e o "até X%" chegam aqui pelo mesmo contexto que preenche a página. Mudou um
número no .env ou um parágrafo no template, o assistente passa a responder com ele
na próxima vez que a base for montada, sem ninguém lembrar de atualizar um prompt.

A base é dividida em duas partes por causa do cache de prompt da API:
- montar_base(): o texto das páginas. Muda raramente, vai em cache (barato).
- dados_do_momento(): data/hora atual e campanha em andamento. Muda a todo momento,
  por isso fica depois do trecho em cache - senão o cache seria perdido a cada minuto.
"""

import re
from html.parser import HTMLParser

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from paginas import views as paginas_views
from pedidos.models import CampanhaCashback

# Páginas que entram na base, na ordem em que aparecem para o modelo. Ficaram de fora
# de propósito: Fale conosco (é só um formulário), cookies (nada que um usuário
# pergunte no WhatsApp) e a página de links da bio (navegação, sem conteúdo).
PAGINAS = [
    ("Perguntas frequentes", paginas_views.faq, "faq"),
    ("Regras do cashback", paginas_views.regras_cashback, "regras_cashback"),
    ("A cash-b é confiável?", paginas_views.e_confiavel, "e_confiavel"),
    ("Cashback na Shopee vale a pena?", paginas_views.cashback_vale_a_pena, "cashback_vale_a_pena"),
    (
        "Como saber se um site de cashback é confiável",
        paginas_views.checklist_cashback_confiavel,
        "checklist_cashback_confiavel",
    ),
    ("Termos de uso", paginas_views.termos_de_uso, "termos_de_uso"),
    ("Política de privacidade", paginas_views.privacidade, "privacidade"),
]

# Endereço público do site, para o assistente poder mandar o link da página que
# responde a dúvida (o WhatsApp não tem como "clicar" num link relativo).
ENDERECO_SITE = "https://cash-b.com"

DIAS_DA_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


class _ExtratorDeTexto(HTMLParser):
    """Tira o texto do conteúdo principal da página (a <div class="container"> do
    accounts/base.html), deixando de fora o que não é conteúdo: o link de "voltar",
    formulários, botões, scripts e estilos.

    Mantém um mínimo de estrutura em texto para o modelo entender a página: títulos
    viram "#", itens de lista viram "-" e a pergunta de cada item do FAQ vira "P:"."""

    IGNORAR = {"script", "style", "form", "button", "noscript", "svg"}
    QUEBRA_ANTES = {"p", "div", "ul", "ol", "table", "tr", "details", "section", "br"}
    PREFIXOS = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "### ", "li": "- ", "summary": "P: "}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []
        self._profundidade_container = 0  # >0 enquanto estamos dentro do container
        self._ignorando = 0  # >0 enquanto estamos dentro de algo a ignorar

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get("class") or "").split()
        if tag == "div" and self._profundidade_container:
            self._profundidade_container += 1
        elif tag == "div" and "container" in classes:
            self._profundidade_container = 1
            return
        if not self._profundidade_container:
            return
        if self._ignorando or tag in self.IGNORAR or "nav-topo" in classes:
            # Elementos vazios (<br>, <input>) não têm tag de fechamento: só os que
            # fecham entram na contagem, senão a contagem nunca volta a zero.
            if tag not in {"br", "input", "img", "hr", "meta", "link"}:
                self._ignorando += 1
            return
        if tag in self.PREFIXOS:
            self.partes.append("\n" + self.PREFIXOS[tag])
        elif tag in self.QUEBRA_ANTES:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if not self._profundidade_container:
            return
        if self._ignorando:
            if tag not in {"br", "input", "img", "hr", "meta", "link"}:
                self._ignorando -= 1
            if tag == "div":
                self._profundidade_container -= 1
            return
        if tag == "div":
            self._profundidade_container -= 1
        if tag in self.PREFIXOS or tag in self.QUEBRA_ANTES:
            self.partes.append("\n")

    def handle_data(self, data):
        if self._profundidade_container and not self._ignorando:
            # Quebra de linha dentro do texto é só formatação do template; as quebras
            # que importam vêm das tags (ver handle_starttag/handle_endtag).
            self.partes.append(re.sub(r"\s+", " ", data))

    def texto(self) -> str:
        bruto = "".join(self.partes)
        linhas = [re.sub(r" +", " ", linha).strip() for linha in bruto.split("\n")]
        texto = "\n".join(linhas)
        texto = re.sub(r"^(#+ |- |P: )\s*$", "", texto, flags=re.MULTILINE)  # prefixo órfão
        return re.sub(r"\n{3,}", "\n\n", texto).strip()


def html_para_texto(html: str) -> str:
    extrator = _ExtratorDeTexto()
    extrator.feed(html)
    extrator.close()
    return extrator.texto()


def _renderizar(view) -> str:
    # O template monta links absolutos com o host da requisição, que o Django valida
    # contra ALLOWED_HOSTS - então a requisição simulada usa um host que o site aceita
    # (o domínio de produção, ou localhost em desenvolvimento).
    host = next((h.lstrip(".") for h in settings.ALLOWED_HOSTS if h != "*"), "localhost")
    request = RequestFactory().get("/", HTTP_HOST=host, secure=True)
    request.user = AnonymousUser()
    resposta = view(request)
    return resposta.content.decode(resposta.charset or "utf-8")


def montar_base() -> str:
    """Texto de todas as PAGINAS, cada uma sob um título. É o trecho grande e estável
    do prompt (vai em cache) - não coloque nada aqui que mude a cada minuto."""
    secoes = []
    for titulo, view, nome_url in PAGINAS:
        endereco = ENDERECO_SITE + reverse(nome_url)
        texto = html_para_texto(_renderizar(view))
        secoes.append(f'<pagina titulo="{titulo}" endereco="{endereco}">\n{texto}\n</pagina>')
    return "\n\n".join(secoes)


def _formatar_momento(momento) -> str:
    local = timezone.localtime(momento)
    return f"{local.strftime('%d/%m/%Y')} às {local.strftime('%H:%M')}"


def descrever_campanha(agora=None) -> str:
    """Campanha da cash-b em andamento ou anunciada, pela mesma regra da faixa do site
    (CampanhaCashback.para_faixa): o assistente nunca fala de uma campanha diferente da
    que o site mostra e o sistema paga."""
    faixa = CampanhaCashback.para_faixa(agora=agora)
    if faixa is None:
        return "Nenhuma campanha de cashback extra da cash-b em andamento nem anunciada."
    campanha = faixa["campanha"]
    inicio = _formatar_momento(campanha.inicio)
    fim = _formatar_momento(campanha.fim) if campanha.fim else "sem data de término definida"
    situacao = "Campanha EM ANDAMENTO" if faixa["ativa"] else "Próxima campanha (ainda não começou)"
    return (
        f"{situacao}: {campanha.percentual_extra}% a mais de cashback nas compras feitas "
        f"de {inicio} até {fim} (horário de Brasília). Vale para a data da compra, não "
        "para a data em que o pedido aparece no painel."
    )


def dados_do_momento(agora=None) -> str:
    """Trecho que muda a todo momento: data de hoje e campanha. Vai depois do trecho em
    cache. Os números das regras (pisos, saque mínimo) já estão nas páginas; ficam
    repetidos aqui para o modelo não precisar garimpá-los no meio do texto."""
    agora = agora or timezone.now()
    local = timezone.localtime(agora)
    return "\n".join([
        f"Agora: {DIAS_DA_SEMANA[local.weekday()]}, {_formatar_momento(agora)} (horário de Brasília).",
        f"Cashback mínimo garantido: {_numero(settings.CASHBACK_MINIMO_VENDA_DIRETA)}% em venda direta e "
        f"{_numero(settings.CASHBACK_MINIMO_VENDA_INDIRETA)}% em venda indireta.",
        f"Saque mínimo: R$ {_numero(settings.SAQUE_VALOR_MINIMO, casas=2)}, via Pix, do saldo já liberado.",
        descrever_campanha(agora),
    ])


def _numero(valor, casas=None) -> str:
    """Número no formato brasileiro (vírgula decimal): 1.6 -> "1,6", 20 -> "20,00"."""
    texto = f"{float(valor):.{casas}f}" if casas is not None else f"{float(valor):g}"
    return texto.replace(".", ",")
