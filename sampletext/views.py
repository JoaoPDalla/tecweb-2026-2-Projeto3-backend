from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import TokenUsuarioAuthentication
from .models import Conteudo, Livro, Pergunta, Resposta, TokenUsuario, Usuario
from .permissions import DonoQuerysetMixin, IsDono
from .serializers import (
    ConteudoListaSerializer,
    ConteudoSerializer,
    LivroDetalheSerializer,
    LivroSerializer,
    LoginSerializer,
    ResponderSerializer,
    RespostaSerializer,
    UsuarioSerializer,
)
from .models import TokenUsuario, Usuario
from .serializers import LoginSerializer, UsuarioSerializer
from .throttling import LimiteLogin


class LoginView(APIView):
    """POST /api/auth/login/ {"nome": "..."}

    Se o nome já existe, entra como esse usuário; senão, cria um novo.
    Responde 201 quando criou e 200 quando o usuário já existia.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LimiteLogin]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nome = serializer.validated_data["nome"]

        usuario = Usuario.objects.filter(nome__iexact=nome).first()
        criado = usuario is None
        if criado:
            try:
                with transaction.atomic():
                    usuario = Usuario.objects.create(nome=nome)
            except IntegrityError:
                # Outra requisição criou o mesmo nome ao mesmo tempo.
                usuario = Usuario.objects.get(nome__iexact=nome)
                criado = False

        token, _ = TokenUsuario.objects.get_or_create(usuario=usuario)
        return Response(
            {"token": token.key, "usuario": UsuarioSerializer(usuario).data, "criado": criado},
            status=status.HTTP_201_CREATED if criado else status.HTTP_200_OK,
        )


class MeView(APIView):
    """GET /api/auth/me/ -> usuário do token (o front usa para validar a sessão)."""

    authentication_classes = [TokenUsuarioAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)


class LogoutView(APIView):
    """POST /api/auth/logout/ -> apaga o token; o próximo login gera um novo."""

    authentication_classes = [TokenUsuarioAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _parametro_inteiro(request, nome):
    """Lê um filtro numérico da query string (?livro=3). Ausente -> None; inválido -> 400."""
    valor = request.query_params.get(nome)
    if valor is None or valor == "":
        return None
    if not valor.isdigit():
        raise ValidationError({nome: "Informe um número inteiro."})
    return int(valor)


class LivroViewSet(DonoQuerysetMixin, viewsets.ModelViewSet):
    """/api/livros/ — listar, criar, abrir (com os conteúdos), renomear e excluir.

    Excluir um livro exclui os conteúdos dele.
    """

    queryset = Livro.objects.all()
    permission_classes = [IsAuthenticated, IsDono]

    def get_serializer_class(self):
        return LivroDetalheSerializer if self.action == "retrieve" else LivroSerializer

    def get_queryset(self):
        consulta = super().get_queryset()
        if self.action == "retrieve":
            consulta = consulta.prefetch_related("conteudos")
        return consulta


class ConteudoViewSet(DonoQuerysetMixin, viewsets.ModelViewSet):
    """/api/conteudos/ — listar (?livro=<id>), abrir, salvar, mover (PATCH livro) e excluir."""

    queryset = Conteudo.objects.all()
    permission_classes = [IsAuthenticated, IsDono]

    def get_serializer_class(self):
        return ConteudoListaSerializer if self.action == "list" else ConteudoSerializer

    def get_queryset(self):
        consulta = super().get_queryset()
        if self.action == "list":
            livro = _parametro_inteiro(self.request, "livro")
            if livro is not None:
                consulta = consulta.filter(livro_id=livro)
        if self.action == "retrieve":
            consulta = consulta.prefetch_related("perguntas")
        return consulta


class ResponderView(APIView):
    """POST /api/perguntas/<id>/responder/ {"alternativa": "a"}

    Registra a escolha do usuário (o servidor calcula se acertou) e devolve a resposta
    já com o gabarito. Pode responder à mesma pergunta várias vezes: cada tentativa é um registro.
    """

    def post(self, request, pergunta_id):
        pergunta = get_object_or_404(Pergunta, pk=pergunta_id)
        dados = ResponderSerializer(data=request.data)
        dados.is_valid(raise_exception=True)
        resposta = Resposta.objects.create(
            usuario=request.user, pergunta=pergunta, alternativa=dados.validated_data["alternativa"]
        )
        return Response(RespostaSerializer(resposta).data, status=status.HTTP_201_CREATED)


class PaginacaoHistorico(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


class HistoricoRespostasView(ListAPIView):
    """GET /api/respostas/ — histórico do usuário, da mais recente para a mais antiga.

    Filtros opcionais: ?pergunta=<id> e ?conteudo=<id>. Paginação: ?limit= e ?offset=.
    """

    serializer_class = RespostaSerializer
    pagination_class = PaginacaoHistorico

    def get_queryset(self):
        consulta = (
            Resposta.objects.filter(usuario=self.request.user)
            .select_related("pergunta")
            .order_by("-criado_em", "-id")
        )
        pergunta = _parametro_inteiro(self.request, "pergunta")
        if pergunta is not None:
            consulta = consulta.filter(pergunta_id=pergunta)
        conteudo = _parametro_inteiro(self.request, "conteudo")
        if conteudo is not None:
            consulta = consulta.filter(pergunta__conteudo_id=conteudo)
        return consulta
