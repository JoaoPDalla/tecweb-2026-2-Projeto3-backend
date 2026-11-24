from django.urls import path

from .content_views import GerarConteudoView, ValidarTemaView

urlpatterns = [
    path("validar-tema/", ValidarTemaView.as_view(), name="validar-tema"),
    path("gerar/", GerarConteudoView.as_view(), name="gerar-conteudo"),
]
