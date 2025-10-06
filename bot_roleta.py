import time
import requests
from datetime import datetime
import pytz
import os
import re

# INÍCIO DO KEEP ALIVE (usado no Render.com)
if os.environ.get("RENDER"):
    from keep_alive import keep_alive
    keep_alive()

# CONFIGURAÇÕES DO TELEGRAM
TOKEN = '8390745428:AAHX5Iaahc3AKPVFxYCl7-EQvzSeiivuuvI'
CHAT_ID = '-1002787535355'
INTERVALO = 5  # segundos entre verificações

# TIMEZONE BRASÍLIA
fuso_brasilia = pytz.timezone("America/Sao_Paulo")

# CONTADORES DE SINAIS POR HORA
sinais_por_hora = {hora: 0 for hora in range(24)}
total_sinais_dia = 0
ultima_hora = datetime.now(fuso_brasilia).hour

# URLS DAS APIS DAS MESAS
MESAS_API = {
    # Pragmatic
    "Brazilian Roulette": "https://api.revesbot.com.br/history/pragmatic-brazilian-roulette",
    "Auto Roulette": "https://api.revesbot.com.br/history/pragmatic-auto-roulette",
    "Immersive Roulette Deluxe": "https://api.revesbot.com.br/history/pragmatic-immersive-roulette-deluxe",
    "Mega Roulette": "https://api.revesbot.com.br/history/pragmatic-mega-roulette",
    "Auto Mega Roulette": "https://api.revesbot.com.br/history/pragmatic-auto-mega-roulette",

    # Evolution
    "Evolution Roulette": "https://api.revesbot.com.br/history/evolution-roulette",
    "Evolution Immersive Roulette": "https://api.revesbot.com.br/history/evolution-immersive-roulette",
    "Evolution Auto Roulette VIP": "https://api.revesbot.com.br/history/evolution-auto-roulette-vip",
    "Evolution Roleta ao Vivo": "https://api.revesbot.com.br/history/evolution-roleta-ao-vivo",
    "Evolution Ruleta Bola Rápida EN Vivo": "https://api.revesbot.com.br/history/evolution-ruleta-bola-rapida-en-vivo",
}

# 🔧 LISTA DE PROVEDORES BLOQUEADOS
# Escreva "PRAGMATIC" ou "EVOLUTION" (ou ambos) para pausar a coleta
# Exemplo: PROVEDORES_BLOQUEADOS = ["PRAGMATIC"]
PROVEDORES_BLOQUEADOS = ["EVOLUTION"]

# LINKS DAS MESAS PARA JOGAR
MESAS_LINK = {
    # Pragmatic
    "Brazilian Roulette": "https://www.betano.bet.br/casino/live/games/brazilian-roulette/11354/tables/",
    "Auto Roulette": "https://www.betano.bet.br/casino/live/games/auto-roulette/3502/tables/?entrypoint=1",
    "Immersive Roulette Deluxe": "https://www.betano.bet.br/casino/live/games/immersive-roulette-deluxe/23563/tables/?entrypoint=1",
    "Mega Roulette": "https://www.betano.bet.br/casino/live/games/mega-roulette/3523/tables/?entrypoint=1",
    "Auto Mega Roulette": "https://www.betano.bet.br/casino/live/games/auto-mega-roulette/10842/tables/?entrypoint=1",

    # Evolution
    "Evolution Roulette": "https://www.betano.bet.br/casino/live/games/roulette/1526/tables/",
    "Evolution Immersive Roulette": "https://www.betano.bet.br/casino/live/games/immersive-roulette/1527/tables/",
    "Evolution Auto Roulette VIP": "https://www.betano.bet.br/casino/live/games/auto-roulette-vip/1539/tables/",
    "Evolution Roleta ao Vivo": "https://www.betano.bet.br/casino/live/games/roleta-ao-vivo/7899/tables/?entrypoint=1",
    "Evolution Ruleta Bola Rápida EN Vivo": "https://www.betano.bet.br/casino/live/games/ruleta-bola-rapida-en-vivo/4695/tables/",
}

# Fichas mínimas
FICHAS_MINIMAS = {
    # Pragmatic
    "Brazilian Roulette": 0.50,
    "Auto Roulette": 2.50,
    "Immersive Roulette Deluxe": 0.50,
    "Mega Roulette": 0.50,
    "Auto Mega Roulette": 0.50,

    # Evolution
    "Evolution Roulette": 2.50,
    "Evolution Immersive Roulette": 5.00,
    "Evolution Auto Roulette VIP": 1.00,
    "Evolution Roleta ao Vivo": 1.00,
    "Evolution Ruleta Bola Rápida EN Vivo": 2.50,
}

gatilhos = {}

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': mensagem,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("[✅ MENSAGEM ENVIADA AO TELEGRAM]")
        else:
            print(f"[❌ ERRO AO ENVIAR TELEGRAM] Código {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"[❌ ERRO ENVIO TELEGRAM] {e}")

def extrair_numeros(json_data):
    """Extrai lista de números, tratando string, dict e list."""
    try:
        if isinstance(json_data, str):
            return [int(n) for n in re.findall(r'\d+', json_data)]
        elif isinstance(json_data, list):
            return [int(n) for n in json_data if isinstance(n, int)]
        elif isinstance(json_data, dict):
            for chave in ["results", "data", "lastNumbers"]:
                if chave in json_data and isinstance(json_data[chave], list):
                    return [int(n) for n in json_data[chave] if isinstance(n, int)]
            for value in json_data.values():
                if isinstance(value, list) and all(isinstance(n, int) for n in value):
                    return value
        return []
    except Exception as e:
        print(f"[❌ ERRO AO EXTRAIR NÚMEROS] {e}")
        return []

def verificar_resultados():
    headers = {"User-Agent": "Mozilla/5.0"}
    for nome_mesa, url_api in MESAS_API.items():

        # Se o nome da mesa contiver algum provedor bloqueado, pula
        if any(prov in nome_mesa.upper() for prov in PROVEDORES_BLOQUEADOS):
            print(f"⏸ Coleta pausada para o provedor: {nome_mesa}")
            continue

        print(f"\n🔎 Checando mesa: {nome_mesa}")
        try:
            response = requests.get(url_api, headers=headers, timeout=10)
            if response.status_code == 200:
                json_data = response.json()
                numeros = extrair_numeros(json_data)
                print(f"📊 Últimos números (mais recente à esquerda): {numeros[:15]}")
                processar_resultados(nome_mesa, numeros)
            else:
                print(f"[⚠️ ERRO API] Código {response.status_code} na mesa {nome_mesa}")
        except Exception as e:
            print(f"[❌ ERRO CONEXÃO] Mesa {nome_mesa}: {e}")

def processar_resultados(nome_mesa, numeros):
    global gatilhos, total_sinais_dia, sinais_por_hora
    if not numeros:
        return

    tamanho = len(numeros)

    for i in range(tamanho):
        alvo = numeros[i]
        if 1 <= alvo <= 10:
            pos_gatilho = i + alvo
            if pos_gatilho < tamanho:
                gatilho = numeros[pos_gatilho]
                terminal = alvo % 10

                if gatilho in numeros[0:i]:
                    continue

                if gatilho not in gatilhos:
                    gatilhos[gatilho] = []

                ja_existe = any(x['mesa'] == nome_mesa and x['terminal'] == terminal for x in gatilhos[gatilho])
                if not ja_existe:
                    gatilhos[gatilho].append({
                        'mesa': nome_mesa,
                        'terminal': terminal,
                        'ativo': True
                    })
                    print(f"[🎯 GATILHO SALVO] {gatilho} → Terminal {terminal} (Mesa: {nome_mesa})")

    numero_mais_recente = numeros[0]
    novas_entradas = []

    # percorre todos os gatilhos salvos
    for num_gatilho, entradas in gatilhos.items():
        if num_gatilho == numero_mais_recente:
            for entrada in entradas:
                if entrada['ativo'] and entrada['mesa'] == nome_mesa:
                    entrada['ativo'] = False
                    novas_entradas.append(entrada)

    # Lógica para enviar a mensagem do Telegram
    for entrada in novas_entradas:
        ficha_minima = FICHAS_MINIMAS.get(nome_mesa, "N/A")
        mensagem = (
            f"🎯 **GATILHO ATIVADO!**\n"
            f"🎰 **Mesa:** {nome_mesa}  \n"
            f"💰 **Ficha mínima:** R$ {ficha_minima:.2f}  \n"
            f"🔁 **Gatilho:** {numero_mais_recente}  \n"
            f"🎯 **Entrada:** Terminal {entrada['terminal']} + Viz + 0.  \n"
            f"🎮 **Acessar Mesa Ao Vivo:** \n"
            f"🔗 {MESAS_LINK[nome_mesa]}"
        )
        enviar_telegram(mensagem)

        hora_brasilia = datetime.now(fuso_brasilia).hour
        sinais_por_hora[hora_brasilia] += 1
        total_sinais_dia += 1

def checar_relatórios_horarios():
    global ultima_hora, sinais_por_hora, total_sinais_dia
    agora = datetime.now(fuso_brasilia)
    hora_atual = agora.hour
    minuto = agora.minute

    if minuto == 0 and hora_atual != ultima_hora:
        hora_passada = (hora_atual - 1) % 24
        enviados = sinais_por_hora[hora_passada]
        mensagem = f"📈 Sinais enviados entre {hora_passada:02d}:00 e {hora_atual:02d}:00: {enviados}"
        enviar_telegram(mensagem)

        if hora_atual == 22:
            horas_validas = [v for v in sinais_por_hora.values() if v > 0]
            media = total_sinais_dia / len(horas_validas) if horas_validas else 0
            resumo = f"📊 Média de sinais hoje: *{media:.2f} por hora* ({total_sinais_dia} no total)."
            enviar_telegram(resumo)

            sinais_por_hora = {hora: 0 for hora in range(24)}
            total_sinais_dia = 0
            print("[🔁 CONTADORES REINICIADOS PARA O NOVO DIA]")

        ultima_hora = hora_atual

# Início do bot
print("[🤖 BOT INICIADO] Monitorando mesas...")
enviar_telegram("🤖 Bot de Gatilhos iniciado com sucesso!")

while True:
    verificar_resultados()
    checar_relatórios_horarios()
    time.sleep(INTERVALO)

