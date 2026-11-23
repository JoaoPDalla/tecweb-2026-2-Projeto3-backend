from django.core.exceptions import ValidationError


def validar_alternativas(valor):
    """Valida o campo do modelo, não a resposta completa do provedor de IA (#13)."""
    if not isinstance(valor, list) or len(valor) != 4:
        raise ValidationError("Informe exatamente quatro alternativas.")

    ids = []
    for alternativa in valor:
        if not isinstance(alternativa, dict) or set(alternativa) != {"id", "text", "explanation"}:
            raise ValidationError("Cada alternativa deve ter id, text e explanation.")
        if not all(isinstance(item, str) and item.strip() for item in alternativa.values()):
            raise ValidationError("Os campos das alternativas devem ser textos não vazios.")
        ids.append(alternativa["id"])

    if set(ids) != set("abcd"):
        raise ValidationError("As alternativas devem ter IDs únicos: a, b, c e d.")
