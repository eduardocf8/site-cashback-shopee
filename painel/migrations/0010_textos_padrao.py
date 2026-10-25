from django.db import migrations


def criar(apps, schema_editor):
    from painel.textos_dicas import TEXTOS

    Texto = apps.get_model("painel", "TextoEmailDica")
    for chave, t in TEXTOS.items():
        Texto.objects.get_or_create(chave=chave, defaults={
            "assunto": t["assunto"], "texto": t["texto"], "texto_sem": t.get("texto_sem", ""), "ativo": t.get("ativo", True),
        })


class Migration(migrations.Migration):
    dependencies = [("painel", "0009_textos_e_sugestoes")]
    operations = [migrations.RunPython(criar, migrations.RunPython.noop)]
