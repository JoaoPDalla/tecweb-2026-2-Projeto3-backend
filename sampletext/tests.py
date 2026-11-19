from types import SimpleNamespace

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import TokenUsuario, Usuario
from .permissions import IsDono


class LoginTests(APITestCase):
    def login(self, nome):
        return self.client.post(reverse("login"), {"nome": nome}, format="json")

    def test_primeiro_login_cria_usuario(self):
        r = self.login("Luan")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["criado"])
        self.assertEqual(r.data["usuario"]["nome"], "Luan")
        self.assertEqual(len(r.data["token"]), 40)
        self.assertEqual(Usuario.objects.count(), 1)

    def test_login_repetido_reaproveita_usuario_e_token(self):
        primeiro = self.login("Luan")
        segundo = self.login("Luan")
        self.assertEqual(segundo.status_code, 200)
        self.assertFalse(segundo.data["criado"])
        self.assertEqual(primeiro.data["token"], segundo.data["token"])
        self.assertEqual(Usuario.objects.count(), 1)

    def test_nome_ignora_caixa_e_espacos_extras(self):
        self.login("Luan Miguel")
        r = self.login("  luan   MIGUEL ")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Usuario.objects.count(), 1)

    def test_nome_invalido(self):
        for nome in ["", "   ", "a", "x" * 51]:
            self.assertEqual(self.login(nome).status_code, 400, nome)
        self.assertEqual(self.client.post(reverse("login"), {}, format="json").status_code, 400)
        self.assertEqual(Usuario.objects.count(), 0)


class AutenticacaoTests(APITestCase):
    def setUp(self):
        r = self.client.post(reverse("login"), {"nome": "Ana"}, format="json")
        self.token = r.data["token"]

    def test_me_sem_token_retorna_401(self):
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)

    def test_me_com_token_invalido_retorna_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token invalido")
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)

    def test_me_com_token_valido(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")
        r = self.client.get(reverse("me"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["nome"], "Ana")

    def test_logout_invalida_token_e_novo_login_gera_outro(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")
        self.assertEqual(self.client.post(reverse("logout")).status_code, 204)
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)
        self.assertFalse(TokenUsuario.objects.exists())
        self.client.credentials()
        novo = self.client.post(reverse("login"), {"nome": "Ana"}, format="json")
        self.assertNotEqual(novo.data["token"], self.token)


class PermissaoDonoTests(SimpleTestCase):
    def test_dono_pode_e_outro_usuario_nao(self):
        perm = IsDono()
        req = SimpleNamespace(user=SimpleNamespace(pk=1))
        self.assertTrue(perm.has_object_permission(req, None, SimpleNamespace(usuario_id=1)))
        self.assertFalse(perm.has_object_permission(req, None, SimpleNamespace(usuario_id=2)))
