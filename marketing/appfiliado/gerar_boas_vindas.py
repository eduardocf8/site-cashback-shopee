"""PDF de boas-vindas do Appfiliado (anexo do produto na Zouti, "Arquivos digitais").

Uso (na raiz do repositório): python3 marketing/appfiliado/gerar_boas_vindas.py [contato]
O contato (ex: "WhatsApp (11) 99999-9999" ou um e-mail) é opcional e entra no fim do guia.
Sai em marketing/appfiliado/boas-vindas-appfiliado.pdf."""

import html
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
E = html.escape
LOGO = ('<svg viewBox="3 8.25 36 36" width="40" height="40"><g fill="none" stroke="currentColor" stroke-width="5" '
        'stroke-linecap="round"><circle cx="21" cy="26" r="9.5"/><path d="M30.5 16.5V36"/></g>'
        '<circle cx="21" cy="26" r="3.6" fill="currentColor"/></svg>')

PASSOS = [
    ("Confira o seu e-mail",
     "Logo depois da compra você recebe um e-mail do <strong>Appfiliado</strong> com a sua chave de acesso e um link para criar a senha. "
     "Se não chegar em alguns minutos, olhe a caixa de <strong>spam</strong> ou a aba Promoções."),
    ("Crie a senha e entre",
     "Clique no link do e-mail, crie a sua senha e entre em <strong>app.appfiliado.com.br</strong>. "
     "Nas próximas vezes, entre pelo mesmo endereço com o seu e-mail e a senha."),
    ("Conecte a sua conta da Shopee",
     "Em <strong>Configurações</strong>, informe o <strong>AppID</strong> e o <strong>Secret</strong> da sua conta de afiliado. "
     "Eles ficam no portal de afiliados da Shopee, em Open API. O Secret é guardado criptografado e nunca aparece de novo na tela."),
    ("Comece pelo módulo que você comprou",
     "O menu do painel mostra o que está liberado no seu plano."),
]
MODULOS = [
    ("Bot de WhatsApp", "Abra a aba <strong>Conexão</strong>, leia o QR Code com o WhatsApp do número que vai mandar as ofertas e conecte. "
     "Depois, em <strong>Automação</strong>, escolha de onde vêm as ofertas, os grupos de destino e o intervalo, e ligue as ofertas. "
     "Dica: comece com a opção de <em>simulação</em>, que faz tudo sem enviar nada."),
    ("Meu site", "Escolha o endereço, o nome e a cor, adicione os botões e confira a prévia ao lado. "
     "Quando estiver bom, marque o site como publicado e coloque o link na bio."),
    ("Carrosséis", "Cole o link de um produto da Shopee e gere o carrossel. Ajuste os textos no editor e baixe as imagens para postar."),
    ("Emissão NFS-e", "Cadastre o CNPJ, envie o certificado digital A1, informe o serviço e faça uma nota de teste. "
     "Depois, envie o Relatório Mensal da Shopee: sai uma nota por loja, com e-mail para cada vendedor."),
]
DICAS = [
    "Use <strong>Sub IDs</strong> diferentes para cada canal (grupos, Instagram, site). Em Resultados você vê quanto cada um vendeu.",
    "Ative o <strong>relatório diário por e-mail</strong> em Configurações para receber os números de ontem toda manhã.",
    "O bot usa o WhatsApp de forma não oficial. Use um número só para as ofertas, sem exagerar no volume, para evitar bloqueios.",
]

CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; margin: 0; }
body { font-family: 'DM Sans', Arial, sans-serif; color: #1D2A23; font-size: 11pt; line-height: 1.5; }
.topo { background: #1F3A2E; color: #F6F3EA; padding: 22mm 18mm 14mm; }
.marca { display: flex; align-items: center; gap: 10px; font-size: 15pt; font-weight: 800; }
.marca .logo { width: 40px; height: 40px; border-radius: 10px; background: #F2C230; color: #1D2A23; display: grid; place-items: center; }
h1 { font-size: 27pt; font-weight: 800; letter-spacing: -.02em; line-height: 1.1; margin: 14mm 0 3mm; }
.topo p { color: #CFDBD2; font-size: 12pt; max-width: 150mm; }
.corpo { padding: 9mm 18mm 14mm; }
h2 { font-size: 14pt; color: #1F3A2E; margin: 8mm 0 3mm; padding-bottom: 2mm; border-bottom: 2px solid #F2C230; }
.passo { display: flex; gap: 4mm; margin: 0 0 4mm; page-break-inside: avoid; }
.num { flex: none; width: 8mm; height: 8mm; border-radius: 50%; background: #F2C230; font-weight: 800; display: grid; place-items: center; }
.passo h3 { font-size: 11.5pt; margin: 0 0 1mm; }
.modulo { background: #F6F3EA; border-radius: 3mm; padding: 3.5mm 4.5mm; margin: 0 0 3mm; page-break-inside: avoid; }
.modulo h3 { font-size: 11pt; color: #1F3A2E; margin-bottom: 1mm; }
ul { padding-left: 5mm; } li { margin: 0 0 2mm; }
.contato { margin-top: 8mm; background: #FBF1CF; border-left: 4px solid #F2C230; border-radius: 2mm; padding: 4mm 5mm; }
.rodape { margin-top: 8mm; color: #5C6A61; font-size: 9pt; }
"""


def pagina(contato: str) -> str:
    passos = "".join(
        f"<div class='passo'><div class='num'>{i}</div><div><h3>{E(t)}</h3><p>{d}</p></div></div>"
        for i, (t, d) in enumerate(PASSOS, 1))
    modulos = "".join(f"<div class='modulo'><h3>{E(t)}</h3><p>{d}</p></div>" for t, d in MODULOS)
    dicas = "".join(f"<li>{d}</li>" for d in DICAS)
    bloco_contato = (f"<div class='contato'><strong>Precisa de ajuda?</strong> Fale com a gente: {E(contato)}.</div>"
                     if contato else "")
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700;9..40,800&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<div class="topo"><div class="marca"><span class="logo">{LOGO}</span>Appfiliado</div>
<h1>Bem-vindo ao Appfiliado!</h1>
<p>Em 4 passos você começa a usar. Guarde este guia: ele reúne o caminho de cada módulo.</p></div>
<div class="corpo">
<h2>Primeiros passos</h2>{passos}
<h2>Cada módulo, em poucas linhas</h2>{modulos}
<h2>Dicas para vender mais</h2><ul>{dicas}</ul>
{bloco_contato}
<p class="rodape">O Appfiliado é independente e não tem vínculo oficial com a Shopee. Cancele quando quiser, sem multa,
e conte com 7 dias de garantia: não gostou, devolvemos o valor.</p>
</div></body></html>"""


def main():
    from playwright.sync_api import sync_playwright

    contato = " ".join(sys.argv[1:]).strip()
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        folha = navegador.new_page()
        folha.set_content(pagina(contato), wait_until="networkidle")
        folha.pdf(path=str(PASTA / "boas-vindas-appfiliado.pdf"), format="A4", print_background=True)
        navegador.close()
    print(PASTA / "boas-vindas-appfiliado.pdf")


if __name__ == "__main__":
    main()
