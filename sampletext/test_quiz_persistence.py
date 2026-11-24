import uuid
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from .ai.test_generation import TEMA, classificacao, material, resposta_sdk
from .models import Conteudo, ConteudoGerado, Livro, Pergunta, Resposta, TokenUsuario, Usuario
from .quiz_persistence import perguntas_da_geracao


class PerguntasGeradasTests(TestCase):
    def test_ids_reais_estaveis_sem_modificar_o_material_do_cache(self):
        origem = material()
        primeira = perguntas_da_geracao(origem)
        segunda = perguntas_da_geracao(origem)
        self.assertEqual(primeira, segunda)
        self.assertEqual(Pergunta.objects.count(), 10)
        self.assertEqual(origem["perguntas"][0]["id"], "pergunta-1")
        self.assertTrue(all(q["id"].isdigit() for q in primeira["perguntas"]))
        self.assertFalse(Pergunta.objects.exclude(conteudo=None).exists())


class PersistenciaQuizTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create(nome="Matheus")
        self.outro = Usuario.objects.create(nome="Ana")
        self.livro = Livro.objects.create(usuario=self.usuario, nome="Cálculo")
        self.outro_livro = Livro.objects.create(usuario=self.outro, nome="Física")
        self.autenticar(self.usuario)

    def autenticar(self, usuario):
        token, _ = TokenUsuario.objects.get_or_create(usuario=usuario)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def salvar(self, **extras):
        return self.client.post(reverse("conteudo-list"), {"livro": self.livro.pk, **material(), **extras}, format="json")

    def responder(self, pergunta, alternativa="a", chave=None):
        dados = {"alternativa": alternativa}
        if chave is not None: dados["chave_envio"] = str(chave)
        return self.client.post(reverse("responder", args=[pergunta]), dados, format="json")

    @override_settings(GEMINI_API_KEY="chave-teste", GEMINI_MODEL="gemini-3.8-flash")
    @patch("sampletext.ai.client.genai.Client")
    def test_gemini_geracao_cache_salvamento_e_historico_compativeis(self, sdk):
        gerar = sdk.return_value.models.generate_content
        gerar.side_effect = [resposta_sdk(classificacao()), resposta_sdk(material())]
        rota = reverse("gerar-conteudo")

        gerado = self.client.post(rota, {"tema": TEMA}, format="json")
        self.assertEqual(gerado.status_code, 200)
        self.assertEqual(Pergunta.objects.count(), 10)
        self.assertEqual(Conteudo.objects.count(), 0)
        self.assertEqual(ConteudoGerado.objects.get().perguntas, material()["perguntas"])
        em_cache = self.client.post(rota, {"tema": TEMA.lower()}, format="json")
        self.assertEqual(em_cache.status_code, 200)
        self.assertEqual(em_cache.data, gerado.data)
        self.assertEqual(gerar.call_count, 2)

        salvo = self.salvar(**gerado.data)
        self.assertEqual(salvo.status_code, 201)
        self.assertEqual(Pergunta.objects.count(), 20)
        reaberto = self.client.get(reverse("conteudo-detail", args=[salvo.data["id"]]))
        self.assertEqual(reaberto.status_code, 200)
        self.assertEqual(reaberto.data, salvo.data)
        self.assertEqual(len(reaberto.data["perguntas"]), 10)
        ids_geracao = {q["id"] for q in gerado.data["perguntas"]}
        self.assertFalse(ids_geracao & {q["id"] for q in reaberto.data["perguntas"]})

        pergunta = reaberto.data["perguntas"][0]["id"]
        chave = uuid.uuid4()
        resposta = self.responder(pergunta, chave=chave)
        repetida = self.responder(pergunta, chave=chave)
        self.assertEqual((resposta.status_code, repetida.status_code), (201, 200))
        self.assertEqual(resposta.data, repetida.data)
        self.assertTrue(resposta.data["acertou"])
        historico = self.client.get(reverse("respostas"), {"conteudo": salvo.data["id"]})
        self.assertEqual(historico.status_code, 200)
        self.assertEqual(historico.data["count"], 1)
        self.assertEqual(historico.data["results"][0], resposta.data)

    def test_salva_e_reabre_conteudo_com_dez_perguntas_e_ids_de_banco(self):
        geradas = perguntas_da_geracao(material())
        resposta = self.salvar(perguntas=geradas["perguntas"])
        self.assertEqual(resposta.status_code, 201)
        conteudo = Conteudo.objects.get(pk=resposta.data["id"])
        self.assertEqual(conteudo.perguntas.count(), 10)
        ids_geracao = {q["id"] for q in geradas["perguntas"]}
        ids_salvos = {q["id"] for q in resposta.data["perguntas"]}
        self.assertFalse(ids_geracao & ids_salvos)
        reaberto = self.client.get(reverse("conteudo-detail", args=[conteudo.pk]))
        self.assertEqual(reaberto.data, resposta.data)
        for recebida, original in zip(resposta.data["perguntas"], material()["perguntas"]):
            self.assertEqual({**recebida, "id": original["id"]}, original)

    def test_cliente_antigo_pode_salvar_so_o_resumo(self):
        dados = material()
        del dados["perguntas"]
        resposta = self.client.post(reverse("conteudo-list"), {"livro": self.livro.pk, **dados}, format="json")
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.data["perguntas"], [])

    def test_rejeita_perguntas_invalidas_sem_deixar_conteudo_parcial(self):
        for defeito in ("quantidade", "gabarito", "tema", "explicacao"):
            perguntas = material()["perguntas"]
            if defeito == "quantidade": perguntas.pop()
            elif defeito == "gabarito": perguntas[0]["correctAnswerId"] = "e"
            elif defeito == "tema": perguntas[0]["topic"] = "Outro"
            else: perguntas[0]["answers"][0]["explanation"] = ""
            self.assertEqual(self.salvar(perguntas=perguntas).status_code, 400)
        self.assertEqual(Conteudo.objects.count(), 0)
        self.assertEqual(Pergunta.objects.count(), 0)

    def test_falha_ao_criar_questao_desfaz_todo_o_salvamento(self):
        criar = Pergunta.objects.create
        chamadas = 0
        def com_falha(*args, **kwargs):
            nonlocal chamadas
            chamadas += 1
            if chamadas == 2: raise RuntimeError("Falha simulada")
            return criar(*args, **kwargs)
        with patch("sampletext.serializers.Pergunta.objects.create", side_effect=com_falha):
            with self.assertRaises(RuntimeError): self.salvar()
        self.assertFalse(Conteudo.objects.exists())
        self.assertFalse(Pergunta.objects.exists())

    def test_permissoes_e_edicao_de_metadados_preservam_perguntas(self):
        self.assertEqual(self.salvar(livro=self.outro_livro.pk).status_code, 400)
        salvo = self.salvar().data
        rota = reverse("conteudo-detail", args=[salvo["id"]])
        ids = [q["id"] for q in salvo["perguntas"]]
        mudado = self.client.patch(rota, {"tema": "Título de revisão"}, format="json")
        self.assertEqual(mudado.status_code, 200)
        self.assertEqual([q["id"] for q in mudado.data["perguntas"]], ids)
        self.assertEqual(self.client.patch(rota, {"perguntas": []}, format="json").status_code, 400)
        self.autenticar(self.outro)
        self.assertEqual(self.client.get(rota).status_code, 404)

    def test_respostas_de_conteudo_salvo_aparecem_no_historico_do_dono_da_resposta(self):
        salvo = self.salvar().data
        pergunta = salvo["perguntas"][0]["id"]
        r = self.responder(pergunta, chave=uuid.uuid4())
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["acertou"])
        historico = self.client.get(reverse("respostas"), {"conteudo": salvo["id"]})
        self.assertEqual(historico.data["count"], 1)
        self.assertEqual(historico.data["results"][0]["id"], r.data["id"])
        self.autenticar(self.outro)
        self.assertEqual(self.client.get(reverse("respostas")).data["count"], 0)

    def test_quiz_nao_salvo_tambem_pode_registrar_respostas(self):
        perguntas = perguntas_da_geracao(material())["perguntas"]
        self.assertEqual(self.responder(perguntas[0]["id"], "b", uuid.uuid4()).status_code, 201)
        self.assertFalse(Resposta.objects.get().acertou)
        self.assertEqual(self.client.get(reverse("respostas")).data["count"], 1)
        self.assertFalse(Conteudo.objects.exists())

    def test_repeticao_do_mesmo_envio_e_idempotente_e_nova_tentativa_e_independente(self):
        pergunta = self.salvar().data["perguntas"][0]["id"]
        chave = uuid.uuid4()
        a, b = self.responder(pergunta, chave=chave), self.responder(pergunta, chave=chave)
        self.assertEqual((a.status_code, b.status_code), (201, 200))
        self.assertEqual(a.data, b.data)
        self.assertEqual(Resposta.objects.count(), 1)
        self.assertEqual(self.responder(pergunta, "b", chave).status_code, 409)
        self.assertEqual(Resposta.objects.count(), 1)
        self.assertEqual(self.responder(pergunta, "b", uuid.uuid4()).status_code, 201)
        self.assertEqual(Resposta.objects.count(), 2)

    def test_chaves_sao_isoladas_por_usuario_e_protegidas_no_banco(self):
        pergunta = self.salvar().data["perguntas"][0]["id"]
        chave = uuid.uuid4()
        self.responder(pergunta, chave=chave)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Resposta.objects.bulk_create([Resposta(usuario=self.usuario, pergunta_id=pergunta, alternativa="a", acertou=True, chave_envio=chave)])
        self.autenticar(self.outro)
        self.assertEqual(self.responder(pergunta, chave=chave).status_code, 201)
        self.assertEqual(Resposta.objects.count(), 2)

    def test_envio_antigo_sem_chave_continua_criando_registros_e_uuid_invalida_e_recusada(self):
        pergunta = self.salvar().data["perguntas"][0]["id"]
        self.assertEqual(self.responder(pergunta).status_code, 201)
        self.assertEqual(self.responder(pergunta).status_code, 201)
        self.assertEqual(self.responder(pergunta, chave="nao-e-uuid").status_code, 400)
        self.assertEqual(Resposta.objects.count(), 2)
