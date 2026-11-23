from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Pergunta, Resposta, Usuario


def dados_pergunta():
    return {
        "tema": "Derivadas",
        "enunciado": "Qual é a derivada de $x^2$?",
        "alternativas": [
            {"id": "a", "text": "$2x$", "explanation": "A regra da potência dá $2x$."},
            {"id": "b", "text": "$x$", "explanation": "Faltou multiplicar pelo expoente 2."},
            {"id": "c", "text": "$2$", "explanation": "A derivada ainda depende de x."},
            {"id": "d", "text": "$x^3$", "explanation": "Na derivação, o expoente diminui."},
        ],
        "resposta_correta": "a",
    }


class PerguntaTests(TestCase):
    def test_pergunta_sem_id_nao_pode_ser_exportada(self):
        with self.assertRaises(ValueError):
            Pergunta(**dados_pergunta()).para_quiz()

    def test_persistencia_e_contrato_do_frontend(self):
        pergunta = Pergunta.objects.create(**dados_pergunta())
        pergunta.refresh_from_db()
        self.assertEqual(pergunta.para_quiz(), {
            "id": str(pergunta.pk),
            "topic": "Derivadas",
            "prompt": "Qual é a derivada de $x^2$?",
            "answers": dados_pergunta()["alternativas"],
            "correctAnswerId": "a",
        })
        self.assertIsNotNone(pergunta.criado_em)
        exportada = pergunta.para_quiz()
        exportada["answers"][0]["text"] = "Modificada"
        self.assertEqual(pergunta.alternativas[0]["text"], "$2x$")

    def test_exige_quatro_alternativas_unicas_com_explicacoes(self):
        alternativas = dados_pergunta()["alternativas"]
        casos = [None, {}, "abcd", [], alternativas[:3], alternativas + [alternativas[0]]]
        for campo, valor in [
            ("id", "a"), ("id", "e"), ("id", ["b"]),
            ("text", "  "), ("explanation", ""), ("explanation", None),
        ]:
            alteradas = deepcopy(alternativas)
            alteradas[1][campo] = valor
            casos.append(alteradas)
        sem_explicacao = deepcopy(alternativas)
        del sem_explicacao[0]["explanation"]
        casos.append(sem_explicacao)
        for invalido in casos:
            with self.subTest(alternativas=invalido), self.assertRaises(ValidationError):
                Pergunta.objects.create(**{**dados_pergunta(), "alternativas": invalido})
        self.assertEqual(Pergunta.objects.count(), 0)

    def test_exige_tema_enunciado_e_gabarito_valido(self):
        for campo, valor in [
            ("tema", "  "), ("tema", "x" * 256), ("enunciado", "  "),
            ("resposta_correta", ""), ("resposta_correta", "e"),
            ("resposta_correta", "ab"),
        ]:
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ValidationError):
                Pergunta.objects.create(**{**dados_pergunta(), campo: valor})

    def test_banco_impede_gabarito_fora_das_alternativas(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Pergunta.objects.bulk_create([
                Pergunta(**{**dados_pergunta(), "resposta_correta": "e"}),
            ])


class RespostaTests(TestCase):
    def setUp(self):
        self.pergunta = Pergunta.objects.create(**dados_pergunta())
        self.usuario = Usuario.objects.create(nome="Matheus")

    def responder(self, alternativa, **extras):
        return Resposta.objects.create(
            usuario=self.usuario, pergunta=self.pergunta, alternativa=alternativa, **extras,
        )

    def test_registra_acerto_e_erro_sem_confiar_em_valor_fornecido(self):
        certa = self.responder("a", acertou=False)
        errada = self.responder("b", acertou=True)
        certa.refresh_from_db()
        errada.refresh_from_db()
        self.assertTrue(certa.acertou)
        self.assertFalse(errada.acertou)
        self.assertIsNotNone(certa.criado_em)
        self.assertEqual(self.usuario.respostas.count(), 2)
        self.assertEqual(self.pergunta.respostas.count(), 2)

    def test_preserva_resultado_registrado_se_gabarito_mudar_depois(self):
        resposta = self.responder("a")
        self.pergunta.resposta_correta = "b"
        self.pergunta.save()
        resposta.refresh_from_db()
        self.assertTrue(resposta.acertou)

    def test_historico_permite_repetir_e_separa_usuarios(self):
        primeira = self.responder("a")
        segunda = self.responder("b")
        outro = Usuario.objects.create(nome="Ana")
        Resposta.objects.create(usuario=outro, pergunta=self.pergunta, alternativa="c")
        self.assertEqual(list(self.usuario.respostas.values_list("pk", flat=True)), [primeira.pk, segunda.pk])
        self.assertEqual(outro.respostas.count(), 1)

    def test_rejeita_alternativa_inexistente_e_relacoes_ausentes(self):
        for valor in ("e", "", "ab"):
            with self.subTest(alternativa=valor), self.assertRaises(ValidationError):
                self.responder(valor)
        with self.assertRaises(ValidationError):
            Resposta.objects.create(pergunta=self.pergunta, alternativa="a")
        with self.assertRaises(ValidationError):
            Resposta.objects.create(usuario=self.usuario, pergunta_id=99999, alternativa="a")
        self.assertFalse(Resposta.objects.exists())

    def test_atualizacao_parcial_da_escolha_atualiza_acerto(self):
        resposta = self.responder("a")
        resposta.alternativa = "d"
        resposta.save(update_fields=["alternativa"])
        resposta.refresh_from_db()
        self.assertFalse(resposta.acertou)

    def test_exclusao_de_usuario_remove_apenas_suas_respostas(self):
        self.responder("b")
        self.usuario.delete()
        self.assertFalse(Resposta.objects.exists())
        self.assertTrue(Pergunta.objects.filter(pk=self.pergunta.pk).exists())
