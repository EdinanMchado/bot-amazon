import os
import random
import re
import time
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from curl_cffi import requests

# ==============================================================================
# CONFIGURAÇÕES PRINCIPAIS E REGRAS ANTI-FAKE
# ==============================================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TAG_AFILIADO = "SEU_TAG_AFILIADO_AQUI"

# 🛒 Termos que o robô vai buscar na Amazon
TERMOS_BUSCA = [
    "smartphone",
    "air fryer",
    "notebook",
    "fone bluetooth",
    "playstation 5",
    "sabonete",
    "shampoo",
]

# 🧴 Categorias com tratamento especial anti-fake
TERMOS_HIGIENE = ["sabonete", "shampoo", "condicionador", "desodorante", "sabonetes"]

# 🛑 Palavras-chave de acessórios a serem ignorados nas buscas de eletrônicos
TERMOS_IGNORADOS_ELETRONICOS = [
    "capa",
    "capinha",
    "case",
    "pelicula",
    "película",
    "suporte",
    "cabo",
    "carregador",
    "adaptador",
    "cordão",
    "proteção",
]

# Impersonations e User-Agents para evitar Status 503
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
            print("🚀 Alerta enviado com sucesso para o Telegram!")
        else:
            print(f"❌ Erro ao enviar mensagem no Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Falha na conexão com o Telegram: {e}")


# ==============================================================================
# FUNÇÕES DE PROCESSAMENTO E SCRAPING DA AMAZON
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
    is_higiene = any(higiene in termo.lower() for higiene in TERMOS_HIGIENE)

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
                    titulo_lower = titulo.lower()

                    # 1. Filtro Anti-Acessórios (aplica em eletrônicos/tecnologia)
                    if not is_higiene:
                        if any(ignora in titulo_lower for ignora in TERMOS_IGNORADOS_ELETRONICOS):
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

                            # 2. Lógica de Validação por Categoria
                            oferta_valida = False

                            if is_higiene:
                                # Sabonete/Shampoo: aceita descontos de 20% a 35% e valor mínimo de R$ 15 (foco em kits)
                                if 20.0 <= desconto <= 35.0 and preco_atual >= 15.0:
                                    oferta_valida = True
                                else:
                                    if desconto > 35.0:
                                        print(f"⚠️ Descartado (Desconto fake em higiene {desconto:.1f}%): {titulo[:30]}...")
                            else:
                                # Eletrônicos/Geral: aceita descontos de 45% a 75% e valor mínimo de R$ 40
                                if 45.0 <= desconto <= 75.0 and preco_atual >= 40.0:
                                    oferta_valida = True
                                else:
                                    if desconto > 75.0:
                                        print(f"⚠️ Descartado (Preço inflado/suspeito {desconto:.1f}%): {titulo[:30]}...")

                            if oferta_valida:
                                mensagem = (
                                    f"🚨 *OFERTA VERIFICADA!*\n\n"
                                    f"📦 *Produto:* {titulo}\n"
                                    f"💰 *De:* ~R$ {preco_antigo:.2f}~\n"
                                    f"🔥 *Por:* R$ {preco_atual:.2f} ({desconto:.0f}% OFF)\n\n"
                                    f"🔗 [Clique aqui para comprar]({link_produto})"
                                )

                                print(f"✅ Oferta válida ({desconto:.1f}% OFF): {titulo[:30]}...")
                                enviar_alerta_telegram(mensagem, link_foto=link_foto)
                                ofertas_encontradas += 1
                                time.sleep(5)  # Pausa para aliviar tráfego do Telegram

                if ofertas_encontradas == 0:
                    print("ℹ️ Nenhuma oferta dentro dos critérios de segurança encontrada nesta busca.")

                break

            elif response.status_code == 503 and tentativa == 1:
                print("⚠️ Status 503 detectado. Aguardando 15 segundos...")
                time.sleep(15)
            else:
                print(f"⚠️ Não foi possível acessar a busca (Status: {response.status_code})")

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
    print("🤖 Bot de Ofertas Inteligente Iniciado!")
    print("🎯 Filtros Anti-Fake por Categoria Ativos.\n")
    executar_monitoramento()
