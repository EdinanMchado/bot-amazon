import os
import random
import re
import time
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from curl_cffi import requests

# ==============================================================================
# CONFIGURAÇÕES DO MODO BUG DE PREÇO (INCLUINDO PC HARDWARE)
# ==============================================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TAG_AFILIADO = "SEU_TAG_AFILIADO_AQUI"

# ⚡ CRITÉRIOS DE BUG
DESCONTO_MINIMO_BUG = 70.0  # Mínimo 70% OFF para apitar
PRECO_MINIMO_PRODUTO = 40.0  # Garante que é um produto/hardware de valor real

# 🛒 Termos de Busca (Geral + Hardware/Periféricos de Alta Demanda)
TERMOS_BUSCA = [
    # Eletrônicos & Consoles
    "smartphone",
    "air fryer",
    "notebook gamer",
    "fone bluetooth",
    "playstation 5",
    "tv 4k",
    "monitor gamer",
    # Hardware & Periféricos de PC
    "memoria ram ddr5",
    "ssd nvme",
    "placa de video",
    "processador intel ryzen",
    "teclado mecanico",
    "mouse gamer",
    "water cooler",
]

# 🛑 Apenas bugigangas reais e capas de celular/tablet (para não filtrar peças de PC)
TERMOS_IGNORADOS = [
    "capa para celular",
    "capinha",
    "pelicula",
    "película",
    "capa de tablet",
    "capa kindle",
    "cordão",
    "adesivo",
]

NAVEGADORES = ["chrome110", "chrome119", "chrome120", "edge101"]
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
        if response.status_code == 200:
            print("🚀 ALERTA DE BUG ENVIADO PARA O TELEGRAM!")
        else:
            print(f"❌ Erro ao enviar mensagem no Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Falha na conexão com o Telegram: {e}")


# ==============================================================================
# FUNÇÃO DE BUSCA E IDENTIFICAÇÃO DE BUGS
# ==============================================================================


def extrair_preco(texto):
    if not texto:
        return None
    texto_limpo = re.sub(r"[^\d,]", "", texto)
    if texto_limpo:
        return float(texto_limpo.replace(",", "."))
    return None


def buscar_bugs_amazon(termo):
    print(f"\n⚡ Caçando BUGS em: '{termo}'...")
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

                bugs_encontrados = 0
                for item in produtos:
                    tag_titulo = item.find("h2")
                    if not tag_titulo:
                        continue
                    titulo = tag_titulo.get_text(strip=True)
                    titulo_lower = titulo.lower()

                    # Bloqueia apenas capas e capas de celular/tablet
                    if any(ignora in titulo_lower for ignora in TERMOS_IGNORADOS):
                        continue

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
                            preco_antigo_tag.find("span", class_="a-offscreen").get_text()
                        )

                        if preco_atual and preco_antigo and preco_antigo > preco_atual:
                            desconto = ((preco_antigo - preco_atual) / preco_antigo) * 100

                            # 🎯 SE FOR DESCONTO SUPREMO (BUG REAL DE PREÇO)
                            if desconto >= DESCONTO_MINIMO_BUG and preco_atual >= PRECO_MINIMO_PRODUTO:
                                mensagem = (
                                    f"🔥 *POSSÍVEL BUG / PROMOÇÃO RELÂMPAGO!*\n\n"
                                    f"📦 *Produto:* {titulo}\n"
                                    f"💰 *De:* ~R$ {preco_antigo:.2f}~\n"
                                    f"💥 *Por:* R$ {preco_atual:.2f} ({desconto:.0f}% OFF)\n\n"
                                    f"⚡ *CORRA ANTES QUE CORRIGIAM:* [Link do Produto]({link_produto})"
                                )

                                print(f"🚨 BUG ENCONTRADO ({desconto:.1f}% OFF): {titulo[:35]}...")
                                enviar_alerta_telegram(mensagem, link_foto=link_foto)
                                bugs_encontrados += 1
                                time.sleep(5)

                if bugs_encontrados == 0:
                    print(f"ℹ️ Nenhum bug encontrado para '{termo}'.")

                break

            elif response.status_code == 503 and tentativa == 1:
                print("⚠️ Status 503 detectado. Aguardando 15 segundos...")
                time.sleep(15)

        except Exception as e:
            print(f"❌ Erro ao caçar bugs em '{termo}': {e}")


def executar_caca_bugs():
    termos_embaralhados = TERMOS_BUSCA.copy()
    random.shuffle(termos_embaralhados)

    for termo in termos_embaralhados:
        buscar_bugs_amazon(termo)
        tempo_espera = random.randint(15, 30)
        time.sleep(tempo_espera)


if __name__ == "__main__":
    print("🤖 Caçador de BUGS de Preço & Hardware Iniciado!")
    print(f"🎯 Notificando apenas descontos acima de {DESCONTO_MINIMO_BUG}% OFF.\n")
    executar_caca_bugs()
