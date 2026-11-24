import json

from django.test import TestCase

from .ia_falsa import IAFalsa, conteudo_falso
from .models import Pergunta
from .prompts.resumo import montar_mensagens_resumo, obter_schema_conteudo


class ConteudoFalsoTests(TestCase):
    def test_segue_o_contrato_do_prompt(self):
        schema = obter_schema_conteudo()
        conteudo = conteudo_falso("Derivadas")
        self.assertEqual(set(conteudo), set(schema["required"]))
        self.assertEqual(conteudo["tema"], "Derivadas")
        self.assertEqual(len(conteudo["perguntas"]), schema["properties"]["perguntas"]["maxItems"])

        ids = set()
        for pergunta in conteudo["perguntas"]:
            with self.subTest(pergunta=pergunta["id"]):
                self.assertEqual(set(pergunta), set(schema["properties"]["perguntas"]["items"]["required"]))
                self.assertEqual(pergunta["topic"], "Derivadas")
                self.assertEqual([a["id"] for a in pergunta["answers"]], list("abcd"))
                self.assertIn(pergunta["correctAnswerId"], list("abcd"))
                self.assertTrue(all(a["text"].strip() and a["explanation"].strip() for a in pergunta["answers"]))
                ids.add(pergunta["id"])
        self.assertEqual(len(ids), 10)

    def test_gabarito_varia_entre_as_letras(self):
        corretas = {p["correctAnswerId"] for p in conteudo_falso()["perguntas"]}
        self.assertEqual(corretas, set("abcd"))

    def test_cada_pergunta_cabe_no_model_pergunta(self):
        for p in conteudo_falso("Limites")["perguntas"]:
            salva = Pergunta.objects.create(
                tema=p["topic"], enunciado=p["prompt"], alternativas=p["answers"], resposta_correta=p["correctAnswerId"]
            )
            quiz = salva.para_quiz()
            self.assertEqual(quiz["answers"], p["answers"])
            self.assertEqual(quiz["correctAnswerId"], p["correctAnswerId"])


class IAFalsaTests(TestCase):
    def test_gerar_recebe_as_mensagens_do_prompt_e_devolve_json(self):
        ia = IAFalsa()
        texto = ia.gerar(montar_mensagens_resumo("Regra da cadeia"))
        conteudo = json.loads(texto)
        self.assertEqual(conteudo["tema"], "Regra da cadeia")
        self.assertEqual(len(conteudo["perguntas"]), 10)
        self.assertEqual(ia.chamadas, ["Regra da cadeia"])

    def test_conta_chamadas(self):
        ia = IAFalsa()
        ia.gerar_conteudo("A")
        ia.gerar_conteudo("B")
        self.assertEqual(ia.total_chamadas, 2)
        self.assertEqual(ia.chamadas, ["A", "B"])

    def test_falhas_acontecem_na_ordem_e_depois_volta_ao_normal(self):
        ia = IAFalsa(falhas=[TimeoutError("lenta demais"), ConnectionError])
        with self.assertRaises(TimeoutError):
            ia.gerar_conteudo("A")
        with self.assertRaises(ConnectionError):
            ia.gerar_conteudo("A")
        self.assertEqual(ia.gerar_conteudo("A")["tema"], "A")
        self.assertEqual(ia.total_chamadas, 3)

    def test_conteudo_personalizado_e_texto_bruto(self):
        ia = IAFalsa(conteudo={"tema": "X", "resumo": "r", "perguntas": []})
        self.assertEqual(ia.gerar_conteudo("qualquer")["resumo"], "r")

        quebrada = IAFalsa(texto_bruto="isto não é JSON {")
        texto = quebrada.gerar(montar_mensagens_resumo("Tema"))
        self.assertEqual(texto, "isto não é JSON {")
        with self.assertRaises(json.JSONDecodeError):
            json.loads(texto)

    def test_conteudo_como_funcao_do_tema(self):
        ia = IAFalsa(conteudo=lambda tema: conteudo_falso(tema.upper(), quantidade=2))
        resultado = ia.gerar_conteudo("limites")
        self.assertEqual(resultado["tema"], "LIMITES")
        self.assertEqual(len(resultado["perguntas"]), 2)