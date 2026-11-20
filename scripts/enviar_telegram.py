"""Envia um resumo em Markdown para um chat do Telegram.

Uso: python scripts/enviar_telegram.py caminho/do/resumo.md

Variáveis de ambiente:
  TELEGRAM_BOT_TOKEN  token do bot (secret do repositório)
  TELEGRAM_CHAT_ID    um ou mais chat IDs separados por vírgula
"""

import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

LIMITE = 3900  # Telegram aceita até 4096 caracteres por mensagem

LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
NEGRITO_RE = re.compile(r"\*\*(.+?)\*\*")
ITALICO_RE = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
CODIGO_RE = re.compile(r"`([^`]+)`")


def formatar_inline(texto: str) -> str:
    """Converte Markdown simples de uma linha em HTML aceito pelo Telegram."""
    links = []

    def guardar_link(m):
        links.append((m.group(1), m.group(2)))
        return f"\x00{len(links) - 1}\x00"

    texto = LINK_RE.sub(guardar_link, texto)
    texto = html.escape(texto, quote=False)
    texto = CODIGO_RE.sub(r"<code>\1</code>", texto)
    texto = NEGRITO_RE.sub(r"<b>\1</b>", texto)
    texto = ITALICO_RE.sub(r"<i>\1</i>", texto)

    def restaurar_link(m):
        rotulo, url = links[int(m.group(1))]
        rotulo = NEGRITO_RE.sub(r"\1", rotulo)
        return f'<a href="{html.escape(url)}">{html.escape(rotulo, quote=False)}</a>'

    return re.sub(r"\x00(\d+)\x00", restaurar_link, texto)


def markdown_para_html(md: str) -> list[str]:
    """Converte o resumo em linhas HTML do Telegram."""
    linhas = []
    for bruta in md.splitlines():
        linha = bruta.rstrip()
        if re.fullmatch(r"\s*(-{3,}|\*{3,}|_{3,})\s*", linha):
            linhas.append("")
            continue
        cab = re.match(r"^(#{1,6})\s+(.*)$", linha)
        if cab:
            titulo = formatar_inline(cab.group(2))
            if linhas and linhas[-1] != "":
                linhas.append("")
            linhas.append(f"<b>{titulo}</b>")
            continue
        item = re.match(r"^(\s*)[-*+]\s+(.*)$", linha)
        if item:
            recuo = "   " if item.group(1) else ""
            linhas.append(f"{recuo}• {formatar_inline(item.group(2))}")
            continue
        linhas.append(formatar_inline(linha))

    # remove linhas vazias repetidas
    limpas = []
    for linha in linhas:
        if linha == "" and limpas and limpas[-1] == "":
            continue
        limpas.append(linha)
    return limpas


def dividir(linhas: list[str]) -> list[str]:
    """Junta as linhas em mensagens de até LIMITE caracteres, quebrando em
    títulos ou parágrafos sempre que possível."""
    mensagens, atual = [], ""
    for linha in linhas:
        candidato = f"{atual}\n{linha}" if atual else linha
        if len(candidato) > LIMITE and atual:
            mensagens.append(atual.strip())
            atual = linha
        else:
            atual = candidato
    if atual.strip():
        mensagens.append(atual.strip())
    return mensagens


def enviar(token: str, chat_id: str, texto: str) -> None:
    dados = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(url, data=dados, timeout=30) as r:
                resposta = json.load(r)
            if resposta.get("ok"):
                return
            raise RuntimeError(resposta)
        except urllib.error.HTTPError as e:
            corpo = e.read().decode(errors="replace")
            if e.code == 429 and tentativa < 2:
                time.sleep(5)
                continue
            raise RuntimeError(f"Telegram respondeu {e.code}: {corpo}") from None


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python scripts/enviar_telegram.py arquivo.md")
        return 2
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chats = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]
    if not token or not chats:
        print("Faltam TELEGRAM_BOT_TOKEN e/ou TELEGRAM_CHAT_ID.")
        return 1

    with open(sys.argv[1], encoding="utf-8") as f:
        mensagens = dividir(markdown_para_html(f.read()))

    total = len(mensagens)
    for chat in chats:
        for i, msg in enumerate(mensagens, 1):
            if total > 1:
                msg = f"{msg}\n\n<i>({i}/{total})</i>"
            enviar(token, chat, msg)
            time.sleep(1)
    print(f"Enviado: {total} mensagem(ns) para {len(chats)} chat(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
