import os
import random
import re
import time
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from curl_cffi import requests

# ==============================================================================
# CONFIGURAÇÕES DO CAÇA-BUGS PICHAU
# ==============================================================================

TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN", "8417768846:AAGOJQ1uINzL1ViHgRW4N12YEnR6w2z14f8"
)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "93372553")

# ⚡ REGRAS DE BUG SUPREMO
DESCONTO_MINIMO_BUG = 50.0  # Mínimo de 50% OFF para considerar bug/oportunidade
PRECO_MINIMO_PRODUTO = 30.0  # Mínimo de R$ 30 para evitar cabos e miudezas

# 🛒 Termos de Busca Focados em Hardware e Gamer na Pichau
TERMOS_BUSCA = [
    "memoria ddr4",
    "memoria ddr5",
    "ssd nvme",
    "placa de video",
    "rtx 4060",
    "rx 6600",
    "processador ryzen",
    "processador intel",
    "fonte 600w",
    "gabinete gamer",
    "water cooler",
    "teclado mecanico",
    "monitor gamer",
    "Cadeira",
    "Cadeira gamer",
]

# 🛑 Termos de itens genéricos para ignorar
TERMOS_IGNORADOS = [
    "cabo",
    "adaptador",
    "pasta termica",
    "parafuso",
    "suporte",
    "adesivo",
]

NAVEGADORES = ["chrome110", "chrome119", "chrome120", "edge101"]

# ==============================================================================
# FUNÇÕES AUXILIARES E TELEGRAM
# ==============================================================================


def extrair_preco(texto):
    """Limpa a string de preço e converte para float (ex: 'R$ 1.299,90' -> 1299.90)."""
    if not texto:
        return None
    texto_limpo = re.sub(r"[^\d,]", "", texto)
    if texto_limpo:
        try:
            return float(texto_limpo.replace(",", "."))
        except ValueError:
            return None
    return None


def enviar_alerta_telegram(mensagem, link_foto=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram não configurado corretamente.")
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
            print("🚀 ALERTA PICHAU ENVIADO PARA O TELEGRAM!")
        else:
            print(f"❌ Erro ao enviar mensagem no Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Falha na conexão com o Telegram: {e}")


# ==============================================================================
# SCRAPING PICHAU
# ==============================================================================


def buscar_bugs_pichau(termo):
    print(f"\n⚡ Caçando BUGS na Pichau em: '{termo}'...")
    url_busca = f"https://www.pichau.com.br/search?q={quote_plus(termo)}"

    try:
        browser = random.choice(NAVEGADORES)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.pichau.com.br/",
        }

        # Impersonate bypassa a checagem do Cloudflare da Pichau
        response = requests.get(
            url_busca, impersonate=browser, headers=headers, timeout=25
        )

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")

            # Mapeia os cards da listagem da Pichau
            produtos = soup.find_all(
                "div", class_=re.compile(r"MuiGrid-item|product-card")
            )
            bugs_encontrados = 0

            for item in produtos:
                # Procura por links de produto válidos
                link_tag = item.find("a", href=re.compile(r"^/"))
                tag_titulo = item.find(["h2", "hr"], text=True) or item.find(
                    "a"
                )

                if not link_tag or not tag_titulo:
                    continue

                titulo = tag_titulo.get_text(strip=True)
                titulo_lower = titulo.lower()

                # Ignora acessórios indesejados
                if any(
                    ignora in titulo_lower for ignora in TERMOS_IGNORADOS
                ):
                    continue

                link_produto = "https://www.pichau.com.br" + link_tag["href"]

                # Pega a imagem do produto
                tag_imagem = item.find("img")
                link_foto = (
                    tag_imagem["src"]
                    if tag_imagem and "src" in tag_imagem.attrs
                    else None
                )

                # Busca blocos de preços (Preço original De vs Preço no PIX Por)
                textos_preco = [
                    span.get_text() for span in item.find_all(["span", "p", "div"]) if "R$" in span.get_text()
                ]

                valores = []
                for txt in textos_preco:
                    val = extrair_preco(txt)
                    if val and val not in valores:
                        valores.append(val)

                if len(valores) >= 2:
                    preco_antigo = max(valores)
                    preco_atual = min(valores)

                    if preco_antigo > preco_atual:
                        desconto = (
                            (preco_antigo - preco_atual) / preco_antigo
                        ) * 100

                        if (
                            desconto >= DESCONTO_MINIMO_BUG
                            and preco_atual >= PRECO_MINIMO_PRODUTO
                        ):
                            mensagem = (
                                f"🔥 *POSSÍVEL BUG / OFERTA PICHAU!*\n\n"
                                f"📦 *Produto:* {titulo}\n"
                                f"💰 *De:* ~R$ {preco_antigo:.2f}~\n"
                                f"💥 *Por (À Vista/PIX):* R$ {preco_atual:.2f} ({desconto:.0f}% OFF)\n\n"
                                f"⚡ *CORRA:* [Ver na Pichau]({link_produto})"
                            )

                            print(
                                f"🚨 BUG ENCONTRADO ({desconto:.1f}% OFF):"
                                f" {titulo[:35]}..."
                            )
                            enviar_alerta_telegram(
                                mensagem, link_foto=link_foto
                            )

                            bugs_encontrados += 1
                            time.sleep(5)

            if bugs_encontrados == 0:
                print(f"ℹ️ Nenhum bug encontrado na Pichau para '{termo}'.")

        else:
            print(
                f"⚠️ Status {response.status_code} ao tentar acessar a Pichau."
            )

    except Exception as e:
        print(f"❌ Erro ao buscar na Pichau para '{termo}': {e}")


def executar_caca_bugs():
    termos_embaralhados = TERMOS_BUSCA.copy()
    random.shuffle(termos_embaralhados)

    for termo in termos_embaralhados:
        buscar_bugs_pichau(termo)
        tempo_espera = random.randint(15, 30)
        time.sleep(tempo_espera)


if __name__ == "__main__":
    print("🤖 Caçador de BUGS da Pichau Iniciado!")
    print(
        f"🎯 Monitorando descontos a partir de {DESCONTO_MINIMO_BUG}% OFF"
        f" (Mínimo R$ {PRECO_MINIMO_PRODUTO:.2f})\n"
    )
    executar_caca_bugs()
