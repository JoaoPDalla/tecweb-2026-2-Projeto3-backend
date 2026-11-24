from django.db import migrations


class Migration(migrations.Migration):
    """Junta as duas migracoes 0003 (ConteudoGerado e Livro/Conteudo)."""

    dependencies = [
        ('sampletext', '0003_conteudogerado'),
        ('sampletext', '0003_livro_conteudo_pergunta_conteudo'),
    ]

    operations = []
