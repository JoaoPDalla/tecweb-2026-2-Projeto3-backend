import json

from django.db import transaction
from rest_framework import serializers

from .models import Conteudo, Livro, Pergunta, Resposta, Usuario
from .ai.errors import ErroIA
from .ai.validation import validar_conteudo
from .quiz_persistence import campos_pergunta


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ["id", "nome"]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    nome = serializers.CharField(min_length=2, max_length=50)

    def validate_nome(self, valor):
        return Usuario.normalizar_nome(valor)


class ConteudoResumoSerializer(serializers.ModelSerializer):
    """Item de conteúdo dentro do livro (os "chips" do frontend)."""

    class Meta:
        model = Conteudo
        fields = ["id", "tema", "criado_em"]
        read_only_fields = fields


class LivroSerializer(serializers.ModelSerializer):
    class Meta:
        model = Livro
        fields = ["id", "nome", "criado_em"]
        read_only_fields = ["id", "criado_em"]

    def validate_nome(self, valor):
        nome = Usuario.normalizar_nome(valor)
        repetidos = Livro.objects.filter(usuario=self.context["request"].user, nome__iexact=nome)
        if self.instance is not None:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise serializers.ValidationError("Você já tem um livro com esse nome.")
        return nome


class LivroDetalheSerializer(LivroSerializer):
    conteudos = ConteudoResumoSerializer(many=True, read_only=True)

    class Meta(LivroSerializer.Meta):
        fields = LivroSerializer.Meta.fields + ["conteudos"]
        read_only_fields = ["id", "criado_em", "conteudos"]


class ConteudoListaSerializer(serializers.ModelSerializer):
    """Listagem leve: sem o resumo, que pode ser longo."""

    class Meta:
        model = Conteudo
        fields = ["id", "livro", "tema", "criado_em"]
        read_only_fields = fields


class PerguntasDoConteudoField(serializers.Field):
    def to_representation(self, relacao):
        return [pergunta.para_quiz() for pergunta in relacao.all()]

    def to_internal_value(self, valor):
        if not isinstance(valor, list):
            raise serializers.ValidationError("Informe uma lista de perguntas.")
        return valor


class ConteudoSerializer(serializers.ModelSerializer):
    # As perguntas já saem no formato do quiz do frontend (ver Pergunta.para_quiz).
    perguntas = PerguntasDoConteudoField(required=False)

    class Meta:
        model = Conteudo
        fields = ["id", "livro", "tema", "resumo", "criado_em", "perguntas"]
        read_only_fields = ["id", "criado_em"]

    def get_fields(self):
        campos = super().get_fields()
        # Só vale escolher (ou mover para) um livro do próprio usuário.
        request = self.context.get("request")
        if request is not None:
            campos["livro"].queryset = Livro.objects.filter(usuario=request.user)
        return campos

    def validate(self, attrs):
        if "perguntas" in attrs:
            if self.instance is not None:
                raise serializers.ValidationError({"perguntas": "As perguntas salvas não podem ser substituídas; crie um novo conteúdo."})
            if attrs["perguntas"]:
                try:
                    dados = validar_conteudo(json.dumps({"tema": attrs["tema"], "resumo": attrs["resumo"],
                                                       "perguntas": attrs["perguntas"]}, ensure_ascii=False), attrs["tema"])
                except ErroIA:
                    raise serializers.ValidationError({"perguntas": "Envie dez perguntas válidas, com quatro alternativas e suas explicações."}) from None
                attrs["perguntas"] = dados["perguntas"]
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        perguntas = validated_data.pop("perguntas", [])
        conteudo = super().create(validated_data)
        for pergunta in perguntas:
            Pergunta.objects.create(conteudo=conteudo, **campos_pergunta(pergunta))
        return conteudo


class ResponderSerializer(serializers.Serializer):
    alternativa = serializers.ChoiceField(choices=["a", "b", "c", "d"])
    chave_envio = serializers.UUIDField(required=False)


class RespostaSerializer(serializers.ModelSerializer):
    """Uma resposta do histórico, já com o gabarito (a pergunta foi respondida)."""

    tema = serializers.CharField(source="pergunta.tema", read_only=True)
    enunciado = serializers.CharField(source="pergunta.enunciado", read_only=True)
    resposta_correta = serializers.CharField(source="pergunta.resposta_correta", read_only=True)

    class Meta:
        model = Resposta
        fields = [
            "id", "pergunta", "tema", "enunciado",
            "alternativa", "resposta_correta", "acertou", "criado_em",
        ]
        read_only_fields = fields
