# Cache, limite de requisições e IA falsa: #7, #8 e #11

## O que existe

- **#7 Cache de temas já gerados:** `sampletext/cache_conteudo.py` e o model `ConteudoGerado`.
  Um registro por tema, compartilhado entre todos os usuários. "Cálculo I", "calculo i" e
  "  CÁLCULO   I " são o mesmo tema (ignora maiúsculas, acentos e espaços extras).
- **#8 Limite de requisições:** `sampletext/throttling.py`. Limite por usuário nas rotas, limite de
  login por IP e uma cota de gerações com a IA por usuário. O erro 429 vem em português.
- **#11 IA simulada:** `sampletext/ia_falsa.py`. `IAFalsa` e `conteudo_falso()` seguem o contrato do
  `prompts/resumo.py` (10 perguntas, alternativas a–d, um gabarito) e cabem no model `Pergunta`.

## Como usar no endpoint de gerar conteúdo (#12)

```python
from sampletext.cache_conteudo import obter_ou_gerar
from sampletext.throttling import verificar_limite_ia

conteudo, do_cache = obter_ou_gerar(
    tema,
    gerador=gerar_conteudo_com_ia,  # #15 + #13: chama a IA e devolve o dict JÁ VALIDADO
    antes_de_gerar=lambda: verificar_limite_ia(request, self),
)
```

- Tema que já está no cache **não gasta cota** de IA: `antes_de_gerar` só roda quando vai chamar a IA.
- Se a cota acabou, `verificar_limite_ia` levanta `Throttled` e o handler responde 429 com
  `{"detail": "Muitas requisições. Tente de novo em ...", "retry_after": segundos}`.
- Se o `gerador` falhar, nada é guardado no cache.
- O cache guarda o que o `gerador` devolve: a validação do JSON (#13) precisa acontecer antes.
- `invalidar_tema(tema)` apaga um tema do cache para gerá-lo de novo.

## Limites (valores padrão; troque no `.env` se quiser)

| Escopo | Padrão | Variável | Vale para |
| --- | --- | --- | --- |
| `user` | 120/minute | `LIMITE_USUARIO` | qualquer rota, por usuário |
| `login` | 10/minute | `LIMITE_LOGIN` | `POST /api/auth/login/`, por IP |
| `ia_hora` | 20/hour | `LIMITE_IA_HORA` | gerações com a IA, por usuário |
| `ia_dia` | 60/day | `LIMITE_IA_DIA` | gerações com a IA, por usuário |

## Testando sem a IA de verdade

```python
from sampletext.ia_falsa import IAFalsa

ia = IAFalsa()                              # devolve um conteúdo válido
ia = IAFalsa(falhas=[TimeoutError()])       # a 1ª chamada falha, as seguintes funcionam
ia = IAFalsa(texto_bruto="{ isto quebrou")  # gerar() devolve um JSON inválido (para testar a #13)
ia.gerar_conteudo("Derivadas")              # dict; serve de `gerador` em obter_ou_gerar
ia.gerar(montar_mensagens_resumo("Derivadas"))  # texto JSON, como um provedor devolveria
ia.total_chamadas                           # quantas vezes a "IA" foi usada
```

## Atenção

- **Migração:** a `0003_conteudogerado` pode colidir com a migração da #9. Se o Django reclamar de
  "conflicting migrations", rode `python manage.py makemigrations --merge`.
- **Testes:** no `manage.py test` o cache fica desligado (`DummyCache`), para o limite não vazar de um
  teste para outro. Os testes de `test_limites.py` ligam um cache de verdade só para eles.
- **Cache do limite:** o padrão do Django guarda os contadores na memória de cada processo. Para vários
  servidores em produção, configure um cache compartilhado (Redis, por exemplo).
- **Ainda falta (#11):** os testes dos endpoints de validar tema e gerar conteúdo, que dependem das
  issues #12 a #15. Quando existirem, use `IAFalsa` no lugar do cliente de IA.
