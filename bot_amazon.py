import re
import time
from datetime import datetime
import urllib.parse
import requests
from bs4 import BeautifulSoup

# ==========================================
# CONFIGURAÇÕES DO TELEGRAM
# ==========================================
TELEGRAM_TOKEN = "8417768846:AAGOJQ1uINzL1ViHgRW4N12YEnR6w2z14f8"
TELEGRAM_CHAT_ID = "8492736362"

# ==========================================
# BUSCAS E PORCENTAGEM DE DESCONTO
# ==========================================
# Definir a % de desconto mínima para enviar o alerta (ex: 20 = 20% de desconto)
DESCONTO_MINIMO_PORCENTAGEM = 50.0

# Termos que você quer buscar na Amazon
TERMOS_BUSCA = [
    "Smartphone",
    "Memória RAM",
    "fone bluetooth",
    "SSD interno",
]

INTERVALO_SEGUNDOS = 900  # Checa a cada 15 minutos (900 segundos)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


def enviar_telegram(mensagem):
    """Envia mensagem de alerta via API do Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML",
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Erro ao enviar para o Telegram: {e}")
        return False


def extrair_valor(texto):
    """Auxiliar para converter texto de preço para float"""
    if not texto:
        return None
    numeros = re.findall(r"\d+[\.,]?\d*", texto)
    if numeros:
        valor_str = numeros[0].replace(".", "").replace(",", ".")
        try:
            return float(valor_str)
        except ValueError:
            return None
    return None


def buscar_produtos_por_termo(termo):
    """Faz a busca da palavra-chave na Amazon e analisa os produtos encontrados"""
    termo_encoded = urllib.parse.quote(termo)
    url_busca = f"https://www.amazon.com.br/s?k={termo_encoded}"

    print(f"\n🔍 Pesquisando por: '{termo}'...")

    try:
        response = requests.get(url_busca, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print("   ❌ Não foi possível carregar a página de busca.")
            return

        soup = BeautifulSoup(response.content, "html.parser")
        # Encontra os blocos de produtos na busca
        itens = soup.select('div[data-component-type="s-search-result"]')

        print(f"   📦 {len(itens)} produtos encontrados na lista.")

        for item in itens:
            # 1. Pega o título do produto
            titulo_elem = item.select_one(
                "h2 a span, span.a-size-medium, span.a-size-base-plus"
            )
            if not titulo_elem:
                continue
            nome = titulo_elem.get_text().strip()

            # 2. Pega o Link
            link_elem = item.select_one("h2 a")
            if not link_elem or "href" not in link_elem.attrs:
                continue
            link_produto = "https://www.amazon.com.br" + link_elem["href"]

            # 3. Pega o Preço Atual (Preço Por)
            preco_atual_elem = item.select_one("span.a-price span.a-offscreen")
            preco_atual = (
                extrair_valor(preco_atual_elem.get_text())
                if preco_atual_elem
                else None
            )

            # 4. Pega o Preço Original (Preço De / Riscado)
            preco_original_elem = item.select_one(
                "span.a-price.a-text-price span.a-offscreen"
            )
            preco_original = (
                extrair_valor(preco_original_elem.get_text())
                if preco_original_elem
                else None
            )

            # Só calcula o desconto se encontrou ambos os preços e o preço original for maior
            if (
                preco_atual
                and preco_original
                and preco_original > preco_atual
            ):
                desconto_reais = preco_original - preco_atual
                porcentagem_desconto = (desconto_reais / preco_original) * 100

                print(
                    f"   • {nome[:30]}... | De: R$ {preco_original:.2f} Por: R$ {preco_atual:.2f} ({porcentagem_desconto:.1f}% OFF)"
                )

                # Se a % de desconto for maior ou igual ao mínimo configurado, envia o alerta!
                if porcentagem_desconto >= DESCONTO_MINIMO_PORCENTAGEM:
                    msg = (
                        f"🔥 <b>OFERTA / DESCONTO IMPERDÍVEL!</b>\n\n"
                        f"📦 <b>Produto:</b> {nome}\n"
                        f"🏷️ <b>Desconto:</b> {porcentagem_desconto:.1f}% OFF\n"
                        f"❌ <b>De:</b> <s>R$ {preco_original:.2f}</s>\n"
                        f"✅ <b>Por:</b> R$ {preco_atual:.2f}\n"
                        f"💰 <b>Economia:</b> R$ {desconto_reais:.2f}\n\n"
                        f"🔗 <a href='{link_produto}'>Clique aqui para aproveitar na Amazon</a>"
                    )
                    if enviar_telegram(msg):
                        print("     ✅ Alerta de desconto enviado!")
                    else:
                        print("     ❌ Falha ao enviar alerta.")

            time.sleep(1)  # Pausa leve entre itens

    except Exception as e:
        print(f"Erro ao realizar a busca por '{termo}': {e}")


def executar_monitoramento():
    """Roda o ciclo de busca em todas as palavras-chave"""
    horario_atual = datetime.now().strftime("%H:%M:%S")
    print(f"\n==========================================")
    print(f"🚀 Varredura por Descontos Iniciada em {horario_atual}")
    print(f"==========================================")

    for termo in TERMOS_BUSCA:
        buscar_produtos_por_termo(termo)
        time.sleep(3)  # Pausa entre buscas para evitar bloqueios


if __name__ == "__main__":
    print("🤖 Bot de Ofertas por Busca Automática Iniciado!")
    print(
        f"🎯 Monitorando descontos a partir de {DESCONTO_MINIMO_PORCENTAGEM}% OFF\n"
    )
    executar_monitoramento()
