import secrets

from django.db import models
from django.db.models.functions import Lower


class Usuario(models.Model):
    """Usuário identificado apenas pelo nome (sem senha)."""

    nome = models.CharField(max_length=50)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # "Luan" e "luan" são o mesmo nome: a unicidade ignora maiúsculas/minúsculas.
            models.UniqueConstraint(Lower("nome"), name="usuario_nome_unico_sem_caixa"),
        ]

    def __str__(self):
        return self.nome

    # O DRF consulta estes atributos em request.user.
    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @staticmethod
    def normalizar_nome(nome):
        """Remove espaços das pontas e colapsa espaços repetidos."""
        return " ".join(nome.split())


def gerar_chave():
    return secrets.token_hex(20)  # 40 caracteres


class TokenUsuario(models.Model):
    """Token de acesso do usuário (um por usuário)."""

    key = models.CharField(max_length=40, primary_key=True, default=gerar_chave)
    usuario = models.OneToOneField(Usuario, related_name="token", on_delete=models.CASCADE)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Token de {self.usuario}"
