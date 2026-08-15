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
    "fone bluetooth",
    "playstation 5",
]

# Impersonations suportadas pelo curl_cffi
NAVEGADORES = ["chrome110", "chrome119", "chrome120", "edge101"]

# Headers realistas de navegador humano
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]

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
        response = requests.post(url, data=payload, timeout=10)
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

    for tentativa in range(1, 3):
        try:
            browser = random.choice(NAVEGADORES)
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://www.amazon.com.br/",
                "DNT": "1",
                "Upgrade-Insecure-Requests": "1",
            }

            response = requests.get(
                url_busca,
                impersonate=browser,
                headers=headers,
                timeout=20,
            )

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                produtos = soup.find_all(
                    "div", {"data-component-type": "s-search-result"}
                )

                ofertas_encontradas = 0
                for item in produtos:
                    tag_titulo = item.find("h2")
                    if not tag_titulo:
                        continue
                    titulo = tag_titulo.get_text(strip=True)

                    link_tag = item.find(
                        "a", class_="a-link-normal s-no-outline"
                    )
                    if not link_tag or "href" not in link_tag.attrs:
                        continue
                    link_produto = (
                        "https://www.amazon.com.br" + link_tag["href"]
                    )
                    if TAG_AFILIADO:
                        link_produto += f"&tag={TAG_AFILIADO}"

                    tag_imagem = item.find("img", class_="s-image")
                    link_foto = tag_imagem["src"] if tag_imagem else None

                    preco_atual_tag = item.find("span", class_="a-price-whole")
                    preco_antigo_tag = item.find("span", class_="a-text-price")

                    if preco_atual_tag and preco_antigo_tag:
                        preco_atual = extrair_preco(
                            preco_atual_tag.get_text()
                        )
                        preco_antigo = extrair_preco(
                            preco_antigo_tag.find(
                                "span", class_="a-offscreen"
                            ).get_text()
                        )

                        if (
                            preco_atual
                            and preco_antigo
                            and preco_antigo > preco_atual
                        ):
                            desconto = (
                                (preco_antigo - preco_atual) / preco_antigo
                            ) * 100

                            if desconto >= DESCONTO_MINIMO_PORCENTAGEM:
                                mensagem = (
                                    f"🚨 *OFERTA ENCONTRADA!*\n\n"
                                    f"📦 *Produto:* {titulo}\n"
                                    f"💰 *De:* ~R$ {preco_antigo:.2f}~\n"
                                    f"🔥 *Por:* R$ {preco_atual:.2f}"
                                    f" ({desconto:.0f}% OFF)\n\n"
                                    f"🔗 [Clique aqui para comprar]({link_produto})"
                                )

                                print(
                                    f"✅ Desconto de {desconto:.1f}% achado:"
                                    f" {titulo[:30]}..."
                                )
                                enviar_alerta_telegram(
                                    mensagem, link_foto=link_foto
                                )
                                ofertas_encontradas += 1
                                time.sleep(4)

                if ofertas_encontradas == 0:
                    print("ℹ️ Nenhuma oferta acima de 50% OFF nesta busca.")

                break

            elif response.status_code == 503 and tentativa == 1:
                print(
                    "⚠️ Status 503 detectado. Aguardando 15 segundos para tentar"
                    " novamente..."
                )
                time.sleep(15)
            else:
                print(
                    f"⚠️ Não foi possível acessar a busca (Status:"
                    f" {response.status_code})"
                )

        except Exception as e:
            print(f"❌ Erro durante a busca de '{termo}': {e}")


def executar_monitoramento():
    termos_embaralhados = TERMOS_BUSCA.copy()
    random.shuffle(termos_embaralhados)

    for termo in termos_embaralhados:
        buscar_ofertas_amazon(termo)
        tempo_espera = random.randint(15, 30)
        time.sleep(tempo_espera)


if __name__ == "__main__":
    print("🤖 Bot de Ofertas por Busca Automática Iniciado!")
    print(
        f"🎯 Monitorando descontos a partir de {DESCONTO_MINIMO_PORCENTAGEM}%"
        " OFF\n"
    )
    executar_monitoramento()
