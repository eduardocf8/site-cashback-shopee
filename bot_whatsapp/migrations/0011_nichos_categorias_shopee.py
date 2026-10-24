"""Os nichos passam a ser as categorias principais da Shopee (busca direto na categoria). Converte
os nichos salvos com as categorias antigas (por palavras do nome do produto)."""

from django.db import migrations

ANTIGAS = {
    "moda": "100017", "beleza": "100630", "casa": "100636", "eletronicos": "100013", "eletrodomesticos": "100010",
    "bebes": "100632", "brinquedos": "100639", "esporte": "100637", "automotivo": "100640", "pet": "100631",
    "papelaria": "100638", "saude": "100001", "joias": "100009", "ferramentas": "100636",
}


def converter(apps, schema_editor):
    Config = apps.get_model("bot_whatsapp", "ConfiguracaoOfertas")
    for config in Config.objects.exclude(nichos={}):
        if not isinstance(config.nichos, dict):
            config.nichos = {}
        else:
            config.nichos = {jid: ANTIGAS[n] for jid, n in config.nichos.items() if n in ANTIGAS}
        config.paginas_nichos = {}
        config.save(update_fields=["nichos", "paginas_nichos"])


class Migration(migrations.Migration):
    dependencies = [("bot_whatsapp", "0010_envio_por_nicho")]
    operations = [migrations.RunPython(converter, migrations.RunPython.noop)]
