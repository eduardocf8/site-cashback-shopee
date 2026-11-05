"""O e-mail de dicas do dia 12 (site_carrosseis) fala do Estúdio Instagram, das Automações e dos pacotes de
hoje, em vez dos Carrosséis e do desconto de combo antigo. Só troca o texto salvo se ele ainda é o padrão
antigo: o que foi editado no admin fica como está."""

from django.db import migrations

TEXTO_ANTIGO = 'Grupo de WhatsApp vende muito, mas quem chega pelo Instagram também compra. O segredo é ter um caminho fácil do post até o link.\n\n[site] **No seu site** (o seu link na bio):\n[site] ↳ Deixe o botão mais importante em destaque, como o link do seu grupo VIP\n[site] ↳ Use a vitrine com as ofertas que combinam com o seu público (com o Bot, ela mostra as últimas que ele enviou)\n[site] ↳ Acompanhe os cliques de cada botão e produto no painel\n\n{imagem}\n\n[carrosséis] **Nos carrosséis:** cole o link de um produto e o Appfiliado monta o carrossel com textos feitos por IA e o seu link.\n[carrosséis premium] Minha dica: salve o seu modelo, cor e @ como padrão, e os próximos já saem com a sua cara.\n\n{botao}\n\n[sem site] Quer um link na bio com vitrine e conversor pro seu público? Conheça o [Meu site](planos).\n[sem carrosséis] Quer posts prontos pro Instagram a partir de um link? Conheça os [Carrosséis](planos).'

TEXTO_SEM_ANTIGO = 'Grupo de WhatsApp vende muito, mas quem chega pelo Instagram também compra. O segredo é ter um caminho fácil do post até o link.\n\nNo Appfiliado, dois módulos fazem esse caminho:\n\n↳ **Meu site:** o seu link na bio, com botões, conversor de links pro seu público e vitrine de ofertas\n↳ **Carrosséis:** cole o link de um produto e receba um carrossel pronto pro Instagram, com textos feitos por IA\n\n{imagem}\n\nJuntando com o que você já tem, sai com desconto de combo: 10% com 2 módulos e 20% com 3.\n\n{botao}'

TEXTO_NOVO = 'Grupo de WhatsApp vende muito, mas quem chega pelo Instagram também compra. O segredo é ter um caminho fácil do post até o link.\n\n[site] **No seu site** (o seu link na bio):\n[site] ↳ Deixe o botão mais importante em destaque, como o link do seu grupo VIP\n[site] ↳ Ligue a vitrine de ofertas (com o Bot, ela mostra as últimas que ele mandou nos grupos)\n[site] ↳ Deixe o conversor de links no ar: quem achou algo na Shopee cola o link e compra pelo seu\n[site] ↳ Acompanhe as visitas e os cliques de cada botão e produto no painel\n\n{imagem}\n\n[estúdio] **No Estúdio Instagram:** cole o link de um produto e a IA monta o post, o carrossel ou os stories com a foto, o preço e o seu link. Você publica na hora ou agenda pro dia e a hora que quiser.\n\n[estúdio] [sem estúdio premium] Minha dica: salve o seu @ em [Minha marca](marca). Os próximos posts já saem com ele.\n[estúdio premium] Minha dica: salve o seu logo, as suas cores e a sua fonte em [Minha marca](marca). Os próximos posts já saem com a sua cara.\n\n[sem estúdio] [carrosséis] **Nos carrosséis:** cole o link de um produto e o Appfiliado monta o carrossel com textos feitos por IA e o seu link. Em breve ele vira o **Estúdio Instagram**, que já faz parte do seu plano: posts, stories e publicação direto no seu perfil.\n\n[sem estúdio] [carrosséis premium] Minha dica: salve o seu modelo, a cor e o @ como padrão. Os próximos carrosséis já saem com a sua cara.\n\n[automações] **Nas Automações Instagram:** quem comentar a palavra certa no seu post (como QUERO) recebe o seu link por DM, na hora. Avise na legenda: "comente QUERO que eu te mando o link".\n\n{botao}\n\n[sem site] Quer um link na bio com vitrine e conversor pro seu público? Conheça o [Meu site](planos).\n[instagram lançado] [sem carrosséis] Quer posts e stories prontos pro Instagram a partir de um link? Conheça o [Estúdio Instagram](planos).\n[instagram lançado] [sem automações] Quer mandar o seu link por DM para quem comentar no seu post? Conheça as [Automações Instagram](planos).'

TEXTO_SEM_NOVO = 'Grupo de WhatsApp vende muito, mas quem chega pelo Instagram também compra. O segredo é ter um caminho fácil do post até o link.\n\nO **Meu site** faz esse caminho: é o seu link na bio, com botões, conversor de links pro seu público e vitrine de ofertas.\n\n{imagem}\n\n[bot] Com o Bot, a vitrine mostra sozinha as últimas ofertas que ele mandou nos seus grupos. Juntos no **Pacote Ofertas**, os dois saem 10% mais baratos.\n[sem bot] Com o Bot de WhatsApp no **Pacote Ofertas**, os dois saem 10% mais baratos.\n\n[instagram lançado] E pro Instagram tem mais dois módulos:\n[sem instagram lançado] E vêm aí mais dois módulos pro Instagram:\n↳ **Estúdio Instagram:** posts e stories prontos a partir do link do produto, publicados direto no seu perfil\n↳ **Automações Instagram:** o seu link por DM para quem comentar no seu post\n\n[instagram lançado] Juntos no **Pacote Instagram**, os dois também saem 10% mais baratos.\n\n{botao}'


def atualizar(apps, schema_editor):
    Texto = apps.get_model("painel", "TextoEmailDica")
    salvo = Texto.objects.filter(chave="site_carrosseis").first()
    if not salvo:
        return
    mudou = []
    if salvo.texto.replace("\r\n", "\n").strip() == TEXTO_ANTIGO.strip():
        salvo.texto = TEXTO_NOVO
        mudou.append("texto")
    if salvo.texto_sem.replace("\r\n", "\n").strip() == TEXTO_SEM_ANTIGO.strip():
        salvo.texto_sem = TEXTO_SEM_NOVO
        mudou.append("texto_sem")
    if mudou:
        salvo.save(update_fields=mudou)


class Migration(migrations.Migration):
    dependencies = [("painel", "0016_ferramentas_das_sugestoes")]
    operations = [migrations.RunPython(atualizar, migrations.RunPython.noop)]
