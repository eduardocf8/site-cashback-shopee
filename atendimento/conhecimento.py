"""Base de conhecimento do agente, montada do mesmo conteúdo do site (appfiliado.com.br).
Mudou preço, plano, link ou pergunta frequente no site? O agente passa a saber sozinho."""

from functools import lru_cache

from django.conf import settings

from landing import planos
from landing import recursos as paginas
from landing import views as site
from licencas import api_shopee


def _paginas_das_ferramentas() -> str:
    partes = []
    for codigo, montar in paginas.PAGINAS.items():
        if codigo == "carrosseis":
            continue  # saiu do site: o Estúdio Instagram toma o lugar
        p = montar()
        linhas = [f"### {p['nome']} (página: https://appfiliado.com.br/{p['slug']}/)", p["h1"], p["texto"]]
        if planos.em_breve(codigo):
            linhas.append("EM BREVE: ainda não está à venda. Não tem preço nem planos definidos ainda: não invente preço, "
                          "data de lançamento nem diferença entre planos.")
        if p.get("incluso"):
            linhas.append("Incluído em todos os planos (não é vendido à parte).")
        for g in p["grupos"]:
            linhas.append(f"- {g['titulo']}: " + " ".join(
                f"{i['nome']}: {i['texto']}" + (f" (só no {i['plano']})" if i.get("plano") else "") for i in g["itens"]))
        if p.get("tabela"):
            linhas.append("Standard x Premium: " + "; ".join(
                f"{rotulo}: Standard {_valor(a)}, Premium {_valor(b)}" for rotulo, a, b in p["tabela"]))
        for pergunta, resposta in p.get("perguntas", []):
            linhas.append(f"P: {pergunta} R: {resposta}")
        partes.append("\n".join(linhas))
    return "\n\n".join(partes)


def _valor(v) -> str:
    return {True: "sim", False: "não"}.get(v, str(v)) if isinstance(v, bool) else str(v)


def _precos() -> str:
    linhas = ["Preços por mês (o plano anual sai com 17% de desconto, escolhido no checkout):"]
    for m in planos.a_venda():
        resumo = site.RESUMOS[m]
        linhas.append(f"\n{planos.NOMES[m]}: {resumo['frase']}")
        for nivel in (0, 1):
            itens = "; ".join(resumo["itens"][nivel])
            linhas.append(f"- {planos.NIVEIS[nivel]}: {planos.brl(planos.PRECOS[m][nivel])}/mês. {itens}. "
                          f"Checkout: {_link(planos.LINKS[f'{m}{nivel}'])}")
        if resumo.get("comuns"):
            linhas.append("- Nos dois planos: " + "; ".join(resumo["comuns"]))
    linhas.append("\nIncluídos em todos os planos: " + "; ".join(f"{n} ({f})" for _, n, f in site.INCLUSOS))
    breves = [m for m in planos.modulos() if planos.em_breve(m)]
    if breves:
        linhas.append("\nEm breve (ainda não estão à venda, sem preço e sem planos definidos; quem perguntar pode conhecer "
                      "os recursos na página de cada um): " + "; ".join(f"{planos.NOMES[m]} ({site.RESUMOS[m]['frase']})" for m in breves)
                      + ". O antigo Gerador de carrosséis não é mais vendido: o Estúdio Instagram toma o lugar dele.")
    linhas.append("\nPacotes (todos os módulos do pacote no mesmo plano, Standard ou Premium, numa assinatura só). "
                  "Fora dos pacotes não há desconto por juntar módulos: quem quiser outra combinação assina cada módulo separado.")
    for p in planos.pacotes():
        linhas.append(f"\n{p['nome']} ({' + '.join(p['modulos'])}): {p['frase']}")
        if p["em_breve"]:
            linhas.append("- Em breve: chega com o lançamento do Estúdio Instagram e das Automações Instagram (sem preço ainda).")
        for n in p["niveis"]:
            linhas.append(f"- {n['nivel']}: {planos.brl(n['preco'])}/mês (separado sairia {planos.brl(n['separado'])}). "
                          f"Checkout: {_link(n['link'])}")
    linhas.append("\nEmissor NFS-e (só para afiliado pessoa jurídica, MEI ou Simples Nacional, com certificado digital A1). "
                  "Emite as notas fiscais dos vendedores que pagaram comissão extra, direto do relatório mensal da Shopee. "
                  "O plano é pela quantidade de notas emitidas no mês:")
    for (nome, preco), link in zip(planos.NOTAS, planos.LINKS_NOTAS.values()):
        linhas.append(f"- {nome}: {planos.brl(preco)}/mês. Checkout: {link}")
    linhas.append("Página do emissor: https://appfiliado.com.br/emissao-de-notas/")
    for pergunta, resposta in site.PERGUNTAS_NOTAS:
        linhas.append(f"P: {pergunta} R: {resposta}")
    return "\n".join(linhas)


def _link(link: str) -> str:
    return link or "ainda não está à venda (se a pessoa quiser assinar, chame o humano)"


def _api_shopee() -> str:
    passos = "\n".join(f"{i}. {t}: {d}" for i, (t, d) in enumerate(api_shopee.PASSOS, 1))
    campos = "; ".join(f"{c}: {v}" for c, v in api_shopee.CAMPOS_FORMULARIO)
    return (f"{api_shopee.RESUMO}\nExceção: o Emissor NFS-e não precisa da API da Shopee, porque usa o Relatório Mensal "
            "que o afiliado baixa na Central do Afiliado e envia no painel.\nPasso a passo:\n{passos}\nComo preencher o formulário: {campos}.\n"
            f"Formulário da Shopee: {api_shopee.URL_FORMULARIO}\nPágina Open API do afiliado: {api_shopee.URL_OPEN_API}")


@lru_cache(maxsize=1)
def texto() -> str:
    perguntas = "\n".join(f"P: {p} R: {r}" for p, r in site.perguntas())
    return f"""# O que é o Appfiliado
Ferramentas para afiliados da Shopee num painel só (app.appfiliado.com.br): encontrar ofertas, divulgar no WhatsApp,
no link na bio e no Instagram, acompanhar os resultados e emitir notas fiscais. Site: https://appfiliado.com.br
O Appfiliado é independente e não tem vínculo oficial com a Shopee. Pagamento pelo checkout seguro da Zouti, com Pix, boleto ou cartão de crédito (as condições de parcelamento aparecem no próprio checkout).
Depois de pagar, a pessoa recebe no e-mail o link para criar a senha e entrar no painel.
{("Suporte por e-mail: " + settings.APPFILIADO_EMAIL_SUPORTE) if settings.APPFILIADO_EMAIL_SUPORTE else ""}

# Resultados por este WhatsApp (para quem já assina)
Quem assina pode vincular este número à conta do Appfiliado (no painel, em Configurações > Resultados no WhatsApp: gera
um código e manda aqui "VINCULAR" e o código). Depois disso, mandando só a palavra, recebe na hora: "resultados" (ontem,
últimos 7 dias e o mês), "metas", "vendas" (produtos vendidos ontem), "top" (mais vendidos dos últimos 7 dias),
"validada" (comissão validada de hoje, o único número que a Shopee libera no mesmo dia),
"atualizar" (busca agora os dados mais novos na Shopee), "desvincular" e "comandos" (a lista). Esses comandos são respondidos sozinhos pelo sistema, não por você: se a pessoa
perguntar dos números dela, explique como vincular e quais comandos mandar. Nunca invente números de vendas.

# Antes de tudo: a API da Shopee
{_api_shopee()}

# Planos, preços e links de checkout
{_precos()}

# Perguntas frequentes do site
{perguntas}

# Cada ferramenta em detalhe
{_paginas_das_ferramentas()}
"""
