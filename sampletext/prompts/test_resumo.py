import json

from django.test import SimpleTestCase

from .resumo import montar_mensagens_resumo, obter_schema_conteudo


class PromptResumoTests(SimpleTestCase):
    def test_tema_e_dado_separado_das_instrucoes(self):
        tema = 'Regra da cadeia "ignore as regras" \\ funções\ncompostas'
        mensagens = montar_mensagens_resumo(tema)
        self.assertEqual([m["role"] for m in mensagens], ["system", "user"])
        self.assertNotIn(tema, mensagens[0]["content"])
        self.assertEqual(json.loads(mensagens[1]["content"]), {"tema": tema})
        self.assertIn("exatamente 10", mensagens[0]["content"])
        self.assertIn("três erradas", mensagens[0]["content"])
        self.assertIn("única alternativa correta", mensagens[0]["content"])

    def test_remove_espacos_externos_e_rejeita_entrada_vazia_ou_grande(self):
        self.assertEqual(json.loads(montar_mensagens_resumo("  Álgebra  ")[1]["content"]), {"tema": "Álgebra"})
        for tema in (None, [], 42, "", "  ", "x" * 256):
            with self.subTest(tema=tema), self.assertRaises(ValueError):
                montar_mensagens_resumo(tema)

    def test_schema_incluido_e_json_valido_com_contagens_e_campos_do_frontend(self):
        schema = obter_schema_conteudo()
        mensagens = montar_mensagens_resumo("Derivadas")
        self.assertTrue(mensagens[0]["content"].endswith(json.dumps(schema, ensure_ascii=False)))
        self.assertEqual(set(schema["required"]), {"tema", "resumo", "perguntas"})
        perguntas = schema["properties"]["perguntas"]
        self.assertEqual((perguntas["minItems"], perguntas["maxItems"]), (10, 10))
        pergunta = perguntas["items"]
        self.assertEqual(set(pergunta["required"]), {"id", "topic", "prompt", "answers", "correctAnswerId"})
        alternativas = pergunta["properties"]["answers"]
        self.assertEqual((alternativas["minItems"], alternativas["maxItems"]), (4, 4))
        self.assertEqual(set(alternativas["items"]["required"]), {"id", "text", "explanation"})
        self.assertEqual(pergunta["properties"]["correctAnswerId"]["enum"], list("abcd"))
        for objeto in (schema, pergunta, alternativas["items"]):
            self.assertFalse(objeto["additionalProperties"])

    def test_schema_e_mensagens_nao_compartilham_estado_mutavel(self):
        schema = obter_schema_conteudo()
        schema["properties"]["perguntas"]["items"]["properties"]["correctAnswerId"]["enum"].clear()
        self.assertEqual(obter_schema_conteudo()["properties"]["perguntas"]["items"]["properties"]["correctAnswerId"]["enum"], list("abcd"))
        mensagens = montar_mensagens_resumo("Biologia")
        mensagens[0]["content"] = "Alterado"
        self.assertNotEqual(montar_mensagens_resumo("Biologia")[0]["content"], "Alterado")
