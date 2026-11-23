# Modelos e prompt de estudo — Ma7zz (#5 e #10)

## Escopo

- #5: `Pergunta`, `Resposta`, validação dos campos e migração.
- #10: mensagens de geração de resumo e dez perguntas, acompanhadas do JSON Schema.

A #5 não tem descrição no GitHub. Aqui, **Resposta representa a escolha do estudante**,
coerente com a #20 (responder e histórico). As quatro alternativas fazem parte da
Pergunta, com a explicação de cada opção.

## Modelos

`Pergunta` armazena `tema` (até 255 caracteres), `enunciado`, `alternativas`,
`resposta_correta` e `criado_em`. `alternativas` é uma lista JSON com exatamente
quatro objetos `{id, text, explanation}`, com IDs únicos `a`, `b`, `c`, `d`.
Todos os textos são obrigatórios. `resposta_correta` aponta para uma dessas letras,
representando um único gabarito.

`Resposta` relaciona `usuario` e `pergunta`, registra `alternativa`, `acertou` e
`criado_em`. `acertou` é calculado ao salvar, sem confiar em um valor fornecido pelo
chamador. O resultado fica registrado no banco, mesmo se o gabarito mudar depois.
Salvar novamente uma resposta recalcula seu resultado. O mesmo usuário pode
responder à mesma pergunta várias vezes, mantendo registros distintos no histórico.
Excluir usuário ou pergunta também remove suas respostas.

Use `objects.create()` ou `save()` para executar a validação dos modelos.
Como no Django em geral, `bulk_create()` e `QuerySet.update()` não chamam `save()`;
as restrições do banco cobrem as letras permitidas, mas não a estrutura do JSON.

## Contrato com o frontend

O objeto de conteúdo gerado tem `tema`, `resumo` e `perguntas`. Os dois primeiros
campos seguem o formato já usado por `services/conteudos.js` e pela tela de resumo:
`resumo` é uma string Markdown com LaTeX, quando aplicável.

Cada item de `perguntas` segue diretamente o controlador de quiz existente em
`src/quiz/quiz.js`:

```json
{
  "id": "pergunta-1",
  "topic": "Derivadas",
  "prompt": "Qual é a derivada de $x^2$?",
  "answers": [
    {"id": "a", "text": "$2x$", "explanation": "A regra da potência dá $2x$."},
    {"id": "b", "text": "$x$", "explanation": "Faltou multiplicar pelo expoente 2."},
    {"id": "c", "text": "$2$", "explanation": "A derivada ainda depende de x."},
    {"id": "d", "text": "$x^3$", "explanation": "Na derivação, o expoente diminui."}
  ],
  "correctAnswerId": "a"
}
```

`Pergunta.para_quiz()` exporta uma pergunta persistida nesse mesmo formato,
usando o ID do banco convertido para string. O objeto inclui gabarito e explicações
porque o controlador atual faz a correção localmente. Ele já adapta as explicações
ao formato `escolhida`/`correta` da tela de resolução e remove o gabarito da projeção
usada para exibir a pergunta.

Na futura persistência, o mapeamento é:

| JSON da IA | Campo do modelo Pergunta |
| --- | --- |
| `topic` | `tema` |
| `prompt` | `enunciado` |
| `answers` | `alternativas` |
| `correctAnswerId` | `resposta_correta` |

O ID `pergunta-1` é local ao material gerado; a exportação após persistência usa
o ID real do banco. As perguntas devem ser apresentadas na ordem retornada pela IA.

## Uso do prompt

```python
from sampletext.prompts.resumo import montar_mensagens_resumo, obter_schema_conteudo

mensagens = montar_mensagens_resumo("Regra da cadeia")
schema = obter_schema_conteudo()
```

As mensagens seguem o formato `role`/`content`, independente de provedor. O schema
também está incorporado à instrução de sistema. O tema é enviado separadamente
como dado JSON. A instrução exige dez perguntas distintas, quatro alternativas,
um único gabarito e explicações específicas tanto das erradas quanto da correta.
Não há chamada externa nem necessidade de chave de IA para executar estes módulos.

O schema define tipos, campos e quantidades. As regras semânticas (IDs distintos
entre perguntas, quatro IDs diferentes nas alternativas, `topic == tema` e qualidade
das explicações) também são descritas no prompt. Um prompt não garante que o provedor
obedeça: a validação da resposta completa continua sendo a #13.

## Integrações que continuam nas tarefas separadas

- #9 (João): Conteúdo e endpoints. Esse modelo ainda não existe na `main` consultada;
  por isso não foi criada uma relação para uma tabela inexistente. O vínculo de
  Conteúdo com as perguntas precisará ser acrescentado quando a #9 entrar na base.
- #20 (João): endpoints para responder e consultar histórico. Nenhuma rota foi criada.
- #13: validação do JSON completo retornado pela IA.
- #14: validação semântica do tema.
- #15: cliente/provedor da IA.
- #17/#18 e integração do frontend: conectar a geração, persistência e telas.

Autenticação, permissões, views, rotas e frontend existentes foram preservados.

## Verificação

Com o ambiente Python e as dependências do projeto instalados, a partir do backend:

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Os testes novos cobrem persistência, validação de alternativas/gabarito, histórico,
resultado calculado, formato do frontend e contrato do prompt. Os testes de
autenticação existentes continuam na suíte. A migração é criada sem aplicar
alterações ao banco de desenvolvimento; o comando `test` usa seu próprio banco.
