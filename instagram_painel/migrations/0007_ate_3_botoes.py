from django.db import migrations, models


def de_botao_para_botoes(apps, schema_editor):
    Automacao = apps.get_model("instagram_painel", "Automacao")
    Automacao.objects.filter(botao=False).update(botoes=0)


def de_botoes_para_botao(apps, schema_editor):
    Automacao = apps.get_model("instagram_painel", "Automacao")
    Automacao.objects.filter(botoes=0).update(botao=False)


class Migration(migrations.Migration):
    dependencies = [("instagram_painel", "0006_conta_do_instagram")]

    operations = [
        migrations.AddField(model_name="automacao", name="botoes", field=models.PositiveSmallIntegerField(default=1)),
        migrations.AddField(model_name="automacao", name="botoes_extras", field=models.JSONField(blank=True, default=list)),
        migrations.RunPython(de_botao_para_botoes, de_botoes_para_botao),
        migrations.RemoveField(model_name="automacao", name="botao"),
    ]
