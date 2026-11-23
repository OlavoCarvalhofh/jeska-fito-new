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
CODIGO_RE = re.compile(r"`([^`]+)`")
TAG = {1: "i", 2: "b"}


def enfatizar(texto: str) -> str:
    """Converte *itálico*, **negrito** e ***ambos*** em HTML sempre bem
    aninhado. Asteriscos que não fecham voltam a ser texto."""
    saida: list[str] = []
    pilha: list[tuple[int, int]] = []  # (tamanho do marcador, posição em saida)
    i, n = 0, len(texto)
    while i < n:
        if texto[i] != "*":
            j = i
            while j < n and texto[j] != "*":
                j += 1
            saida.append(texto[i:j])
            i = j
            continue
        j = i
        while j < n and texto[j] == "*":
            j += 1
        resto = j - i
        antes = texto[i - 1] if i > 0 else " "
        depois = texto[j] if j < n else " "
        # fechar marcadores abertos, sempre do topo da pilha
        while resto and pilha and not antes.isspace() and pilha[-1][0] <= resto:
            tam, _ = pilha.pop()
            saida.append(f"</{TAG[tam]}>")
            resto -= tam
        # abrir novos marcadores
        if resto and not depois.isspace():
            if resto >= 2:
                pilha.append((2, len(saida)))
                saida.append("<b>")
                resto -= 2
            if resto >= 1:
                pilha.append((1, len(saida)))
                saida.append("<i>")
                resto -= 1
        if resto:
            saida.append("*" * resto)
        i = j
    for tam, pos in pilha:  # não fechados: viram asteriscos de novo
        saida[pos] = "*" * tam
    return "".join(saida)


def formatar_inline(texto: str) -> str:
    """Converte Markdown simples de uma linha em HTML aceito pelo Telegram."""
    guardados = []

    def guardar(html_pronto: str) -> str:
        guardados.append(html_pronto)
        return f"\x00{len(guardados) - 1}\x00"

    def guardar_link(m):
        rotulo = m.group(1).replace("*", "")
        return guardar(f'<a href="{html.escape(m.group(2))}">{html.escape(rotulo, quote=False)}</a>')

    texto = LINK_RE.sub(guardar_link, texto)
    texto = CODIGO_RE.sub(lambda m: guardar(f"<code>{html.escape(m.group(1), quote=False)}</code>"), texto)
    texto = enfatizar(html.escape(texto, quote=False))
    return re.sub(r"\x00(\d+)\x00", lambda m: guardados[int(m.group(1))], texto)


def sem_formatacao(texto_html: str) -> str:
    """Versão em texto puro, usada se o Telegram recusar o HTML."""
    texto = re.sub(r'<a href="([^"]+)">([^<]*)</a>', r"\2 (\1)", texto_html)
    texto = re.sub(r"</?(b|i|code)>", "", texto)
    return html.unescape(texto)


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
    """Envia em HTML; se o Telegram recusar a formatação, reenvia em texto puro."""
    try:
        _enviar(token, chat_id, texto, html_mode=True)
    except RuntimeError as erro:
        if "can't parse entities" not in str(erro):
            raise
        print(f"Formatação recusada ({erro}); reenviando em texto puro.")
        _enviar(token, chat_id, sem_formatacao(texto), html_mode=False)


def _enviar(token: str, chat_id: str, texto: str, html_mode: bool) -> None:
    campos = {
        "chat_id": chat_id,
        "text": texto,
        "disable_web_page_preview": "true",
    }
    if html_mode:
        campos["parse_mode"] = "HTML"
    dados = urllib.parse.urlencode(campos).encode()
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
