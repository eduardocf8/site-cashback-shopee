"""Guia em PDF do cadastro dos produtos do Appfiliado na Zouti.

Uso (na raiz do repositório): python3 marketing/appfiliado/gerar_guia_zouti.py
Sai em marketing/appfiliado/guia-zouti.pdf. Preços, códigos e textos ficam aqui embaixo."""

import html
import itertools
import math
from pathlib import Path

PASTA = Path(__file__).resolve().parent
E = html.escape

PRECOS = {  # (Standard, Premium)
    "bot": (49.90, 89.90), "site": (22.90, 35.90), "carrosseis": (19.90, 35.90),
}
NOMES = {"bot": "Bot de WhatsApp", "site": "Meu site", "carrosseis": "Gerador de carrosséis"}
CODIGOS = {
    ("bot", 0): "whatsapp", ("bot", 1): "whatsapp_premium",
    ("site", 0): "site", ("site", 1): "site_sem_marca",
    ("carrosseis", 0): "carrosseis", ("carrosseis", 1): "carrosseis_premium",
}
LINHA = {
    ("bot", 0): "até 3 grupos, 30 ofertas por dia em cada, modo campanha e alerta de preço (10 produtos)",
    ("bot", 1): "até 20 grupos, 100 ofertas por dia em cada, copiar ofertas, IA e alerta de preço (50 produtos)",
    ("site", 0): "até 3 botões, conversor e vitrine de ofertas",
    ("site", 1): "até 10 botões, produtos que você escolher e sem a nossa marca",
    ("carrosseis", 0): "3 por dia, com roteiro por IA",
    ("carrosseis", 1): "10 por dia, modelos premium, cores livres e foto própria",
}
DESCRICOES = {
    ("bot", 0): ("Ofertas da Shopee enviadas no automático para os seus grupos, sempre com o seu link de afiliado.",
                 ["Até 3 grupos e canais", "Até 30 ofertas por dia em cada grupo, com intervalo a partir de 15 minutos",
                  "Busca por palavra-chave, loja ou categoria, com filtros de comissão, desconto, preço e avaliação",
                  "Horário e dias de envio, Sub ID por grupo e modo simulação para testar antes",
                  "Modo campanha: no 11.11, na Black Friday e nas outras datas, o bot muda sozinho o ritmo, o texto e o cupom",
                  "Alerta de preço: acompanha até 10 produtos e avisa por e-mail e nos grupos quando baixarem (conferência a cada 1 hora ou mais)"],
                 "Precisa de: um número de WhatsApp (conecta pelo QR Code) e a conta de afiliado da Shopee."),
    ("bot", 1): ("Tudo do Standard, com mais alcance e mais automação.",
                 ["Até 20 grupos e canais", "Até 100 ofertas por dia em cada grupo, com intervalo a partir de 3 minutos",
                  "Copia as ofertas de outros grupos e canais e troca pelo seu link de afiliado",
                  "Revisão do texto com IA (corrige o português sem mexer em link, preço ou cupom)",
                  "Alerta de preço com até 50 produtos, conferidos a cada 15 minutos"],
                 "Precisa de: um número de WhatsApp (conecta pelo QR Code) e a conta de afiliado da Shopee."),
    ("site", 0): ("Seu link na bio (seunome.appfiliado.com.br) com vitrine de ofertas e conversor de links.",
                  ["Até 3 botões, ícones das redes sociais, cores e estilo à sua escolha",
                   "Conversor: o visitante cola um link da Shopee e compra pelo seu link de afiliado",
                   "Vitrine com as últimas ofertas do bot ou com uma busca na Shopee",
                   "Cliques contados e Sub ID próprio para ver as vendas do site em Resultados"], ""),
    ("site", 1): ("Tudo do Standard, com mais espaço e a sua marca no lugar da nossa.",
                  ["Até 10 botões", "Vitrine com os produtos que você escolher",
                   "Sem a marca \"Feito com Appfiliado\" no rodapé"], ""),
    ("carrosseis", 0): ("Cole um link da Shopee e receba um carrossel pronto para o Instagram.",
                        ["3 carrosséis por dia", "Roteiro dos slides, legenda e hashtags escritos por IA",
                         "Editor para ajustar os textos e baixar as imagens",
                         "Seu link de afiliado com Sub ID próprio para ver as vendas do Instagram"], ""),
    ("carrosseis", 1): ("Tudo do Standard, com mais volume e mais liberdade de criação.",
                        ["10 carrosséis por dia", "Modelos premium, cores livres e foto própria do produto",
                         "IA reescrevendo os slides que você quiser", "Salve o seu padrão visual para os próximos carrosséis"], ""),
}
ARTES_AVULSO = {("bot", 0): "bot-standard", ("bot", 1): "bot-premium", ("site", 0): "site-standard",
                ("site", 1): "site-premium", ("carrosseis", 0): "carrosseis-standard", ("carrosseis", 1): "carrosseis-premium"}
NOTAS = [("100", 17.90, "notas"), ("500", 49.90, "notas_500"), ("2.000", 89.90, "notas_2000"),
         ("5.000", 129.90, "notas_5000"), ("10.000", 169.90, "notas_10000"), (None, 229.90, "notas_ilimitado")]
ARTES_NOTAS = ["nfse-100", "nfse-500", "nfse-2000", "nfse-5000", "nfse-10000", "nfse-ilimitado"]
NIVEL = ("Standard", "Premium")


def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def com_desconto(total: float, fator: float) -> float:
    return math.floor(total * fator - 0.90 + 1e-9) + 0.90  # arredonda para baixo terminando em ,90


def produtos() -> list[dict]:
    lista = []
    for (modulo, nivel), (frase, itens, precisa) in DESCRICOES.items():
        mensal = PRECOS[modulo][nivel]
        lista.append({"grupo": "Avulsos", "nome": f"{NOMES[modulo]} {NIVEL[nivel]}", "mensal": mensal,
                      "codigos": CODIGOS[(modulo, nivel)], "arte": ARTES_AVULSO[(modulo, nivel)],
                      "frase": frase, "itens": itens, "precisa": precisa})
    for (faixa, preco, codigo), arte in zip(NOTAS, ARTES_NOTAS):
        nome = "Emissor NFS-e ilimitada" if faixa is None else f"Emissor NFS-e até {faixa} notas"
        destaque = "Notas ilimitadas por mês" if faixa is None else f"Até {faixa} notas por mês"
        lista.append({"grupo": "Emissor NFS-e", "nome": nome, "mensal": preco, "codigos": codigo, "arte": arte,
                      "frase": "As notas fiscais dos vendedores que pagaram comissão extra, direto do Relatório Mensal da Shopee.",
                      "itens": [destaque, "Envie o relatório e sai uma nota por loja, sem digitar nada, e mais a nota da Shopee",
                                "Cada vendedor recebe a nota por e-mail, com PDF e XML, no horário que você escolher",
                                "Emitidas no Emissor Nacional do governo, com ambiente de testes e cancelamento pelo painel",
                                "As notas de teste não contam, e a cancelada libera a vaga do mês"],
                      "precisa": "Precisa de: empresa MEI ou Simples Nacional e certificado digital A1 (e-CNPJ)."})
    modulos = list(PRECOS)
    for nivel, nome in ((0, "Combo Standard"), (1, "Combo Premium")):
        total = sum(PRECOS[m][nivel] for m in modulos)
        lista.append({"grupo": "Combos fechados", "nome": nome, "mensal": com_desconto(total, 0.80),
                      "codigos": ", ".join(CODIGOS[(m, nivel)] for m in modulos), "arte": f"combo-{'premium' if nivel else 'standard'}",
                      "frase": f"Bot de WhatsApp + Meu site + Gerador de carrosséis, todos no plano {NIVEL[nivel]}, 20% mais barato que separado.",
                      "itens": [f"{NOMES[m]}: {LINHA[(m, nivel)]}" for m in modulos] + ["Uma assinatura só"], "precisa": ""})
    for n, fator in ((2, 0.90), (3, 0.80)):
        for escolhidos in itertools.combinations(modulos, n):
            for niveis in itertools.product((0, 1), repeat=n):
                if n == 3 and len(set(niveis)) == 1:
                    continue  # os 3 iguais são os combos fechados
                pares = list(zip(escolhidos, niveis))
                total = sum(PRECOS[m][nv] for m, nv in pares)
                lista.append({
                    "grupo": "Combos personalizados", "nome": "Combo " + " + ".join(f"{NOMES[m]} {NIVEL[nv]}" for m, nv in pares),
                    "mensal": com_desconto(total, fator), "codigos": ", ".join(CODIGOS[p] for p in pares),
                    "arte": "combo-personalizado",
                    "frase": f"Combo personalizado com {n} módulos, {int(round((1 - fator) * 100))}% mais barato que separado.",
                    "itens": [f"{NOMES[m]} {NIVEL[nv]}: {LINHA[(m, nv)]}" for m, nv in pares], "precisa": "",
                })
    return lista


CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: 'DM Sans', Arial, sans-serif; color: #1D2A23; font-size: 10.5pt; line-height: 1.45; }
h1 { font-size: 24pt; margin: 0 0 4pt; color: #1F3A2E; }
h2 { font-size: 15pt; color: #1F3A2E; margin: 18pt 0 6pt; border-bottom: 2px solid #F2C230; padding-bottom: 3pt; }
h3 { font-size: 11.5pt; margin: 0 0 3pt; }
.sub { color: #5C6A61; margin: 0 0 10pt; }
.passo { display: flex; gap: 10pt; margin: 0 0 9pt; page-break-inside: avoid; }
.num { flex: none; width: 22pt; height: 22pt; border-radius: 50%; background: #F2C230; font-weight: 800; display: grid; place-items: center; }
.passo p { margin: 2pt 0; } .passo ul { margin: 3pt 0 0; padding-left: 14pt; }
code { background: #EFEADB; padding: 1pt 4pt; border-radius: 4px; font-size: 9.5pt; }
.aviso { background: #FBF1CF; border-left: 4px solid #F2C230; padding: 6pt 9pt; margin: 8pt 0; border-radius: 4px; }
table { width: 100%; border-collapse: collapse; font-size: 9pt; margin: 4pt 0 6pt; }
th, td { border: 1px solid #E5DFCD; padding: 4pt 5pt; text-align: left; vertical-align: top; }
th { background: #1F3A2E; color: #F6F3EA; } tr:nth-child(even) td { background: #FBFAF5; }
@page deitada { size: A4 landscape; margin: 12mm 12mm; }
.deitada { page: deitada; }
.deitada table { font-size: 9.5pt; } .deitada td { padding: 5pt 6pt; }
col.c-n { width: 3%; } col.c-p { width: 33%; } col.c-m { width: 8%; } col.c-a { width: 9%; }
col.c-c { width: 20%; } col.c-r { width: 12%; } col.c-i { width: 15%; }
td.n { white-space: nowrap; }
.produto { border: 1px solid #E5DFCD; border-radius: 8px; padding: 8pt 10pt; margin: 0 0 8pt; page-break-inside: avoid; }
.produto .linha { color: #5C6A61; font-size: 9pt; margin: 0 0 4pt; }
.produto ul { margin: 3pt 0; padding-left: 14pt; } .produto .precisa { font-size: 9pt; color: #5C6A61; margin: 3pt 0 0; }
.quebra { page-break-before: always; }
"""


def pagina() -> str:
    lista = produtos()
    linhas_tabela = "".join(
        f"<tr><td>{i}</td><td>{E(p['nome'])}</td><td class='n'>{brl(p['mensal'])}</td><td class='n'>{brl(p['mensal'] * 10)}</td>"
        f"<td><code>{E(p['codigos'])}</code></td><td>{E(p['arte'])}</td><td></td></tr>"
        for i, p in enumerate(lista, 1))
    fichas, grupo_atual = [], None
    for i, p in enumerate(lista, 1):
        if p["grupo"] != grupo_atual:
            grupo_atual = p["grupo"]
            fichas.append(f"<h2>{E(grupo_atual)}</h2>")
        itens = "".join(f"<li>{E(x)}</li>" for x in p["itens"])
        precisa = f"<p class='precisa'>{E(p['precisa'])}</p>" if p["precisa"] else ""
        fichas.append(
            f"<div class='produto'><h3>{i}. {E(p['nome'])}</h3>"
            f"<p class='linha'>{brl(p['mensal'])}/mês · {brl(p['mensal'] * 10)}/ano · arte: {E(p['arte'])}.png · "
            f"códigos: <code>{E(p['codigos'])}</code></p>"
            f"<p>{E(p['frase'])}</p><ul>{itens}</ul>{precisa}</div>")
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,700;9..40,800&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<h1>Appfiliado na Zouti</h1>
<p class="sub">Tudo o que precisa ser cadastrado: o passo a passo, os {len(lista)} produtos e o texto de cada um.</p>

<h2>Passo a passo</h2>
<div class="passo"><div class="num">1</div><div><p><strong>Criar a conta na Zouti</strong> com o CNPJ que recebe os pagamentos.
Ela pede documentos e dados bancários, e a aprovação pode levar alguns dias.</p></div></div>
<div class="passo"><div class="num">2</div><div><p><strong>Criar os {len(lista)} produtos</strong> (tabela abaixo), como assinatura:</p><ul>
<li>Nome, descrição (fichas no fim do guia) e arte: arquivos em <code>marketing/appfiliado/produtos/</code> (ou no ZIP).</li>
<li>Dois planos em cada produto: <strong>mensal</strong> e <strong>anual</strong> (o anual é 10× o mensal: 12 meses pelo preço de 10).
Se a Zouti exigir um produto separado para o anual, crie e anote os dois IDs.</li>
<li>Anote o ID de cada produto (começa com <code>prod_</code>) na última coluna da tabela.</li></ul></div></div>
<div class="passo"><div class="num">3</div><div><p><strong>Cadastrar o webhook</strong> em Integrações → Webhooks → Novo:</p><ul>
<li>URL: <code>https://app.appfiliado.com.br/licencas/webhook/zouti/</code></li>
<li>Eventos: todos os de <strong>assinatura</strong> (criada, ativada, renovada, cancelada, atrasada) e os de
<strong>pagamento e pedido</strong> de reembolso e contestação (chargeback). Se der para marcar "todos", melhor.</li>
<li>Copie o <strong>segredo do webhook</strong> que a Zouti mostra. Não mande em chat nem por e-mail.</li></ul></div></div>
<div class="passo"><div class="num">4</div><div><p><strong>No Render</strong>, no web service → Environment: crie <code>ZOUTI_WEBHOOK_SECRET</code>
com o segredo e salve (o worker não precisa).</p></div></div>
<div class="passo"><div class="num">5</div><div><p><strong>No admin do Appfiliado</strong> (<code>/admin/</code> → Appfiliado → Contas e assinaturas →
<strong>Produtos da Zouti</strong> → Adicionar), para cada produto: cole o <code>prod_...</code>, dê o nome e marque os módulos
da coluna "Códigos". Premium já inclui o básico.</p></div></div>
<div class="passo"><div class="num">6</div><div><p><strong>Sua conta:</strong> em Contas do Appfiliado, marque nos módulos de cortesia o que você usa
(principalmente "Emissor NFS-e (notas ilimitadas)").</p></div></div>
<div class="passo"><div class="num">7</div><div><p><strong>Testar antes de vender:</strong></p><ul>
<li>Botão "Testar Webhook" na Zouti → no admin, em <strong>Eventos de webhook da Zouti</strong>, o aviso aparece com "assinatura válida".
Se aparecer inválida, mande um print.</li>
<li>Compra de teste com outro e-mail: a conta nova aparece, o e-mail de boas-vindas com o link de senha chega, e o módulo fica liberado.</li>
<li>Reembolse a compra de teste: o acesso dessa conta é cortado.</li></ul></div></div>
<div class="passo"><div class="num">8</div><div><p><strong>Mande os links de checkout</strong> de cada produto para colocar os botões na landing page.</p></div></div>
<div class="aviso">Mudanças em Produtos da Zouti no admin valem na hora para quem já assinou, sem deploy.</div>

<section class="deitada"><h2>Os {len(lista)} produtos</h2>
<table><colgroup><col class="c-n"><col class="c-p"><col class="c-m"><col class="c-a"><col class="c-c"><col class="c-r"><col class="c-i"></colgroup><thead><tr><th>#</th><th>Produto</th><th>Mensal</th><th>Anual</th><th>Códigos (admin)</th><th>Arte</th><th>ID na Zouti (prod_...)</th></tr></thead>
<tbody>{linhas_tabela}</tbody></table></section>

<h2>Texto de cada produto</h2>
<p class="sub">Em todo plano: acesso ao painel (app.appfiliado.com.br) com Início, Resultados por Sub ID, Metas e relatório diário por e-mail.
No fim da descrição: "7 dias de garantia: não gostou, devolvemos o valor. Cancele quando quiser, sem multa. O Appfiliado é
independente e não tem vínculo oficial com a Shopee."</p>
{''.join(fichas)}
</body></html>"""


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        folha = navegador.new_page()
        folha.set_content(pagina(), wait_until="networkidle")
        folha.pdf(path=str(PASTA / "guia-zouti.pdf"), format="A4", print_background=True,
                  margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"})
        navegador.close()
    print(PASTA / "guia-zouti.pdf")


if __name__ == "__main__":
    main()
