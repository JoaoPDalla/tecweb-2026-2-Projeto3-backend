from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("livros", views.LivroViewSet, basename="livro")
router.register("conteudos", views.ConteudoViewSet, basename="conteudo")

urlpatterns = [
    path("", include(router.urls)),
    path("perguntas/<int:pergunta_id>/responder/", views.ResponderView.as_view(), name="responder"),
    path("respostas/", views.HistoricoRespostasView.as_view(), name="respostas"),
]
