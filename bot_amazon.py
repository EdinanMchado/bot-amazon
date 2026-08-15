import os
import random
import re
import time
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from curl_cffi import requests

# ==============================================================================
# CONFIGURAÇÕES PRINCIPAIS
# ==============================================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TAG_AFILIADO = "SEU_TAG_AFILIADO_AQUI"
DESCONTO_MINIMO_PORCENTAGEM = 50.0

TERMOS_BUSCA = [
    "smartphone",
    "air fryer",
    "notebook",
    "smartwatch",
    "fone bluetooth",
    "playstation 5",
    "Eau de Parfum",
]

# Lista de versões de navegadores para alternar
NAVEGADORES = ["chrome110", "chrome119", "chrome120", "edge101"]

# ==============================================================================
# FUNÇÃO DE ENVIO PARA O TELEGRAM
# ==============================================================================


def enviar_alerta_telegram(mensagem, link_foto=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram não configurado em Secrets.")
        return

    if link_foto:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "photo": link_foto,
            "caption": mensagem,
            "parse_mode": "Markdown",
        }
    else:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "parse_mode": "Markdown",
        }

    try:
        response = requests.post(
            url, data=payload, impersonate=random.choice(NAVEGADORES)
        )
        if response.status_code != 200:
            print(f"❌ Erro ao enviar mensagem no Telegram: {response.text}")
        else:
            print("🚀 Alerta enviado com sucesso para o Telegram!")
    except Exception as e:
        print(f"❌ Falha na conexão com o Telegram: {e}")


# ==============================================================================
# FUNÇÕES DE BUSCA E SCRAPING DA AMAZON
# ==============================================================================


def extrair_preco(texto):
    if not texto:
        return None
    texto_limpo = re.sub(r"[^\d,]", "", texto)
    if texto_limpo:
        return float(texto_limpo.replace(",", "."))
    return None


def buscar_ofertas_amazon(termo):
    print(f"\n🔍 Pesquisando por: '{termo}' na Amazon...")
    url_busca = f"https://www.amazon.com.br/s?k={quote_plus(termo)}"

    try:
        # Escolhe aleatoriamente um perfil de navegador a cada requisição
        browser = random.choice(NAVEGADORES)
        response = requests.get(url_busca, impersonate=browser, timeout=15)

        if response.status_code != 200:
            print(
                f"⚠️ Não foi possível acessar a busca (Status:"
                f" {response.status_code})"
            )
            return

        soup = BeautifulSoup(response.content, "html.parser")
        produtos = soup.find_all(
            "div", {"data-component-type": "s-search-result"}
        )

        for item in produtos:
            tag_titulo = item.find("h2")
            if not tag_titulo:
                continue
            titulo = tag_titulo.get_text(strip=True)

            link_tag = item.find("a", class_="a-link-normal s-no-outline")
            if not link_tag or "href" not in link_tag.attrs:
                continue
            link_produto = "https://www.amazon.com.br" + link_tag["href"]
            if TAG_AFILIADO:
                link_produto += f"&tag={TAG_AFILIADO}"

            tag_imagem = item.find("img", class_="s-image")
            link_foto = tag_imagem["src"] if tag_imagem else None

            preco_atual_tag = item.find("span", class_="a-price-whole")
            preco_antigo_tag = item.find("span", class_="a-text-price")

            if preco_atual_tag and preco_antigo_tag:
                preco_atual = extrair_preco(preco_atual_tag.get_text())
                preco_antigo = extrair_preco(
                    preco_antigo_tag.find(
                        "span", class_="a-offscreen"
                    ).get_text()
                )

                if preco_atual and preco_antigo and preco_antigo > preco_atual:
                    desconto = (
                        (preco_antigo - preco_atual) / preco_antigo
                    ) * 100

                    if desconto >= DESCONTO_MINIMO_PORCENTAGEM:
                        mensagem = (
                            f"🚨 *OFERTA ENCONTRADA!*\n\n"
                            f"📦 *Produto:* {titulo}\n"
                            f"💰 *De:* ~R$ {preco_antigo:.2f}~\n"
                            f"🔥 *Por:* R$ {preco_atual:.2f} ({desconto:.0f}%"
                            f" OFF)\n\n"
                            f"🔗 [Clique aqui para comprar]({link_produto})"
                        )

                        print(
                            f"✅ Desconto de {desconto:.1f}% achado:"
                            f" {titulo[:30]}..."
                        )
                        enviar_alerta_telegram(mensagem, link_foto=link_foto)
                        time.sleep(2)

    except Exception as e:
        print(f"❌ Erro durante a busca de '{termo}': {e}")


def executar_monitoramento():
    for termo in TERMOS_BUSCA:
        buscar_ofertas_amazon(termo)
        # Pausa aleatória entre 8 e 15 segundos entre cada termo para evitar padrão humano fixo
        tempo_espera = random.randint(8, 15)
        time.sleep(tempo_espera)


if __name__ == "__main__":
    print("🤖 Bot de Ofertas por Busca Automática Iniciado!")
    print(
        f"🎯 Monitorando descontos a partir de {DESCONTO_MINIMO_PORCENTAGEM}%"
        " OFF\n"
    )
    executar_monitoramento()
