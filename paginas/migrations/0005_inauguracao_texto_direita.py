from django.db import migrations


def mover_texto_pra_direita(apps, schema_editor):
    Banner = apps.get_model("paginas", "Banner")
    Banner.objects.filter(imagem_estatica="images/banners/inauguracao.jpg").update(alinhamento="direita")


def reverter(apps, schema_editor):
    Banner = apps.get_model("paginas", "Banner")
    Banner.objects.filter(imagem_estatica="images/banners/inauguracao.jpg").update(alinhamento="esquerda")


class Migration(migrations.Migration):
    dependencies = [
        ("paginas", "0004_banner_alinhamento"),
    ]

    operations = [
        migrations.RunPython(mover_texto_pra_direita, reverter),
    ]
