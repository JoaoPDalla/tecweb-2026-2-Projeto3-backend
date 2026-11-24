# Perguntas salvas e respostas do quiz

Esta integração completa o vínculo entre a geração de material, o salvamento de
conteúdos e os endpoints de respostas/histórico existentes. Preserva o formato
das telas, o cache, as cotas, as permissões e as operações de livros/conteúdos.
O cliente Gemini do PR #25 foi preservado; a persistência atua sobre o material
já validado, independentemente do provedor. Configuração em [geração de material](ia.md).

## Atualização do banco

Execute `python manage.py migrate` antes de iniciar o backend atualizado. A
migração `0005_persistencia_quiz` adiciona dois campos opcionais e uma restrição
de unicidade. Não remove dados nem altera perguntas ou respostas anteriores.

## Identidade das perguntas

`POST /api/conteudos/gerar/` mantém `{tema, resumo, perguntas}`. Os IDs das perguntas
agora são strings com as chaves reais do banco, como `"12"`. O JSON compartilhado
do cache não é modificado. Um hash dos dados da pergunta permite reutilizar a
mesma identidade em gerações e leituras do cache equivalentes. Essas perguntas
não pertencem a um conteúdo salvo, permitindo fazer o quiz sem apertar Salvar.

## Salvar e reabrir

`POST /api/conteudos/` aceita `perguntas` opcional, junto de `livro`, `tema` e
`resumo`. Envie a lista completa do contrato da geração: dez perguntas distintas,
cada uma com `id`, `topic`, `prompt`, `answers` e `correctAnswerId`, mantendo o
tema e as quatro alternativas com suas explicações. O validador da IA existente
também valida essa lista. Material inválido responde 400 sem criar conteúdo.

O conteúdo e suas perguntas são criados em uma transação. São cópias próprias,
com novos IDs e vínculo ao conteúdo; os IDs recebidos não movem nem alteram
perguntas de outras gerações ou conteúdos. A resposta 201 e o
`GET /api/conteudos/<id>/` devolvem essas cópias na ordem recebida e com IDs reais.
O frontend passa a usá-las ao entrar no quiz depois de salvar.

O payload antigo sem `perguntas` continua válido, assim como `perguntas: []` na
criação. Renomear ou mover um conteúdo continua preservando suas perguntas.
Enviar `perguntas` ao editar um conteúdo responde 400; para trocar o conjunto,
crie outro conteúdo. Isso evita substituir perguntas com histórico existente.

## Registrar uma resposta

Use `POST /api/perguntas/<id>/responder/`, autenticado, por exemplo:

```json
{
  "alternativa": "a",
  "chave_envio": "929a46ed-c9cd-4d24-8e13-a27157aee442"
}
```

O frontend cria um UUID por pergunta e tentativa, reutilizando-o em um reenvio.
O servidor calcula `acertou`; o cliente não envia pontuação nem gabarito.

| Situação | Resposta |
| --- | --- |
| Primeira confirmação | 201, registro criado |
| Mesmo usuário, chave, pergunta e alternativa | 200, mesmo registro |
| Mesma chave com pergunta ou alternativa diferente | 409, código `envio_ja_registrado`, nenhum registro adicional |
| `chave_envio` malformada | 400 |
| Cliente antigo sem `chave_envio` | 201 em cada envio, comportamento anterior |

A unicidade de usuário e chave também é garantida no banco. Usuários diferentes
podem usar o mesmo UUID. Refazer o quiz usa novas chaves e cria novos registros;
não apaga respostas de tentativas anteriores. O corpo da confirmação permanece
`{id, pergunta, tema, enunciado, alternativa, resposta_correta, acertou, criado_em}`.

## Histórico e limites preservados

`GET /api/respostas/` continua paginado e restrito ao usuário autenticado, com
filtros `?pergunta=<id>` e `?conteudo=<id>`. Depois de salvar, respostas às cópias
do conteúdo aparecem no filtro correspondente. Respostas feitas antes de salvar
continuam no histórico geral, vinculadas às perguntas da geração; o salvamento
posterior não reescreve o histórico.

O progresso da tentativa fica em memória no frontend. Recarregar começa outra
tentativa, mantendo as respostas já confirmadas. Conteúdos antigos sem perguntas
continuam abrindo o resumo, e o frontend oferece gerar novo material.

As regras anteriores de exclusão e acesso continuam valendo: excluir um conteúdo
ou livro remove em cascata suas perguntas e respostas vinculadas; qualquer usuário
autenticado pode responder a uma pergunta, mas só consulta seu próprio histórico.

## Verificação

```text
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
```

Os testes cobrem IDs estáveis, compatibilidade dos payloads antigos, validação,
transação, isolamento do histórico e reenvio com a mesma chave. O fluxo também foi
verificado pelo navegador usando Django e banco temporário, simulando somente o
provedor de IA e uma falha de confirmação após a gravação: dez respostas e mais
uma de nova tentativa resultaram em onze registros, sem duplicação no reenvio.

Após incorporar o Gemini, um teste de integração usa os tipos reais do SDK e
simula somente sua chamada de geração. O teste percorre a geração e o cache,
salva e reabre o material, confirma uma resposta e confere seu histórico sem
duplicar o reenvio. Não consulta o provedor nem modifica o banco de desenvolvimento.
