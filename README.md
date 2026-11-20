# Resumo de fitopatologia no Telegram

Resumo diário de notícias de fitopatologia enviado pelo bot [@jessica_fito_bot](https://t.me/jessica_fito_bot).

## Como funciona

1. Uma tarefa agendada do Claude pesquisa as notícias todo dia de manhã e grava o resumo em `resumos/AAAA-MM-DD.md`.
2. O push desse arquivo dispara o workflow **Enviar resumo no Telegram**, que converte o Markdown e manda para o(s) chat(s) configurado(s), dividindo em várias mensagens quando passa do limite do Telegram.

## Configuração (uma vez só)

| Onde | Nome | Valor |
|---|---|---|
| Settings → Secrets and variables → Actions → **Secrets** | `TELEGRAM_BOT_TOKEN` | token do BotFather |
| Settings → Secrets and variables → Actions → **Variables** | `TELEGRAM_CHAT_ID` | chat ID da Jéssica (vários separados por vírgula) |

Para descobrir o chat ID: a pessoa manda `/start` para o bot e você roda o workflow **Descobrir chat ID** (aba Actions → Run workflow). O ID aparece no log.

## Testar

Aba Actions → **Enviar resumo no Telegram** → Run workflow → arquivo `exemplos/2026-11-exemplo.md`.

## Estrutura

```
resumos/        resumos diários (cada push envia)
exemplos/       arquivos de teste (não disparam envio)
scripts/        enviar_telegram.py
.github/workflows/
```
