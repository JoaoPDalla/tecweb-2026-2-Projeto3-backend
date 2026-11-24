from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .ai import services
from .ai.errors import ErroIA
from .cache_conteudo import obter_ou_gerar
from .throttling import verificar_limite_ia


class TemaSerializer(serializers.Serializer):
    tema = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)

    def validate_tema(self, valor):
        return " ".join(valor.split())

    def to_internal_value(self, data):
        if not isinstance(data, dict) or not isinstance(data.get("tema"), str):
            raise serializers.ValidationError({"tema": ["Informe um texto."]})
        return super().to_internal_value(data)


class ConteudoIAView(APIView):
    permission_classes = [IsAuthenticated]
    operacao = None

    def executar(self, tema, request):
        verificar_limite_ia(request, self)
        return self.operacao(tema)

    def post(self, request):
        entrada = TemaSerializer(data=request.data)
        if not entrada.is_valid():
            return Response({"code": "entrada_invalida", "detail": "Informe um tema com 1 a 255 caracteres.",
                             "errors": entrada.errors}, status=400)
        try:
            resultado = self.executar(entrada.validated_data["tema"], request)
        except ErroIA as erro:
            return Response({"code": erro.codigo, "detail": erro.mensagem}, status=erro.status)
        return Response(resultado)


class ValidarTemaView(ConteudoIAView):
    operacao = staticmethod(services.validar_tema)


class GerarConteudoView(ConteudoIAView):
    operacao = staticmethod(services.gerar_conteudo)

    def executar(self, tema, request):
        resultado, _ = obter_ou_gerar(
            tema, gerador=self.operacao,
            antes_de_gerar=lambda: verificar_limite_ia(request, self),
        )
        return resultado
