"""Descarta a fila de posts/stories presos em "aguardando aprovação" desde
agosto/setembro de 2026 (institucional, ofertas da semana, dica, lembrete) - o dono
não estava tendo tempo de aprovar e-mail por e-mail (conversa de 01/11/2026). A
partir desta leva, esse conteúdo passa a publicar direto (ver instagram_bot/services.py,
pular_aprovacao), então a fila não volta a crescer sozinha."""
from django.db import migrations


def descartar_pendentes(apps, schema_editor):
    RegistroPublicacao = apps.get_model("instagram_bot", "RegistroPublicacao")
    RegistroPublicacao.objects.filter(status="pendente_aprovacao").update(status="rejeitado")


class Migration(migrations.Migration):

    dependencies = [
        ("instagram_bot", "0011_alter_registropublicacao_conteudo_tipo"),
    ]

    operations = [
        migrations.RunPython(descartar_pendentes, migrations.RunPython.noop),
    ]
