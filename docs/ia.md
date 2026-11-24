# Geração de material — #12, #13, #14 e #15

O fluxo usa o prompt de resumo já existente da #10, valida o tema antes da geração
e verifica a resposta da IA antes de entregá-la ao frontend. As views de
autenticação e os modelos existentes não foram modificados.

## Configuração

Instale as dependências de `requirements.txt`, copie `.env.example` para `.env`
e configure `AI_API_KEY` com uma chave da **OpenAI API**. O cliente usa a Responses
API com saída JSON estruturada. O modelo padrão é `gpt-4.1-mini`; `AI_MODEL`
permite escolher outro modelo compatível com Structured Outputs.

`AI_TIMEOUT_SECONDS` limita cada chamada (padrão 45 segundos).
`AI_MAX_OUTPUT_TOKENS` limita a geração (padrão 8000). Uma geração válida realiza
duas chamadas: classificação do tema e produção do material. Não há repetição
automática de chamadas. A chave nunca é enviada ao frontend, devolvida nos erros
ou escrita em logs pelo cliente. Sem chave, os endpoints devolvem 503 e não
tentam acessar o provedor. `.env` está ignorado pelo Git.

Referências oficiais usadas na integração:
- [Quickstart](https://developers.openai.com/api/docs/quickstart)
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini)

## Endpoints (#12)

Ambos exigem `Authorization: Token <token-do-login>` e JSON de entrada:

```json
{"tema": "Regra da cadeia"}
```

`tema` deve ser texto não vazio com até 255 caracteres. Espaços repetidos são
normalizados. Números, listas e outros tipos são recusados antes de chamar a IA.

### POST /api/conteudos/validar-tema/

Responde 200 com `{status, tema, motivo}`. `status` é `ok`, `amplo` ou `invalido`,
compatível com o contrato já usado na tela de busca. `tema` reproduz a entrada
normalizada; `motivo` contém uma explicação curta em português. A classificação
é feita pela IA, não por uma lista fixa de disciplinas.

### POST /api/conteudos/gerar/

Classifica o tema; se ele não for `ok`, responde 422 sem gerar material. Para um
tema válido, responde 200 com `{tema, resumo, perguntas}`, no contrato da #10:
dez perguntas distintas com `id`, `topic`, `prompt`, quatro `answers`
(`id`, `text`, `explanation`) e um `correctAnswerId`.

`resumo` e os demais textos preservam Markdown/LaTeX. O endpoint reaproveita os
componentes já existentes de cache (#7) e limite de uso (#8): uma geração validada
é guardada em `ConteudoGerado`; temas em cache não chamam a IA nem gastam a cota
de geração. Validações avulsas de tema também respeitam a cota de IA. Falhas de
validação ou do provedor não entram no cache.

A geração grava as perguntas e devolve seus IDs reais como strings, inclusive
quando o material vem do cache. O cache e as cotas mantêm seu comportamento.
Ainda não cria Conteúdo vinculado a livro: isso ocorre no salvamento solicitado
pelo estudante. O quiz pode registrar respostas antes ou depois desse salvamento.
Consulte o contrato complementar em [persistência do quiz](persistencia-quiz.md).

## Validação e erros (#13)

O validador exige os campos e tipos do contrato, exatamente dez perguntas,
IDs/enunciados distintos, quatro alternativas com IDs únicos `a`–`d`, textos
distintos, explicações não vazias e gabarito existente. Também confere a igualdade
do tema em todas as questões. Recusa JSON com cercas de código, campos extras,
chaves duplicadas, valores não finitos e respostas acima de 2 MB. A validação
estrutural não comprova a correção pedagógica do texto produzido pelo modelo.

Erros usam `{code, detail}`; erros de entrada incluem `errors` por campo.

| HTTP | Códigos principais | Situação |
| --- | --- | --- |
| 400 | `entrada_invalida` | Tema ausente ou malformado |
| 401 | autenticação DRF (`detail`) | Token ausente ou inválido |
| 422 | `tema_amplo`, `tema_invalido`, `ia_recusou` | Reformular o tema |
| 429 | `detail` e `retry_after` do handler existente | Cota de requisições/IA do usuário excedida |
| 502 | `ia_json_invalido`, `ia_resposta_invalida`, `ia_resposta_incompleta`, `ia_indisponivel` | Resposta do provedor inadequada |
| 503 | `ia_nao_configurada`, `ia_configuracao`, `ia_limite`, `ia_conexao` | Configuração, cota ou conexão |
| 504 | `ia_timeout` | Tempo de resposta excedido |

## Verificação

```text
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
```

A suíte verifica o transporte HTTP, os contratos e os endpoints com a IA simulada,
sem consumir créditos. Nenhuma chave real é necessária nos testes. A integração
com o provedor ao vivo precisa ser conferida após configurar uma chave válida.
