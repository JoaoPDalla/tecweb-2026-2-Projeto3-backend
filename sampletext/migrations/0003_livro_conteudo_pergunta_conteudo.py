# Escrita à mão a partir dos models; confira com `python manage.py makemigrations --check --dry-run`.

import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sampletext', '0002_pergunta_resposta'),
    ]

    operations = [
        migrations.CreateModel(
            name='Livro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='livros', to='sampletext.usuario')),
            ],
            options={
                'ordering': ['criado_em', 'id'],
                'constraints': [models.UniqueConstraint(django.db.models.functions.text.Lower('nome'), models.F('usuario'), name='livro_nome_unico_por_usuario')],
            },
        ),
        migrations.CreateModel(
            name='Conteudo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tema', models.CharField(max_length=255)),
                ('resumo', models.TextField()),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('livro', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conteudos', to='sampletext.livro')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conteudos', to='sampletext.usuario')),
            ],
            options={
                'ordering': ['criado_em', 'id'],
            },
        ),
        migrations.AddField(
            model_name='pergunta',
            name='conteudo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='perguntas', to='sampletext.conteudo'),
        ),
    ]
