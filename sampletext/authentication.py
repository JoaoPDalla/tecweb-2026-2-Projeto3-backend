from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication

from .models import TokenUsuario


class TokenUsuarioAuthentication(TokenAuthentication):
    """Autentica pelo header `Authorization: Token <chave>` usando TokenUsuario.

    Em caso de sucesso, `request.user` é um Usuario e `request.auth` é o TokenUsuario.
    """

    def authenticate_credentials(self, key):
        try:
            token = TokenUsuario.objects.select_related("usuario").get(key=key)
        except TokenUsuario.DoesNotExist:
            raise exceptions.AuthenticationFailed("Token inválido.")
        return (token.usuario, token)
