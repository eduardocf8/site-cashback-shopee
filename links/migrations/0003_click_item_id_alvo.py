from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("links", "0002_alter_click_tipo"),
    ]

    operations = [
        migrations.AddField(
            model_name="click",
            name="item_id_alvo",
            field=models.BigIntegerField(
                blank=True,
                help_text="Preenchido quando dá pra identificar de cara qual produto gerou "
                "esse clique (link específico ou card da vitrine), sem seguir "
                "redirecionamento nenhum - usado só pra confirmar depois que a compra real é "
                "do mesmo produto, não pra garantir cashback de campanha nem nada do tipo. "
                "Fica vazio pra cliques na home ('Ir pra Shopee') e pra links que não dá pra "
                "identificar sem seguir redirecionamento (ver ROADMAP.md, Fase 41).",
                null=True,
                verbose_name="Item ID do produto clicado",
            ),
        ),
    ]
