# Livros, Conteúdos e Respostas — #2, #9 e #20

Todas as rotas exigem `Authorization: Token <chave>` (a chave vem do login) e só enxergam
os dados do usuário logado. Itens de outro usuário respondem 404, como se não existissem.

## Livro (#2) — `/api/livros/`

| Método e rota | O que faz |
| --- | --- |
| `GET /api/livros/` | lista os livros: `[{id, nome, criado_em}]` |
| `POST /api/livros/` | cria: `{"nome": "Cálculo I"}` |
| `GET /api/livros/<id>/` | abre, com os conteúdos: `{id, nome, criado_em, conteudos: [{id, tema, criado_em}]}` |
| `PATCH /api/livros/<id>/` | renomeia: `{"nome": "..."}` |
| `DELETE /api/livros/<id>/` | exclui o livro **e os conteúdos dele** |

O nome é limitado a 100 caracteres, tem os espaços normalizados e não pode se repetir para o
mesmo usuário, ignorando maiúsculas e minúsculas.

## Conteúdo (#9) — `/api/conteudos/`

| Método e rota | O que faz |
| --- | --- |
| `GET /api/conteudos/` | lista (sem o resumo): `[{id, livro, tema, criado_em}]`. Filtro: `?livro=<id>` |
| `POST /api/conteudos/` | salva: `{"livro": 1, "tema": "Regra da cadeia", "resumo": "Markdown + LaTeX"}` |
| `GET /api/conteudos/<id>/` | abre: `{id, livro, tema, resumo, criado_em, perguntas}` |
| `PATCH /api/conteudos/<id>/` | move para outro livro (`{"livro": 2}`); também aceita `tema` e `resumo` |
| `DELETE /api/conteudos/<id>/` | exclui o conteúdo **e as perguntas e respostas ligadas a ele** |

`livro` é obrigatório e precisa ser do próprio usuário (também ao mover). `perguntas` vem no
formato do quiz do frontend (`Pergunta.para_quiz()`), com gabarito e explicações; fica vazia
enquanto nenhuma pergunta for salva para o conteúdo.

`Pergunta` ganhou o campo opcional `conteudo` (migração `0003`), que é o vínculo que a #5
deixou para esta tarefa. Perguntas sem conteúdo continuam válidas.

## Responder e histórico (#20)

| Método e rota | O que faz |
| --- | --- |
| `POST /api/perguntas/<id>/responder/` | registra a escolha: `{"alternativa": "a"}` (a, b, c ou d) |
| `GET /api/respostas/` | histórico do usuário, da mais recente para a mais antiga |

`responder` devolve 201 com `{id, pergunta, tema, enunciado, alternativa, resposta_correta, acertou,
criado_em}`. O servidor calcula `acertou`; o cliente não envia esse valor. Responder de novo à
mesma pergunta cria outro registro, e todos aparecem no histórico.

O histórico é paginado (`?limit=` de 1 a 200, padrão 50, e `?offset=`) e responde
`{count, next, previous, results}`. Filtros opcionais: `?pergunta=<id>` e `?conteudo=<id>`.
Valores que não são números inteiros respondem 400.

## Decisões a confirmar com o grupo

- Qualquer usuário logado pode responder a qualquer pergunta. As perguntas não têm dono: o dono é
  o conteúdo, e ele pode nem ter sido salvo (o quiz funciona sem apertar "Salvar").
- Excluir livro ou conteúdo apaga em cascata, inclusive o histórico das perguntas ligadas.
- Quem escolhe o livro na hora de salvar? A API exige `livro`, mas o fluxo do frontend ainda não
  define essa escolha (hoje o livro só chega quando o usuário abre "Novo conteúdo" a partir de um).
- O frontend (`services/livros.js`) usa `GET /livros/` e `GET /livros/:id/`, que batem com estas
  rotas. O formato de `/livros/:id/` no frontend é `{id, nome, topicos: [{id, tema}]}`, e aqui a
  lista se chama `conteudos`. Um dos lados precisa ser ajustado.

## Verificação

```text
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test
```

A migração `0003` foi escrita à mão. Se o `makemigrations --check` acusar diferença, apague o
arquivo `0003_...` e rode `python manage.py makemigrations sampletext`.
