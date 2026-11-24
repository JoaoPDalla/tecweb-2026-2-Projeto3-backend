from django.contrib import admin

from .models import ConteudoGerado, Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ["nome", "criado_em"]
    search_fields = ["nome"]


@admin.register(ConteudoGerado)
class ConteudoGeradoAdmin(admin.ModelAdmin):
    list_display = ["tema", "criado_em"]
    search_fields = ["tema"]