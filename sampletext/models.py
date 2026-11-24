import secrets
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from .validators import validar_alternativas


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


class Livro(models.Model):
    """Coleção de conteúdos de um usuário (ex.: "Cálculo I")."""

    usuario = models.ForeignKey(Usuario, related_name="livros", on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em", "id"]
        constraints = [
            # Cada usuário tem no máximo um livro por nome, ignorando maiúsculas/minúsculas.
            models.UniqueConstraint(Lower("nome"), "usuario", name="livro_nome_unico_por_usuario"),
        ]

    def __str__(self):
        return self.nome

    def clean(self):
        super().clean()
        if isinstance(self.nome, str) and not self.nome.strip():
            raise ValidationError({"nome": "Este campo não pode conter apenas espaços."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Conteudo(models.Model):
    """Resumo de um tema salvo em um livro. Excluir o livro exclui seus conteúdos."""

    usuario = models.ForeignKey(Usuario, related_name="conteudos", on_delete=models.CASCADE)
    livro = models.ForeignKey(Livro, related_name="conteudos", on_delete=models.CASCADE)
    tema = models.CharField(max_length=255)
    resumo = models.TextField()  # Markdown com LaTeX
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em", "id"]

    def __str__(self):
        return self.tema

    def clean(self):
        super().clean()
        erros = {}
        for campo in ("tema", "resumo"):
            valor = getattr(self, campo)
            if isinstance(valor, str) and not valor.strip():
                erros[campo] = "Este campo não pode conter apenas espaços."
        # O livro precisa ser do mesmo usuário: é isso que impede "mover" para o livro de outra pessoa.
        if self.livro_id and self.usuario_id and self.livro.usuario_id != self.usuario_id:
            erros["livro"] = "O livro precisa pertencer ao mesmo usuário."
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


ALTERNATIVAS = [(letra, letra.upper()) for letra in "abcd"]


class Pergunta(models.Model):
    """Questão e gabarito; as alternativas incluem suas explicações."""

    tema = models.CharField(max_length=255)
    enunciado = models.TextField()
    alternativas = models.JSONField(validators=[validar_alternativas])
    resposta_correta = models.CharField(max_length=1, choices=ALTERNATIVAS)
    # Conteúdo de origem. Opcional: perguntas antigas ou ainda não salvas não têm conteúdo.
    conteudo = models.ForeignKey(
        Conteudo, related_name="perguntas", null=True, blank=True, on_delete=models.CASCADE
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(resposta_correta__in=list("abcd")),
                name="pergunta_gabarito_valido",
            ),
        ]

    def __str__(self):
        return self.enunciado[:80]

    def clean(self):
        super().clean()
        erros = {}
        for campo in ("tema", "enunciado"):
            valor = getattr(self, campo)
            if isinstance(valor, str) and not valor.strip():
                erros[campo] = "Este campo não pode conter apenas espaços."
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def para_quiz(self):
        """Contrato do controlador do frontend; inclui o gabarito para correção local."""
        if self.pk is None:
            raise ValueError("Salve a pergunta antes de exportá-la para o quiz.")
        return {
            "id": str(self.pk),
            "topic": self.tema,
            "prompt": self.enunciado,
            "answers": deepcopy(self.alternativas),
            "correctAnswerId": self.resposta_correta,
        }


class Resposta(models.Model):
    """Escolha de um estudante. Repetições são permitidas para manter o histórico."""

    usuario = models.ForeignKey(Usuario, related_name="respostas", on_delete=models.CASCADE)
    pergunta = models.ForeignKey(Pergunta, related_name="respostas", on_delete=models.CASCADE)
    alternativa = models.CharField(max_length=1, choices=ALTERNATIVAS)
    acertou = models.BooleanField(editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(alternativa__in=list("abcd")),
                name="resposta_alternativa_valida",
            ),
        ]

    def __str__(self):
        return f"{self.usuario} — pergunta {self.pergunta_id}: {self.alternativa}"

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["acertou"])
        self.acertou = self.alternativa == self.pergunta.resposta_correta
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"acertou"}
        return super().save(*args, **kwargs)


class ConteudoGerado(models.Model):
    """Cache do conteúdo gerado pela IA, compartilhado entre os usuários (um registro por tema)."""

    tema_chave = models.CharField(max_length=255, unique=True, editable=False)  # tema sem caixa/acentos
    tema = models.CharField(max_length=255)
    resumo = models.TextField()
    perguntas = models.JSONField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "conteúdo gerado"
        verbose_name_plural = "conteúdos gerados"

    def __str__(self):
        return self.tema

    def como_dict(self):
        return {"tema": self.tema, "resumo": self.resumo, "perguntas": self.perguntas}