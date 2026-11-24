from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.exceptions import Throttled
from rest_framework.throttling import SimpleRateThrottle

from .cache_conteudo import chave_do_tema, invalidar_tema, obter_ou_gerar
from .ia_falsa import IAFalsa, conteudo_falso
from .models import ConteudoGerado, Usuario
from .throttling import verificar_limite_ia

CACHE_REAL = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "cache-conteudo-teste"}}


class ChaveDoTemaTests(SimpleTestCase):
    def test_ignora_caixa_acentos_e_espacos(self):
        esperado = chave_do_tema("Cálculo I")
        self.assertEqual(esperado, "calculo i")
        for variacao in ("calculo i", "  CÁLCULO    I ", "Calculo\tI"):
            self.assertEqual(chave_do_tema(variacao), esperado)

    def test_temas_diferentes_tem_chaves_diferentes(self):
        self.assertNotEqual(chave_do_tema("Cálculo I"), chave_do_tema("Cálculo II"))

    def test_rejeita_tema_invalido(self):
        for tema in (None, 42, [], "", "   ", "x" * 256):
            with self.subTest(tema=tema), self.assertRaises(ValueError):
                chave_do_tema(tema)


class ObterOuGerarTests(TestCase):
    def setUp(self):
        self.ia = IAFalsa()

    def pedir(self, tema, **extra):
        return obter_ou_gerar(tema, self.ia.gerar_conteudo, **extra)

    def test_primeira_vez_gera_e_guarda_a_segunda_vem_do_cache(self):
        primeiro, do_cache = self.pedir("Regra da cadeia")
        self.assertFalse(do_cache)
        segundo, do_cache = self.pedir("Regra da cadeia")
        self.assertTrue(do_cache)
        self.assertEqual(primeiro, segundo)
        self.assertEqual(self.ia.total_chamadas, 1)
        self.assertEqual(ConteudoGerado.objects.count(), 1)

    def test_guarda_o_conteudo_completo(self):
        conteudo, _ = self.pedir("Derivadas")
        guardado = ConteudoGerado.objects.get().como_dict()
        self.assertEqual(guardado, conteudo_falso("Derivadas"))
        self.assertEqual(len(guardado["perguntas"]), 10)

    def test_variacoes_do_mesmo_tema_usam_o_cache(self):
        self.pedir("Cálculo I")
        for variacao in ("calculo i", "  CÁLCULO   I  ", "CALCULO I"):
            _, do_cache = self.pedir(variacao)
            self.assertTrue(do_cache, variacao)
        self.assertEqual(self.ia.total_chamadas, 1)

    def test_devolve_o_tema_do_jeito_que_foi_gerado(self):
        self.pedir("Cálculo I")
        conteudo, _ = self.pedir("calculo i")
        self.assertEqual(conteudo["tema"], "Cálculo I")

    def test_tema_diferente_gera_de_novo(self):
        self.pedir("Limites")
        _, do_cache = self.pedir("Integrais")
        self.assertFalse(do_cache)
        self.assertEqual(self.ia.total_chamadas, 2)
        self.assertEqual(ConteudoGerado.objects.count(), 2)

    def test_gerador_recebe_o_tema_sem_espacos_nas_pontas(self):
        self.pedir("  Limites  ")
        self.assertEqual(self.ia.chamadas, ["Limites"])

    def test_falha_da_ia_nao_deixa_nada_no_cache(self):
        self.ia = IAFalsa(falhas=[TimeoutError("lenta demais")])
        with self.assertRaises(TimeoutError):
            self.pedir("Limites")
        self.assertEqual(ConteudoGerado.objects.count(), 0)
        _, do_cache = self.pedir("Limites")
        self.assertFalse(do_cache)
        self.assertEqual(ConteudoGerado.objects.count(), 1)

    def test_conteudo_incompleto_nao_e_guardado(self):
        self.ia = IAFalsa(conteudo={"tema": "X", "resumo": "sem perguntas"})
        with self.assertRaises(ValueError):
            self.pedir("X")
        self.assertEqual(ConteudoGerado.objects.count(), 0)

    def test_tema_invalido_nem_chega_na_ia(self):
        with self.assertRaises(ValueError):
            self.pedir("   ")
        self.assertEqual(self.ia.total_chamadas, 0)

    def test_antes_de_gerar_so_roda_quando_vai_chamar_a_ia(self):
        cobrancas = []
        for _ in range(3):
            self.pedir("Limites", antes_de_gerar=lambda: cobrancas.append(1))
        self.assertEqual(len(cobrancas), 1)

    def test_se_outra_requisicao_guardou_primeiro_vale_a_que_ja_estava(self):
        def gerador_com_corrida(tema):
            ConteudoGerado.objects.create(tema_chave="limites", tema="Limites", resumo="da outra requisição", perguntas=[])
            return conteudo_falso(tema)

        conteudo, do_cache = obter_ou_gerar("Limites", gerador_com_corrida)
        self.assertEqual(conteudo["resumo"], "da outra requisição")
        self.assertFalse(do_cache)
        self.assertEqual(ConteudoGerado.objects.count(), 1)

    def test_invalidar_tema_forca_nova_geracao(self):
        self.pedir("Limites")
        self.assertTrue(invalidar_tema("LIMITES"))
        self.assertFalse(invalidar_tema("Limites"))
        _, do_cache = self.pedir("Limites")
        self.assertFalse(do_cache)
        self.assertEqual(self.ia.total_chamadas, 2)


@override_settings(CACHES=CACHE_REAL)
class CacheComCotaDeIATests(TestCase):
    """Temas que já estão no cache não gastam a cota de IA do usuário."""

    def setUp(self):
        cache.clear()
        self.requisicao = SimpleNamespace(user=Usuario.objects.create(nome="Ana"), META={})
        self.ia = IAFalsa()

    def pedir(self, tema):
        return obter_ou_gerar(
            tema, self.ia.gerar_conteudo, antes_de_gerar=lambda: verificar_limite_ia(self.requisicao)
        )

    def test_so_a_geracao_de_verdade_gasta_cota(self):
        with patch.dict(SimpleRateThrottle.THROTTLE_RATES, {"ia_hora": "2/hour", "ia_dia": "100/day"}):
            for _ in range(5):
                self.pedir("Derivadas")
            self.pedir("Integrais")
            with self.assertRaises(Throttled):
                self.pedir("Limites")
            self.pedir("Derivadas")  # continua saindo do cache mesmo sem cota
        self.assertEqual(self.ia.total_chamadas, 2)
        self.assertEqual(ConteudoGerado.objects.count(), 2)