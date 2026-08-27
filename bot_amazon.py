import os
import random
import re
import time
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from curl_cffi import requests

# ==============================================================================
# CONFIGURAÇÕES DO CAÇA-BUGS (HARDWARE, CASA & ELETRÔNICOS)
# ==============================================================================

TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN", "8417768846:AAGOJQ1uINzL1ViHgRW4N12YEnR6w2z14f8"
)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8492736362")
TAG_AFILIADO = "SEU_TAG_AFILIADO_AQUI"  # Altere para a sua tag de afiliado Amazon

# ⚡ REGRAS DE BUG SUPREMO
DESCONTO_MINIMO_BUG = 65.0  # Mínimo de 65% OFF para considerar oportunidade/bug
PRECO_MINIMO_PRODUTO = 25.0  # Mínimo de R$ 25 para evitar bugigangas e capas

# 🛒 Termos de Busca Focados em Oportunidades e Bugs de Preço
TERMOS_BUSCA = [
    # Hardware & Informática
    "memoria ram ddr4",
    "memoria ram ddr5",
    "ssd nvme",
    "placa de video",
    "processador",
    "teclado mecanico",
    "mouse gamer",
    "monitor gamer",
    # Eletrônicos & Consoles
    "smartphone",
    "air fryer",
    "notebook gamer",
    "playstation 5",
    "fone bluetooth",
    # Casa, Cama & Decoração (onde ocorrem erros brutais de cadastro)
    "kit sofa cama",
    "jogo de cama casal",
    "duvet",
    "cabeceira",
    "panela polishop",
]

# 🛑 Apenas capas genéricas de celular/tablet para evitar falso-positivo
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
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101"
        " Firefox/123.0"
    ),
]

# ==============================================================================
# FUNÇÃO INTEGRAÇÃO KEEPA & TELEGRAM
# ==============================================================================


def extrair_asin(url_produto):
    """Extrai o código ASIN único do produto da URL da Amazon."""
    match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url_produto)
    if match:
        return match.group(1)
    return None


def obter_link_grafico_keepa(asin):
    """Gera o link da imagem do gráfico histórico de preços do Keepa para o Brasil (Domain 12 = BR)."""
    if not asin:
        return None
    # Domain 12 corresponde à Amazon.com.br no Keepa
    return f"https://graph.keepa.com/pricehistory.png?domain=12&asin={asin}"


def enviar_alerta_telegram(mensagem, link_foto=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram não configurado nos Secrets/Variáveis de ambiente.")
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
# FUNÇÃO DE SCRAPING E IDENTIFICAÇÃO DE BUGS
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
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
                ),
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

                    # Bloqueia apenas capas e películas genéricas
                    if any(
                        ignora in titulo_lower for ignora in TERMOS_IGNORADOS
                    ):
                        continue

                    link_tag = item.find(
                        "a", class_="a-link-normal s-no-outline"
                    )
                    if not link_tag or "href" not in link_tag.attrs:
                        continue
                    link_produto = (
                        "https://www.amazon.com.br" + link_tag["href"]
                    )

                    # Extrai o ASIN e gera o gráfico do Keepa
                    asin = extrair_asin(link_produto)
                    link_keepa_web = (
                        f"https://keepa.com/#!product/12-{asin}"
                        if asin
                        else link_produto
                    )

                    if TAG_AFILIADO and TAG_AFILIADO != "SEU_TAG_AFILIADO_AQUI":
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

                            # 🎯 CRITÉRIO DE BUG REFINADO
                            if (
                                desconto >= DESCONTO_MINIMO_BUG
                                and preco_atual >= PRECO_MINIMO_PRODUTO
                            ):
                                mensagem = (
                                    f"🔥 *POSSÍVEL BUG / PROMOÇÃO RELÂMPAGO!*\n\n"
                                    f"📦 *Produto:* {titulo}\n"
                                    f"💰 *De:* ~R$ {preco_antigo:.2f}~\n"
                                    f"💥 *Por:* R$ {preco_atual:.2f} ({desconto:.0f}% OFF)\n\n"
                                    f"📊 [Ver Histórico no Keepa]({link_keepa_web})\n"
                                    f"⚡ *CORRA ANTES QUE CORRIGIAM:* [Comprar na Amazon]({link_produto})"
                                )

                                print(
                                    f"🚨 BUG ENCONTRADO ({desconto:.1f}% OFF):"
                                    f" {titulo[:35]}..."
                                )

                                # Se tiver ASIN, envia o gráfico histórico do Keepa como imagem do alerta
                                foto_alerta = (
                                    obter_link_grafico_keepa(asin)
                                    if asin
                                    else link_foto
                                )
                                enviar_alerta_telegram(
                                    mensagem, link_foto=foto_alerta
                                )

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
    print("🤖 Caçador de BUGS da Amazon + Keepa Iniciado!")
    print(
        f"🎯 Monitorando descontos a partir de {DESCONTO_MINIMO_BUG}% OFF"
        f" (Mínimo R$ {PRECO_MINIMO_PRODUTO:.2f})\n"
    )
    executar_caca_bugs()
