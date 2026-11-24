from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Conteudo, Livro, Pergunta, Usuario


def entrar(client, nome):
    """Faz login (criando o usuário, se preciso) e deixa o token nas próximas requisições."""
    r = client.post(reverse("login"), {"nome": nome}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
    return Usuario.objects.get(nome=nome)


def alternativas():
    return [{"id": l, "text": f"Texto {l}", "explanation": f"Explicação {l}"} for l in "abcd"]


class LivroTests(APITestCase):
    def setUp(self):
        self.ana = entrar(self.client, "Ana")

    def test_exige_login(self):
        self.client.credentials()
        self.assertEqual(self.client.get(reverse("livro-list")).status_code, 401)

    def test_criar_normaliza_o_nome_e_lista(self):
        r = self.client.post(reverse("livro-list"), {"nome": "  Cálculo   I "}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["nome"], "Cálculo I")
        self.assertEqual(Livro.objects.get().usuario, self.ana)
        lista = self.client.get(reverse("livro-list"))
        self.assertEqual([livro["nome"] for livro in lista.data], ["Cálculo I"])

    def test_nome_invalido(self):
        for nome in ["", "   ", "x" * 101]:
            r = self.client.post(reverse("livro-list"), {"nome": nome}, format="json")
            self.assertEqual(r.status_code, 400, nome)
        self.assertEqual(Livro.objects.count(), 0)

    def test_nome_repetido_ignora_caixa_mas_outro_usuario_pode_repetir(self):
        self.client.post(reverse("livro-list"), {"nome": "Química"}, format="json")
        r = self.client.post(reverse("livro-list"), {"nome": "química"}, format="json")
        self.assertEqual(r.status_code, 400)
        entrar(self.client, "Bia")
        r = self.client.post(reverse("livro-list"), {"nome": "Química"}, format="json")
        self.assertEqual(r.status_code, 201)

    def test_usuario_nao_enxerga_nem_mexe_no_livro_de_outro(self):
        livro = Livro.objects.create(usuario=self.ana, nome="Química")
        entrar(self.client, "Bia")
        self.assertEqual(self.client.get(reverse("livro-list")).data, [])
        url = reverse("livro-detail", args=[livro.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, {"nome": "Roubado"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(Livro.objects.filter(pk=livro.pk, nome="Química").exists())

    def test_abrir_livro_traz_os_conteudos(self):
        livro = Livro.objects.create(usuario=self.ana, nome="Cálculo I")
        Conteudo.objects.create(usuario=self.ana, livro=livro, tema="Limite", resumo="...")
        Conteudo.objects.create(usuario=self.ana, livro=livro, tema="Derivadas", resumo="...")
        r = self.client.get(reverse("livro-detail", args=[livro.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["nome"], "Cálculo I")
        self.assertEqual([c["tema"] for c in r.data["conteudos"]], ["Limite", "Derivadas"])

    def test_renomear(self):
        livro = Livro.objects.create(usuario=self.ana, nome="Calculo")
        r = self.client.patch(reverse("livro-detail", args=[livro.pk]), {"nome": "Cálculo I"}, format="json")
        self.assertEqual(r.status_code, 200)
        livro.refresh_from_db()
        self.assertEqual(livro.nome, "Cálculo I")

    def test_excluir_livro_exclui_os_conteudos(self):
        livro = Livro.objects.create(usuario=self.ana, nome="Cálculo I")
        Conteudo.objects.create(usuario=self.ana, livro=livro, tema="Limite", resumo="...")
        r = self.client.delete(reverse("livro-detail", args=[livro.pk]))
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Livro.objects.count(), 0)
        self.assertEqual(Conteudo.objects.count(), 0)


class ConteudoTests(APITestCase):
    def setUp(self):
        self.ana = entrar(self.client, "Ana")
        self.calculo = Livro.objects.create(usuario=self.ana, nome="Cálculo I")
        self.quimica = Livro.objects.create(usuario=self.ana, nome="Química")

    def novo(self, livro=None, tema="Regra da cadeia"):
        return Conteudo.objects.create(
            usuario=self.ana, livro=livro or self.calculo, tema=tema, resumo="**Resumo**"
        )

    def test_exige_login(self):
        self.client.credentials()
        self.assertEqual(self.client.get(reverse("conteudo-list")).status_code, 401)

    def test_salvar_em_um_livro_proprio(self):
        corpo = {"livro": self.calculo.pk, "tema": "Regra da cadeia", "resumo": "**Resumo**"}
        r = self.client.post(reverse("conteudo-list"), corpo, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["livro"], self.calculo.pk)
        self.assertEqual(r.data["perguntas"], [])
        self.assertEqual(Conteudo.objects.get().usuario, self.ana)

    def test_salvar_exige_livro_tema_e_resumo(self):
        base = {"livro": self.calculo.pk, "tema": "Limite", "resumo": "..."}
        for campo in ["livro", "tema", "resumo"]:
            corpo = {k: v for k, v in base.items() if k != campo}
            r = self.client.post(reverse("conteudo-list"), corpo, format="json")
            self.assertEqual(r.status_code, 400, campo)
        for campo in ["tema", "resumo"]:
            r = self.client.post(reverse("conteudo-list"), {**base, campo: "   "}, format="json")
            self.assertEqual(r.status_code, 400, campo)
        self.assertEqual(Conteudo.objects.count(), 0)

    def test_nao_salva_no_livro_de_outro_usuario(self):
        bia = Usuario.objects.create(nome="Bia")
        livro_da_bia = Livro.objects.create(usuario=bia, nome="Física")
        corpo = {"livro": livro_da_bia.pk, "tema": "Limite", "resumo": "..."}
        r = self.client.post(reverse("conteudo-list"), corpo, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("livro", r.data)

    def test_listar_sem_resumo_e_filtrar_por_livro(self):
        self.novo(self.calculo, "Limite")
        self.novo(self.quimica, "Estequiometria")
        todos = self.client.get(reverse("conteudo-list"))
        self.assertEqual(len(todos.data), 2)
        self.assertNotIn("resumo", todos.data[0])
        filtrados = self.client.get(reverse("conteudo-list"), {"livro": self.quimica.pk})
        self.assertEqual([c["tema"] for c in filtrados.data], ["Estequiometria"])

    def test_filtro_invalido_retorna_400(self):
        self.assertEqual(self.client.get(reverse("conteudo-list"), {"livro": "abc"}).status_code, 400)

    def test_abrir_traz_resumo_e_perguntas_no_formato_do_quiz(self):
        conteudo = self.novo()
        pergunta = Pergunta.objects.create(
            tema="Derivadas", enunciado="Quanto é $2x$?", alternativas=alternativas(),
            resposta_correta="a", conteudo=conteudo,
        )
        r = self.client.get(reverse("conteudo-detail", args=[conteudo.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["resumo"], "**Resumo**")
        self.assertEqual(r.data["perguntas"], [pergunta.para_quiz()])

    def test_mover_para_outro_livro(self):
        conteudo = self.novo(self.calculo)
        r = self.client.patch(
            reverse("conteudo-detail", args=[conteudo.pk]), {"livro": self.quimica.pk}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        conteudo.refresh_from_db()
        self.assertEqual(conteudo.livro_id, self.quimica.pk)
        self.assertEqual(conteudo.tema, "Regra da cadeia")

    def test_nao_move_para_livro_de_outro_usuario(self):
        bia = Usuario.objects.create(nome="Bia")
        livro_da_bia = Livro.objects.create(usuario=bia, nome="Física")
        conteudo = self.novo()
        r = self.client.patch(
            reverse("conteudo-detail", args=[conteudo.pk]), {"livro": livro_da_bia.pk}, format="json"
        )
        self.assertEqual(r.status_code, 400)
        conteudo.refresh_from_db()
        self.assertEqual(conteudo.livro_id, self.calculo.pk)

    def test_excluir(self):
        conteudo = self.novo()
        r = self.client.delete(reverse("conteudo-detail", args=[conteudo.pk]))
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Conteudo.objects.count(), 0)
        self.assertEqual(Livro.objects.count(), 2)

    def test_usuario_nao_enxerga_nem_mexe_no_conteudo_de_outro(self):
        conteudo = self.novo()
        entrar(self.client, "Bia")
        self.assertEqual(self.client.get(reverse("conteudo-list")).data, [])
        url = reverse("conteudo-detail", args=[conteudo.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(Conteudo.objects.count(), 1)
