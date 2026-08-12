from django.db import migrations


def atualizar_banners(apps, schema_editor):
    Banner = apps.get_model("paginas", "Banner")

    Banner.objects.filter(imagem_estatica="images/banners/inauguracao.jpg").update(
        selo="MÊS DE INAUGURAÇÃO",
        texto="Cashback em <mark>DOBRO</mark> em todas as compras",
        subtexto="Durante todo o mês, todo link gerado no cash-b paga o dobro do cashback normal.",
        imagem_estatica="",
        alinhamento="esquerda",
        botao_texto="Ir pra Shopee",
        botao_link="/ir-para-shopee/",
        botao2_texto="Converter link de produto",
        botao2_link="/#converter-link",
    )

    Banner.objects.filter(imagem_estatica="images/banners/ofertas.jpg").update(
        selo="ACHADINHOS DA SEMANA",
        texto="Não sabe o que comprar?",
        subtexto="Veja a nossa lista de ofertas.",
        botao_texto="Ver ofertas",
        botao_link="/ofertas/",
    )


def reverter(apps, schema_editor):
    Banner = apps.get_model("paginas", "Banner")

    Banner.objects.filter(texto__startswith="Cashback em").update(
        selo="",
        texto="Mês de inauguração 🎉",
        subtexto="Cashback em DOBRO em todas as compras este mês",
        imagem_estatica="images/banners/inauguracao.jpg",
        botao_texto="",
        botao_link="",
        botao2_texto="",
        botao2_link="",
    )

    Banner.objects.filter(imagem_estatica="images/banners/ofertas.jpg").update(
        selo="",
        texto="Não sabe o que comprar?",
        subtexto="Veja as ofertas com maior cashback da semana",
        botao_texto="",
        botao_link="",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("paginas", "0006_remove_banner_link_banner_botao2_link_and_more"),
    ]

    operations = [
        migrations.RunPython(atualizar_banners, reverter),
    ]
