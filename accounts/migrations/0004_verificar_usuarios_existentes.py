from django.db import migrations


def marcar_como_verificados(apps, schema_editor):
    """Contas criadas antes deste recurso existir não devem ficar bloqueadas
    de sacar só porque nunca receberam um e-mail de confirmação."""
    User = apps.get_model("accounts", "User")
    User.objects.update(email_verificado=True)


def reverter(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.update(email_verificado=False)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_email_verificado"),
    ]

    operations = [
        migrations.RunPython(marcar_como_verificados, reverter),
    ]
