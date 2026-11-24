from django.contrib import admin

from .models import Conteudo, Livro, Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ["nome", "criado_em"]
    search_fields = ["nome"]


@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = ["nome", "usuario", "criado_em"]
    search_fields = ["nome", "usuario__nome"]


@admin.register(Conteudo)
class ConteudoAdmin(admin.ModelAdmin):
    list_display = ["tema", "livro", "usuario", "criado_em"]
    search_fields = ["tema", "usuario__nome"]
