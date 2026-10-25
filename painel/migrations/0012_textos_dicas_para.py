"""Troca "pra" por "para" onde não é "para a" nos textos padrão dos e-mails de dicas.
Só mexe nas linhas cujo texto ainda é exatamente o padrão antigo (não sobrescreve o que foi editado no admin)."""
from django.db import migrations

TROCAS = [
    ('pra só passar', 'para só passar'),
    ('dá pra copiar', 'dá para copiar'),
    ('pra cada lugar', 'para cada lugar'),
    ('pra achar', 'para achar'),
    ('pra você vender', 'para você vender'),
]

# (chave, campo) -> texto padrão antigo, exatamente como a 0010 gravou.
ANTIGOS = {
    ('bot', 'texto'): 'Uma coisa que eu aprendi divulgando oferta em grupo: quem vende todo dia não é quem posta mais. É quem posta **no ritmo certo**, sem cansar o grupo.\n\nFoi pensando nisso que eu montei o Bot do Appfiliado:\n\n↳ **Intervalo e horário:** uma oferta a cada X minutos, só na janela em que o seu público está acordado\n↳ **Não repetir:** o mesmo produto não volta pro mesmo grupo por quantos dias você escolher\n↳ **Filtros:** comissão, desconto, preço e avaliação mínimos, pra só passar o que vale a pena\n↳ **Modo simulação:** você vê o que sairia antes de mandar de verdade\n\n{imagem}\n\nMinha dica: comece com uma oferta a cada 15 ou 20 minutos, das 8h às 22h, e comissão mínima de 10%. Depois de uma semana, veja em Resultados quais grupos venderam mais e ajuste.\n\n{botao}\n\n[sem premium] No Premium, cada grupo pode receber as ofertas do seu nicho (beleza, casa, pet…), a IA revisa o texto antes de enviar e dá pra copiar ofertas de outros grupos com o seu link. [Ver o Premium](planos)',
    ('resultados', 'texto'): 'A maioria dos afiliados olha só o total do mês no painel da Shopee. Mas o total não conta **de onde** veio cada venda.\n\nEm **Resultados**, no Appfiliado, você vê:\n\n↳ Comissão estimada e validada por dia, semana ou mês\n↳ **Vendas por Sub ID:** cada grupo, canal ou rede com o seu número\n↳ Os produtos que mais venderam\n↳ A meta do mês, com as faixas de bônus\n\n{imagem}\n\nE se quiser, recebe tudo isso por e-mail toda manhã: é só ligar o relatório diário em [Configurações](configuracoes).\n\nMinha dica: use um Sub ID diferente pra cada lugar onde você divulga (ex: grupovip, instagram, site).\n[bot] No Bot, cada grupo pode ter o seu Sub ID próprio.\n\n[sem api] **Importante:** pros números aparecerem, conecte a API da Shopee em [Configurações](configuracoes).\n\n{botao}',
    ('campanhas', 'texto_sem'): 'Nas datas duplas (9.9, 10.10, 11.11, 12.12) e na Black Friday, a Shopee vende em poucas horas o que vende num mês. E é justo quando a gente está cansado, de madrugada.\n\nTrês coisas que ajudam nessas datas:\n\n↳ No **Radar**, ordene por **maior desconto** pra achar as melhores ofertas do dia\n↳ No **Conversor**, cole a mensagem da Shopee com os links da campanha e saia com tudo no seu link\n↳ Deixe a página da campanha no seu link na bio\n\n{botao}\n\nCom o Bot de WhatsApp, o modo campanha faz isso tudo sozinho nos seus grupos, inclusive de madrugada. [Conhecer o Bot](planos)',
    ('como_vai', 'texto'): 'Já faz três semanas que você está com o Appfiliado, e eu queria saber como está sendo.\n\n{numeros}\n\n**Me conta:** o que está funcionando e o que falta no Appfiliado pra você vender mais? Responda este e-mail ou mande a sua ideia no formulário de sugestões. Eu leio todas.\n\n{botao}\n\n[notas] Lembrete: no Emissor NFS-e, você importa o relatório da Shopee e emite as notas do mês em lote, cada uma já com o e-mail pro vendedor.\n[emissor] Vendendo nesse ritmo, vale pensar nas notas fiscais das suas comissões. O Emissor NFS-e do Appfiliado importa o relatório da Shopee e emite as notas do mês em lote. [Conhecer o Emissor](planos)',
}


def _novo(texto):
    for antigo, novo in TROCAS:
        texto = texto.replace(antigo, novo)
    return texto


def _trocar(apps, para_frente):
    Texto = apps.get_model("painel", "TextoEmailDica")
    for (chave, campo), antigo in ANTIGOS.items():
        de, para = (antigo, _novo(antigo)) if para_frente else (_novo(antigo), antigo)
        Texto.objects.filter(chave=chave, **{campo: de}).update(**{campo: para})


def aplicar(apps, schema_editor):
    _trocar(apps, True)


def desfazer(apps, schema_editor):
    _trocar(apps, False)


class Migration(migrations.Migration):
    dependencies = [("painel", "0011_textos_para")]
    operations = [migrations.RunPython(aplicar, desfazer)]
