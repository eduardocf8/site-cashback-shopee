from django.db import migrations, models


def classificar_vendas_guardadas(apps, schema_editor):
    """As vendas já guardadas não têm a marca de origem (os links eram gerados sem ela): a origem
    sai do Sub ID, com as mesmas regras de painel/origens.py."""
    from painel.origens import Classificador, rotulos_do_bot

    VendaItem = apps.get_model("painel", "VendaItem")
    ConfiguracaoOfertas = apps.get_model("bot_whatsapp", "ConfiguracaoOfertas")
    SiteAfiliado = apps.get_model("meusite", "SiteAfiliado")
    for conta_id in VendaItem.objects.order_by().values_list("conta_id", flat=True).distinct():
        config = ConfiguracaoOfertas.objects.filter(conta_id=conta_id).first()
        site = SiteAfiliado.objects.filter(conta_id=conta_id).first()
        classificador = Classificador(rotulos_do_bot(config), [site.sub_id, site.sub_id_vitrine] if site else [])
        for rotulo in VendaItem.objects.filter(conta_id=conta_id).order_by().values_list("sub_id", flat=True).distinct():
            origem = classificador.origem(rotulo)
            if origem != "fora":
                VendaItem.objects.filter(conta_id=conta_id, sub_id=rotulo).update(origem=origem)


class Migration(migrations.Migration):

    dependencies = [
        ("painel", "0014_fechamento_do_mes"),
        ("bot_whatsapp", "0020_sub_ids_do_grupo_novo"),
        ("meusite", "0004_andamento_dos_produtos_escolhidos"),
    ]

    operations = [
        migrations.AddField(
            model_name="vendaitem",
            name="origem",
            field=models.CharField(db_index=True, default="fora", max_length=10),
        ),
        migrations.RunPython(classificar_vendas_guardadas, migrations.RunPython.noop),
    ]
