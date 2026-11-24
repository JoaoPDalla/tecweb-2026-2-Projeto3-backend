from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import TokenUsuarioAuthentication
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