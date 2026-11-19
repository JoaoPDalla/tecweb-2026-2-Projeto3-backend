from rest_framework import serializers

from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ["id", "nome"]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    nome = serializers.CharField(min_length=2, max_length=50)

    def validate_nome(self, valor):
        return Usuario.normalizar_nome(valor)
