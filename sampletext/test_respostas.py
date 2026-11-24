from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Conteudo, Livro, Pergunta, Resposta, Usuario


def entrar(client, nome):
    r = client.post(reverse("login"), {"nome": nome}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
    return Usuario.objects.get(nome=nome)


def criar_pergunta(conteudo=None, correta="a"):
    return Pergunta.objects.create(
        tema="Derivadas",
        enunciado="Qual é a derivada de $x^2$?",
        alternativas=[{"id": l, "text": f"Texto {l}", "explanation": f"Explicação {l}"} for l in "abcd"],
        resposta_correta=correta,
        conteudo=conteudo,
    )


class ResponderTests(APITestCase):
    def setUp(self):
        self.ana = entrar(self.client, "Ana")
        self.pergunta = criar_pergunta(correta="a")
        self.url = reverse("responder", args=[self.pergunta.pk])

    def test_exige_login(self):
        self.client.credentials()
        r = self.client.post(self.url, {"alternativa": "a"}, format="json")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(Resposta.objects.count(), 0)

    def test_resposta_certa(self):
        r = self.client.post(self.url, {"alternativa": "a"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["acertou"])
        self.assertEqual(r.data["resposta_correta"], "a")
        self.assertEqual(r.data["pergunta"], self.pergunta.pk)
        resposta = Resposta.objects.get()
        self.assertEqual(resposta.usuario, self.ana)
        self.assertEqual(resposta.alternativa, "a")

    def test_resposta_errada(self):
        r = self.client.post(self.url, {"alternativa": "c"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data["acertou"])
        self.assertEqual(r.data["resposta_correta"], "a")

    def test_alternativa_invalida_ou_ausente(self):
        for corpo in [{"alternativa": "e"}, {"alternativa": ""}, {}]:
            self.assertEqual(self.client.post(self.url, corpo, format="json").status_code, 400, corpo)
        self.assertEqual(Resposta.objects.count(), 0)

    def test_pergunta_inexistente(self):
        url = reverse("responder", args=[999999])
        self.assertEqual(self.client.post(url, {"alternativa": "a"}, format="json").status_code, 404)

    def test_pode_responder_de_novo_e_cada_tentativa_fica_no_historico(self):
        self.client.post(self.url, {"alternativa": "b"}, format="json")
        self.client.post(self.url, {"alternativa": "a"}, format="json")
        self.assertEqual(Resposta.objects.filter(usuario=self.ana, pergunta=self.pergunta).count(), 2)


class HistoricoTests(APITestCase):
    def setUp(self):
        self.ana = entrar(self.client, "Ana")
        livro = Livro.objects.create(usuario=self.ana, nome="Cálculo I")
        self.conteudo = Conteudo.objects.create(usuario=self.ana, livro=livro, tema="Derivadas", resumo="...")
        self.p1 = criar_pergunta(conteudo=self.conteudo)
        self.p2 = criar_pergunta()  # sem conteúdo

    def responder(self, pergunta, alternativa):
        url = reverse("responder", args=[pergunta.pk])
        return self.client.post(url, {"alternativa": alternativa}, format="json")

    def test_exige_login(self):
        self.client.credentials()
        self.assertEqual(self.client.get(reverse("respostas")).status_code, 401)

    def test_lista_so_as_do_usuario_da_mais_recente_para_a_mais_antiga(self):
        self.responder(self.p1, "b")
        self.responder(self.p1, "a")
        entrar(self.client, "Bia")
        self.responder(self.p1, "c")
        entrar(self.client, "Ana")

        r = self.client.get(reverse("respostas"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 2)
        self.assertEqual([item["alternativa"] for item in r.data["results"]], ["a", "b"])
        primeiro = r.data["results"][0]
        self.assertTrue(primeiro["acertou"])
        self.assertEqual(primeiro["tema"], "Derivadas")
        self.assertEqual(primeiro["resposta_correta"], "a")

    def test_filtrar_por_pergunta_e_por_conteudo(self):
        self.responder(self.p1, "a")
        self.responder(self.p2, "a")
        por_pergunta = self.client.get(reverse("respostas"), {"pergunta": self.p2.pk})
        self.assertEqual(por_pergunta.data["count"], 1)
        self.assertEqual(por_pergunta.data["results"][0]["pergunta"], self.p2.pk)
        por_conteudo = self.client.get(reverse("respostas"), {"conteudo": self.conteudo.pk})
        self.assertEqual(por_conteudo.data["count"], 1)
        self.assertEqual(por_conteudo.data["results"][0]["pergunta"], self.p1.pk)

    def test_filtro_invalido_retorna_400(self):
        self.assertEqual(self.client.get(reverse("respostas"), {"pergunta": "abc"}).status_code, 400)
        self.assertEqual(self.client.get(reverse("respostas"), {"conteudo": "-1"}).status_code, 400)

    def test_paginacao(self):
        self.responder(self.p1, "a")
        self.responder(self.p1, "b")
        r = self.client.get(reverse("respostas"), {"limit": 1})
        self.assertEqual(r.data["count"], 2)
        self.assertEqual(len(r.data["results"]), 1)
        self.assertIsNotNone(r.data["next"])

    def test_historico_vazio(self):
        r = self.client.get(reverse("respostas"))
        self.assertEqual(r.data["count"], 0)
        self.assertEqual(r.data["results"], [])
