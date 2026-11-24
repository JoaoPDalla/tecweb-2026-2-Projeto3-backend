from django.contrib import admin

<<<<<<< HEAD
from .models import Conteudo, Livro, Usuario
=======
from .models import ConteudoGerado, Usuario
>>>>>>> ce18c54a87076f9ba2ad6a6dfdb88a4e9e0cfdc0


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ["nome", "criado_em"]
    search_fields = ["nome"]


<<<<<<< HEAD
@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = ["nome", "usuario", "criado_em"]
    search_fields = ["nome", "usuario__nome"]


@admin.register(Conteudo)
class ConteudoAdmin(admin.ModelAdmin):
    list_display = ["tema", "livro", "usuario", "criado_em"]
    search_fields = ["tema", "usuario__nome"]
=======
@admin.register(ConteudoGerado)
class ConteudoGeradoAdmin(admin.ModelAdmin):
    list_display = ["tema", "criado_em"]
    search_fields = ["tema"]
>>>>>>> ce18c54a87076f9ba2ad6a6dfdb88a4e9e0cfdc0
