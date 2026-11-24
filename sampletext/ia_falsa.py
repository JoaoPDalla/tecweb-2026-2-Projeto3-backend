"""IA de mentirinha para testes e desenvolvimento (issue #11): sem rede, sem chave e sem custo."""

import json
from copy import deepcopy

LETRAS = "abcd"


def conteudo_falso(tema="Regra da cadeia", quantidade=10):
    """Conteúdo no formato do contrato (prompts/resumo.py): tema, resumo e perguntas."""
    perguntas = []
    for i in range(1, quantidade + 1):
        correta = LETRAS[(i - 1) % 4]
        respostas = [
            {
                "id": letra,
                "text": f"Alternativa {letra.upper()} da pergunta {i}",
                "explanation": (
                    f"A alternativa {letra.upper()} está correta porque aplica a regra de {tema}."
                    if letra == correta
                    else f"A alternativa {letra.upper()} está errada: confunde um passo de {tema}."
                ),
            }
            for letra in LETRAS
        ]
        perguntas.append(
            {
                "id": f"pergunta-{i}",
                "topic": tema,
                "prompt": f"Pergunta {i} sobre {tema}: quanto vale $x^2$ para $x = {i}$?",
                "answers": respostas,
                "correctAnswerId": correta,
            }
        )
    return {
        "tema": tema,
        "resumo": f"## {tema}\n\nResumo de exemplo sobre {tema}, com a fórmula $f(x) = x^2$.",
        "perguntas": perguntas,
    }


class IAFalsa:
    """Troca o cliente de IA de verdade nos testes.

    - `conteudo`: dict (ou função tema -> dict) para devolver no lugar do conteúdo padrão.
    - `falhas`: exceções levantadas, uma por chamada, nas primeiras chamadas (ex.: [TimeoutError()]).
    - `texto_bruto`: em `gerar()`, devolve este texto em vez do JSON (ex.: um JSON quebrado).
    - `chamadas` guarda os temas pedidos; `total_chamadas` diz quantas vezes a "IA" foi usada.
    """

    def __init__(self, conteudo=None, falhas=(), texto_bruto=None):
        self._conteudo = conteudo
        self._falhas = list(falhas)
        self.texto_bruto = texto_bruto
        self.chamadas = []

    @property
    def total_chamadas(self):
        return len(self.chamadas)

    def gerar_conteudo(self, tema):
        """Versão que já devolve o dict (serve de `gerador` em `obter_ou_gerar`)."""
        self.chamadas.append(tema)
        if self._falhas:
            falha = self._falhas.pop(0)
            raise falha if isinstance(falha, BaseException) else falha()
        if callable(self._conteudo):
            return self._conteudo(tema)
        if self._conteudo is not None:
            return deepcopy(self._conteudo)
        return conteudo_falso(tema)

    def gerar(self, mensagens):
        """Versão no formato de um provedor: recebe as mensagens system/user e devolve texto JSON."""
        tema = json.loads(mensagens[-1]["content"])["tema"]
        conteudo = self.gerar_conteudo(tema)
        if self.texto_bruto is not None:
            return self.texto_bruto
        return json.dumps(conteudo, ensure_ascii=False)