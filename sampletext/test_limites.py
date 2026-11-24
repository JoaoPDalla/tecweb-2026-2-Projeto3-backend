from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework.exceptions import Throttled
from rest_framework.test import APITestCase
from rest_framework.throttling import SimpleRateThrottle

from .models import Usuario
from .throttling import _formatar_espera, tratar_excecoes, verificar_limite_ia

CACHE_REAL = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "limites-teste"}}


def taxas(**novas):
    """Troca as taxas de limite só durante o teste."""
    return patch.dict(SimpleRateThrottle.THROTTLE_RATES, novas)


@override_settings(CACHES=CACHE_REAL)
class LimiteLoginTests(APITestCase):
    def setUp(self):
        cache.clear()

    def login(self, nome="Ana", **extra):
        return self.client.post(reverse("login"), {"nome": nome}, format="json", **extra)

    def test_bloqueia_depois_do_limite_com_mensagem_em_portugues(self):
        with taxas(login="3/min"):
            for _ in range(3):
                self.assertEqual(self.login().status_code, 201 if _ == 0 else 200)
            r = self.login()
        self.assertEqual(r.status_code, 429)
        self.assertIn("Muitas requisições", r.data["detail"])
        self.assertGreaterEqual(r.data["retry_after"], 1)
        self.assertIn("Retry-After", r.headers)

    def test_o_limite_vale_por_ip(self):
        with taxas(login="2/min"):
            self.login(REMOTE_ADDR="10.0.0.1")
            self.login(REMOTE_ADDR="10.0.0.1")
            self.assertEqual(self.login(REMOTE_ADDR="10.0.0.1").status_code, 429)
            self.assertEqual(self.login(REMOTE_ADDR="10.0.0.2").status_code, 200)


@override_settings(CACHES=CACHE_REAL)
class LimitePorUsuarioTests(APITestCase):
    def setUp(self):
        cache.clear()
        with taxas(login="100/min"):
            self.token_a = self.client.post(reverse("login"), {"nome": "Ana"}, format="json").data["token"]
            self.token_b = self.client.post(reverse("login"), {"nome": "Beto"}, format="json").data["token"]

    def me(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        return self.client.get(reverse("me"))

    def test_cada_usuario_tem_o_seu_proprio_limite(self):
        with taxas(user="2/min"):
            self.assertEqual(self.me(self.token_a).status_code, 200)
            self.assertEqual(self.me(self.token_a).status_code, 200)
            self.assertEqual(self.me(self.token_a).status_code, 429)
            self.assertEqual(self.me(self.token_b).status_code, 200)


@override_settings(CACHES=CACHE_REAL)
class LimiteIATests(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = SimpleNamespace(user=Usuario.objects.create(nome="Ana"), META={})
        self.beto = SimpleNamespace(user=Usuario.objects.create(nome="Beto"), META={})

    def test_limite_por_hora(self):
        with taxas(ia_hora="2/hour", ia_dia="100/day"):
            verificar_limite_ia(self.ana)
            verificar_limite_ia(self.ana)
            with self.assertRaises(Throttled) as erro:
                verificar_limite_ia(self.ana)
        self.assertGreater(erro.exception.wait, 0)

    def test_limite_por_dia(self):
        with taxas(ia_hora="100/hour", ia_dia="2/day"):
            verificar_limite_ia(self.ana)
            verificar_limite_ia(self.ana)
            with self.assertRaises(Throttled):
                verificar_limite_ia(self.ana)

    def test_um_usuario_nao_gasta_a_cota_do_outro(self):
        with taxas(ia_hora="1/hour", ia_dia="100/day"):
            verificar_limite_ia(self.ana)
            with self.assertRaises(Throttled):
                verificar_limite_ia(self.ana)
            verificar_limite_ia(self.beto)


class MensagemDoLimiteTests(SimpleTestCase):
    def resposta(self, espera):
        return tratar_excecoes(Throttled(wait=espera), {"view": None, "request": None})

    def test_formata_a_espera(self):
        self.assertEqual(_formatar_espera(1), "1 segundo")
        self.assertEqual(_formatar_espera(45), "45 segundos")
        self.assertEqual(_formatar_espera(600), "10 minutos")
        self.assertEqual(_formatar_espera(7200), "2 horas")

    def test_resposta_429(self):
        r = self.resposta(44.2)
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.data, {"detail": "Muitas requisições. Tente de novo em 45 segundos.", "retry_after": 45})

    def test_sem_tempo_de_espera(self):
        r = self.resposta(None)
        self.assertEqual(r.data, {"detail": "Muitas requisições. Tente de novo em alguns instantes."})


class ConfiguracaoDosLimitesTests(SimpleTestCase):
    def test_as_taxas_esperadas_existem(self):
        for escopo in ("user", "login", "ia_hora", "ia_dia"):
            self.assertIn(escopo, SimpleRateThrottle.THROTTLE_RATES)