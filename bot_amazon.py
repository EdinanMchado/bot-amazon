import os
import re
import time
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup

# ==============================================================================
# CONFIGURAÇÕES PRINCIPAIS
# ==============================================================================

# Insira aqui o Token do seu Bot do Telegram e o Chat ID
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TELEGRAM_TOKEN_AQUI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "SEU_TELEGRAM_CHAT_ID_AQUI")

# Tag de Afiliado da Amazon (opcional, se não tiver deixe em branco "")
TAG_AFILIADO = "SEU_TAG_AFILIADO_AQUI"

# Porcentagem mínima de desconto para disparar o alerta
DESCONTO_MINIMO_PORCENTAGEM = 20.0

# Termos que você quer monitorar automaticamente
TERMOS_BUSCA = [
    "smartphone",
    "air fryer",
    "notebook",
    "smartwatch",
    "fone bluetooth",
    "playstation 5",
    "Eau de Parfum",
    "Air Fryers",
]

# Headers para simular um navegador real e evitar bloqueios
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ==============================================================================
# FUNÇÃO DE ENVIO PARA O TELEGRAM (COM FOTO)
# ==============================================================================


def enviar_alerta_telegram(mensagem, link_foto=None):
    """Envia a mensagem para o Telegram.

    Se houver link de foto, envia como imagem com legenda.
    """
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
        response = requests.post(url, data=payload)
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
    """Converte texto de preço no formato brasileiro para float."""
    if not texto:
        return None
   # Remove R$, espaços e converte pontos de milhar e vírgula decimal
    texto_limpo = re.sub(r"[^\d,]", "", texto)
    if texto_limpo:
        return float(texto_limpo.replace(",", "."))
    return None


def buscar_ofertas_amazon(termo):
    print(f"\n🔍 Pesquisando por: '{termo}' na Amazon...")
    url_busca = f"https://www.amazon.com.br/s?k={quote_plus(termo)}"

    try:
        response = requests.get(url_busca, headers=HEADERS, timeout=10)
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
            # 1. Título do Produto
            tag_titulo = item.find("h2")
            if not tag_titulo:
                continue
            titulo = tag_titulo.get_text(strip=True)

            # 2. Link do Produto
            link_tag = item.find("a", class_="a-link-normal s-no-outline")
            if not link_tag or "href" not in link_tag.attrs:
                continue
            link_produto = "https://www.amazon.com.br" + link_tag["href"]
            if TAG_AFILIADO:
                link_produto += f"&tag={TAG_AFILIADO}"

            # 3. Imagem do Produto (Captura Automática)
            tag_imagem = item.find("img", class_="s-image")
            link_foto = tag_imagem["src"] if tag_imagem else None

            # 4. Preço Atual e Preço Antigo
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

                    # Verifica se o desconto atinge o mínimo configurado
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
                            f"✅ Desconto de {desconto:.1f}% achado: {titulo[:30]}..."
                        )
                        enviar_alerta_telegram(
                            mensagem, link_foto=link_foto
                        )
                        time.sleep(1)  # Pausa de segurança entre alertas

    except Exception as e:
        print(f"❌ Erro durante a busca de '{termo}': {e}")


def executar_monitoramento():
    for termo in TERMOS_BUSCA:
        buscar_ofertas_amazon(termo)
        time.sleep(3)  # Pausa entre termos de busca para evitar bloqueios


if __name__ == "__main__":
    print("🤖 Bot de Ofertas por Busca Automática Iniciado!")
    print(
        f"🎯 Monitorando descontos a partir de {DESCONTO_MINIMO_PORCENTAGEM}% OFF\n"
    )
    executar_monitoramento()
