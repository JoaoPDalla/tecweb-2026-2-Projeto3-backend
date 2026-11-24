from rest_framework import serializers

from .models import Conteudo, Livro, Resposta, Usuario


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


class ConteudoSerializer(serializers.ModelSerializer):
    # As perguntas já saem no formato do quiz do frontend (ver Pergunta.para_quiz).
    perguntas = serializers.SerializerMethodField()

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

    def get_perguntas(self, conteudo):
        return [pergunta.para_quiz() for pergunta in conteudo.perguntas.all()]


class ResponderSerializer(serializers.Serializer):
    alternativa = serializers.ChoiceField(choices=["a", "b", "c", "d"])


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
