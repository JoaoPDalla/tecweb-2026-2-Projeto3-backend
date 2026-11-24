from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('sampletext.urls')),
    # conteudos/validar-tema e conteudos/gerar precisam vir ANTES do router de api_urls,
    # senao o router captura 'validar-tema' como se fosse o id de um conteudo (405).
    path('api/conteudos/', include('sampletext.content_urls')),
    path('api/', include('sampletext.api_urls')),
]
