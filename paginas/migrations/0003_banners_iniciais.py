from django.db import migrations


def criar_banners(apps, schema_editor):
    Banner = apps.get_model("paginas", "Banner")
    Banner.objects.create(
        texto="Mês de inauguração 🎉",
        subtexto="Cashback em DOBRO em todas as compras este mês",
        imagem_estatica="images/banners/inauguracao.jpg",
        link="/ofertas/",
        ativo=True,
        ordem=1,
    )
    Banner.objects.create(
        texto="Não sabe o que comprar?",
        subtexto="Veja as ofertas com maior cashback da semana",
        imagem_estatica="images/banners/ofertas.jpg",
        link="/ofertas/",
        ativo=True,
        ordem=2,
    )


def remover_banners(apps, schema_editor):
    Banner = apps.get_model("paginas", "Banner")
    Banner.objects.filter(
        imagem_estatica__in=["images/banners/inauguracao.jpg", "images/banners/ofertas.jpg"]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("paginas", "0002_banner_imagem_estatica_banner_subtexto_and_more"),
    ]

    operations = [
        migrations.RunPython(criar_banners, remover_banners),
    ]
