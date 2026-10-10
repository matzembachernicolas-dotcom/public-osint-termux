import json
import re
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from html import unescape
from email.utils import parsedate_to_datetime

AGENTE = "PublicOSINT-Termux/2.0"
TIMEOUT = 15
TOTAL_RESULTADOS = 0
FONTES_OK = 0
FONTES_FALHA = 0


def requisicao(url, accept="application/json"):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": AGENTE,
            "Accept": accept
        }
    )

    with urllib.request.urlopen(req, timeout=TIMEOUT) as resposta:
        return resposta.read().decode("utf-8", errors="replace")


def json_get(url):
    return json.loads(requisicao(url))


def limpar(texto):
    texto = unescape(str(texto or ""))
    texto = re.sub(r"<[^>]*>", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def separador():
    print("\n" + "=" * 68)


def mostrar_fonte(nome, resultados, formatador, limite=5):
    global TOTAL_RESULTADOS, FONTES_OK

    print(f"\n[FONTE: {nome}]")

    if resultados is None:
        print("A fonte não retornou dados.")
        return 0

    FONTES_OK += 1
    quantidade = 0

    for item in resultados[:limite]:
        try:
            texto = formatador(item)

            if texto:
                quantidade += 1
                TOTAL_RESULTADOS += 1
                print(f"\n{quantidade}. {texto}")

        except Exception:
            continue

    if quantidade == 0:
        print("Nenhum resultado útil encontrado.")

    return quantidade


def consultar(nome, funcao):
    global FONTES_FALHA

    try:
        return funcao()

    except urllib.error.HTTPError as erro:
        FONTES_FALHA += 1
        print(f"\n[FONTE: {nome}] Erro HTTP {erro.code}.")

    except Exception as erro:
        FONTES_FALHA += 1
        print(
            f"\n[FONTE: {nome}] Falha na consulta: "
            f"{type(erro).__name__}"
        )

    return 0


# --------------------------------------------------
# NOTÍCIAS
# --------------------------------------------------

def google_news(pesquisa):
    parametros = urllib.parse.urlencode({
        "q": pesquisa,
        "hl": "pt-BR",
        "gl": "BR",
        "ceid": "BR:pt-419"
    })

    url = (
        "https://news.google.com/rss/search?"
        + parametros
    )

    xml = requisicao(
        url,
        "application/rss+xml, application/xml, text/xml"
    )

    raiz = ET.fromstring(xml)
    resultados = raiz.findall(".//item")

    def formatar(item):
        titulo = limpar(item.findtext("title"))
        descricao = limpar(item.findtext("description"))
        link = limpar(item.findtext("link"))
        data = limpar(item.findtext("pubDate"))

        partes = [titulo]

        if data:
            partes.append("Data: " + data)

        if descricao:
            partes.append("Trecho: " + descricao[:500])

        if link:
            partes.append("Fonte: " + link)

        return "\n   ".join(partes)

    return mostrar_fonte(
        "Google Notícias — matérias publicadas",
        resultados,
        formatar,
        10
    )


def gdelt(pesquisa):
    parametros = urllib.parse.urlencode({
        "query": pesquisa,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": 10,
        "sort": "HybridRel"
    })

    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc?"
        + parametros
    )

    dados = json_get(url)
    resultados = dados.get("articles", [])

    def formatar(item):
        partes = [
            limpar(item.get("title")),
            "Site: " + limpar(item.get("domain")),
            "Data: " + limpar(item.get("seendate"))
        ]

        if item.get("snippet"):
            partes.append(
                "Trecho: " + limpar(item["snippet"])[:400]
            )

        if item.get("url"):
            partes.append("Fonte: " + item["url"])

        return "\n   ".join(partes)

    return mostrar_fonte(
        "GDELT — notícias internacionais",
        resultados,
        formatar,
        10
    )


# --------------------------------------------------
# WIKIPEDIA
# --------------------------------------------------

def wikipedia(pesquisa, idioma):
    parametros = urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": pesquisa,
        "format": "json",
        "srlimit": 5
    })

    url = (
        f"https://{idioma}.wikipedia.org/w/api.php?"
        + parametros
    )

    dados = json_get(url)
    resultados = dados.get("query", {}).get("search", [])

    def formatar(item):
        nome = limpar(item.get("title"))
        resumo = limpar(item.get("snippet"))

        pagina = (
            f"https://{idioma}.wikipedia.org/wiki/"
            + urllib.parse.quote(nome.replace(" ", "_"))
        )

        return (
            f"{nome}\n"
            f"   Resumo: {resumo}\n"
            f"   Fonte: {pagina}"
        )

    return mostrar_fonte(
        f"Wikipedia {idioma.upper()}",
        resultados,
        formatar
    )


# --------------------------------------------------
# WIKIDATA
# --------------------------------------------------

def wikidata(pesquisa):
    parametros = urllib.parse.urlencode({
        "action": "wbsearchentities",
        "search": pesquisa,
        "language": "pt",
        "format": "json",
        "limit": 5
    })

    url = "https://www.wikidata.org/w/api.php?" + parametros
    dados = json_get(url)
    resultados = dados.get("search", [])

    def formatar(item):
        identificador = item.get("id", "")

        return (
            f"{limpar(item.get('label'))}\n"
            f"   Descrição: {limpar(item.get('description'))}\n"
            f"   Identificador: {identificador}\n"
            f"   Fonte: https://www.wikidata.org/wiki/{identificador}"
        )

    return mostrar_fonte("Wikidata", resultados, formatar)


# --------------------------------------------------
# PUBLICAÇÕES ACADÊMICAS
# --------------------------------------------------

def openalex(pesquisa):
    parametros = urllib.parse.urlencode({
        "search": pesquisa,
        "per-page": 5
    })

    dados = json_get(
        "https://api.openalex.org/works?" + parametros
    )

    resultados = dados.get("results", [])

    def formatar(item):
        autores = []

        for autoria in item.get("authorships", [])[:3]:
            autor = autoria.get("author", {})
            nome = autor.get("display_name")

            if nome:
                autores.append(limpar(nome))

        return (
            f"{limpar(item.get('display_name'))}\n"
            f"   Ano: {item.get('publication_year')}\n"
            f"   Autores: {', '.join(autores) or 'Não informados'}\n"
            f"   Registro: {item.get('id', '')}"
        )

    return mostrar_fonte(
        "OpenAlex — trabalhos acadêmicos",
        resultados,
        formatar
    )


def crossref(pesquisa):
    parametros = urllib.parse.urlencode({
        "query.bibliographic": pesquisa,
        "rows": 5
    })

    dados = json_get(
        "https://api.crossref.org/works?" + parametros
    )

    resultados = dados.get("message", {}).get("items", [])

    def formatar(item):
        titulos = item.get("title") or ["Sem título"]
        autores = []

        for autor in item.get("author", [])[:3]:
            nome = (
                autor.get("given", "")
                + " "
                + autor.get("family", "")
            ).strip()

            if nome:
                autores.append(limpar(nome))

        data = item.get("published-print") or item.get("published-online") or {}
        partes_data = data.get("date-parts", [[]])
        ano = partes_data[0][0] if partes_data and partes_data[0] else "Não informado"

        doi = item.get("DOI", "")
        link = f"https://doi.org/{doi}" if doi else item.get("URL", "")

        return (
            f"{limpar(titulos[0])}\n"
            f"   Ano: {ano}\n"
            f"   Autores: {', '.join(autores) or 'Não informados'}\n"
            f"   Fonte: {link}"
        )

    return mostrar_fonte(
        "Crossref — registros acadêmicos",
        resultados,
        formatar
    )


# --------------------------------------------------
# PERFIS PÚBLICOS DO GITHUB
# --------------------------------------------------

def github(pesquisa):
    parametros = urllib.parse.urlencode({
        "q": pesquisa,
        "per_page": 5
    })

    dados = json_get(
        "https://api.github.com/search/users?" + parametros
    )

    resultados = dados.get("items", [])

    def formatar(item):
        return (
            f"Perfil: {limpar(item.get('login'))}\n"
            f"   Endereço público: {item.get('html_url', '')}"
        )

    return mostrar_fonte(
        "GitHub — perfis públicos",
        resultados,
        formatar
    )


# --------------------------------------------------
# PESQUISA PRINCIPAL
# --------------------------------------------------

def pesquisar_nome(nome):
    global TOTAL_RESULTADOS, FONTES_OK, FONTES_FALHA

    TOTAL_RESULTADOS = 0
    FONTES_OK = 0
    FONTES_FALHA = 0

    separador()
    print("PESQUISA DE INFORMAÇÕES PROFISSIONAIS PÚBLICAS")
    print("Consulta:", nome)
    separador()

    fontes = [
        ("Google Notícias", lambda: google_news(nome)),
        ("GDELT", lambda: gdelt(nome)),
        ("Wikipedia PT", lambda: wikipedia(nome, "pt")),
        ("Wikipedia EN", lambda: wikipedia(nome, "en")),
        ("Wikidata", lambda: wikidata(nome)),
        ("OpenAlex", lambda: openalex(nome)),
        ("Crossref", lambda: crossref(nome)),
        ("GitHub", lambda: github(nome))
    ]

    for nome_fonte, funcao in fontes:
        consultar(nome_fonte, funcao)
        time.sleep(0.3)

    separador()
    print("PESQUISA CONCLUÍDA")
    print("Fontes que responderam:", FONTES_OK)
    print("Fontes com falha:", FONTES_FALHA)
    print("Resultados exibidos:", TOTAL_RESULTADOS)
    print(
        "Importante: confirme a identidade e a relevância "
        "de cada resultado. Um nome igual não prova que seja "
        "a mesma pessoa."
    )


def pesquisar_identificador(tipo, valor):
    global TOTAL_RESULTADOS, FONTES_OK, FONTES_FALHA

    TOTAL_RESULTADOS = 0
    FONTES_OK = 0
    FONTES_FALHA = 0

    if tipo == "email":
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", valor):
            print("Formato de e-mail inválido.")
            return

        pesquisa = '"' + valor + '"'
        titulo_pesquisa = "OCORRÊNCIAS PÚBLICAS DE E-MAIL"

    else:
        numero = re.sub(r"\D", "", valor)

        if len(numero) < 8 or len(numero) > 15:
            print("Número incompleto ou inválido.")
            return

        pesquisa = '"' + numero + '"'
        titulo_pesquisa = "OCORRÊNCIAS PÚBLICAS DE TELEFONE"

    separador()
    print(titulo_pesquisa)
    separador()

    consultar("Google Notícias", lambda: google_news(pesquisa))
    consultar("GDELT", lambda: gdelt(pesquisa))

    print("\nFontes que responderam:", FONTES_OK)
    print("Fontes com falha:", FONTES_FALHA)
    print("Resultados exibidos:", TOTAL_RESULTADOS)
    print("A busca não consulta contas privadas ou bases vazadas.")


def menu():
    while True:
        separador()
        print("PUBLIC OSINT — PESQUISA EM FONTES ABERTAS")
        separador()
        print("1 - Pesquisar por nome")
        print("2 - Pesquisar por e-mail")
        print("3 - Pesquisar por telefone")
        print("0 - Sair")

        opcao = input("\nEscolha: ").strip()

        if opcao == "1":
            nome = input("Nome para pesquisar: ").strip()

            if nome:
                pesquisar_nome(nome)

        elif opcao == "2":
            email = input("E-mail para pesquisar: ").strip()

            if email:
                pesquisar_identificador("email", email)

        elif opcao == "3":
            telefone = input("Telefone para pesquisar: ").strip()

            if telefone:
                pesquisar_identificador("telefone", telefone)

        elif opcao == "0":
            print("Programa encerrado.")
            break

        else:
            print("Opção inválida.")

        input("\nPressione Enter para voltar ao menu...")


if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        print("\nPrograma encerrado.")

