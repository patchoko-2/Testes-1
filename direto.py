import time
import requests
import re
import os
from datetime import datetime
import pytz
from collections import deque, Counter
import json
import urllib.parse
from keep_alive import keep_alive


# --- CONFIGURAÇÕES GLOBAIS ---
TOKEN = '8390745428:AAHX5Iaahc3AKPVFxYCl7-EQvzSeiivuuvI' # GRUPO DO Bot do botlittle
CHAT_ID = '-1002787535355'
INTERVALO = 3

# CONTROLE DA VARREDURA INICIAL
VARREDURA_INICIAL_TELEGRAM = 'off'

# TIMEZONE BRASÍLIA
FUSO_BRASILIA = pytz.timezone("America/Sao_Paulo")

# --- CONFIGURAÇÕES FINANCEIRAS E DE BANCA ---
BANCA_INICIAL = 500.00

# Ordem dos lucros por tentativa (1/4 a 4/4) - Valores em R$
GREEN_VALUES_POR_TENTATIVA = {
    1: 23.0,
    2: 33.0,
    3: 18.5,
    4: 9.0
}
# Valor de perda por Red
RED_VALUE = 117.0

# --- VARIÁVEIS DE ESTADO FINANCEIRO ---
BANCA_ATUAL = BANCA_INICIAL
BANCA_ZERADA = False
ENTRADAS_AO_ZERAR = 0
TOTAL_LUCRO_GREEN = 0.0
TOTAL_PERDA_RED = 0.0

# --- CONTROLE DE METAS ---
META_HISTORICO = []

# --- ORDEM DA ROLETA EUROPEIA ---
ORDEM_ROLETA = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

# --- NÚMEROS DOS TRINTA (GATILHO) ---
NUMEROS_TRINTA = {30, 31, 32, 33, 34, 35, 36}

# --- MESAS, FICHAS E PROVEDORES ---
MESAS_API = {
    "Brazilian Roulette": "https://api.revesbot.com.br/history/pragmatic-brazilian-roulette",
    "Auto Roulette": "https://api.revesbot.com.br/history/pragmatic-auto-roulette",
    "Immersive Roulette Deluxe": "https://api.revesbot.com.br/history/pragmatic-immersive-roulette-deluxe",
    "Mega Roulette": "https://api.revesbot.com.br/history/pragmatic-mega-roulette",
    "Auto Mega Roulette": "https://api.revesbot.com.br/history/pragmatic-auto-mega-roulette",
    "Korean Roulette": "https://api.revesbot.com.br/history/pragmatic-korean-roulette",
}

FICHAS_MINIMAS = {
    "Brazilian Roulette": 0.50,
    "Auto Roulette": 0.50,
    "Immersive Roulette Deluxe": 0.50,
    "Mega Roulette": 0.50,
    "Auto Mega Roulette": 0.50,
    "Korean Roulette": 0.50,
}

MESAS_PROVEDORES = {
    "Brazilian Roulette": "Pragmatic",
    "Auto Roulette": "Pragmatic",
    "Immersive Roulette Deluxe": "Pragmatic",
    "Mega Roulette": "Pragmatic",
    "Auto Mega Roulette": "Pragmatic",
    "Korean Roulette": "Pragmatic",
}

PROVEDORES_BLOQUEADOS = ["EVOLUTION"]

# --- VARIÁVEIS DE ESTADO ---
history = {f"{MESAS_PROVEDORES[mesa]}:{mesa}": deque(maxlen=500) for mesa in MESAS_API.keys()}
monitoramento_sinais = []

# ESTATÍSTICAS
estatisticas = {
    "entradas": 0,
    "greens": 0,
    "reds": 0,
    "greens_por_tentativa": Counter(),
    "reds_total": 0,
}

sinais_por_hora = {hora: 0 for hora in range(24)}
total_sinais_dia = 0
ultima_hora = datetime.now(FUSO_BRASILIA).hour
START_TIME = time.time()
relatorio_diario_por_hora = []

# --- FUNÇÕES AUXILIARES DE CÁLCULO ---

def get_alvos_roleta(alvo_principal, count=6):
    """
    Calcula o alvo principal e seus 'count' vizinhos para cada lado
    na ordem da roleta (13 fichas no total: o alvo + 6 para cada lado).
    """
    if alvo_principal not in ORDEM_ROLETA:
        return set()

    idx = ORDEM_ROLETA.index(alvo_principal)
    vizinhos = {alvo_principal}

    for i in range(1, count + 1):
        vizinhos.add(ORDEM_ROLETA[(idx + i) % 37])
        vizinhos.add(ORDEM_ROLETA[(idx - i + 37) % 37])

    return vizinhos

def resetar_estatisticas():
    """
    Reseta todas as estatísticas quando a meta é atingida.
    """
    global estatisticas, BANCA_ATUAL, BANCA_ZERADA, ENTRADAS_AO_ZERAR
    global TOTAL_LUCRO_GREEN, TOTAL_PERDA_RED

    estatisticas = {
        "entradas": 0,
        "greens": 0,
        "reds": 0,
        "greens_por_tentativa": Counter(),
        "reds_total": 0,
    }

    BANCA_ATUAL = BANCA_INICIAL
    BANCA_ZERADA = False
    ENTRADAS_AO_ZERAR = 0
    TOTAL_LUCRO_GREEN = 0.0
    TOTAL_PERDA_RED = 0.0

    print("[RESET] Estatísticas resetadas por atingir a meta!")

# --- FUNÇÕES DE TELEGRAM ---
def enviar_telegram(msg: str, parse_mode='MarkdownV2'):
    def escape_md(text):
        special_chars = r'_*[]()~`>#+-=|{}.!'
        for ch in special_chars:
            text = text.replace(ch, "\\" + ch)
        return text

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        safe_msg = escape_md(msg)
        response = requests.post(
            url,
            data={'chat_id': CHAT_ID, 'text': safe_msg, 'parse_mode': parse_mode},
            timeout=20
        )
        if response.status_code != 200 or not response.json().get('ok'):
            print(f"[ERRO TELEGRAM] Falha ao enviar mensagem. Status: {response.status_code}")
            if response.status_code == 400:
                response_fallback = requests.post(
                    url,
                    data={'chat_id': CHAT_ID, 'text': msg},
                    timeout=10
                )
    except requests.exceptions.RequestException as e:
        print(f"[ERRO TELEGRAM] Exceção: {e}")

def enviar_relatorio(dados_sinal, status, tentativa_vitoria=None, max_tentativas=4, numero_vencedor=None):
    """
    Envia o relatório final (Green/Red) formatado.
    """
    global BANCA_ATUAL, BANCA_ZERADA, ENTRADAS_AO_ZERAR, TOTAL_LUCRO_GREEN, TOTAL_PERDA_RED

    mesa = dados_sinal['mesa']
    alvo_numero = dados_sinal['alvo_numero']
    alvos = dados_sinal['alvos']
    link_api = dados_sinal['link_api']
    ultimos_3 = dados_sinal['ultimos_3']

    if status == 'Green':
        msg_status_texto = f"✅ Green na {tentativa_vitoria}/4\nVitória no numero: {numero_vencedor}"
    else:
        msg_status_texto = "❌ Red"

    assertividade = (estatisticas['greens']/estatisticas['entradas']*100) if estatisticas['entradas']>0 else 0

    # Bloco de estatísticas por tentativa
    bloco_estatisticas_financeiro = ""
    for t in range(1, 5):
        vitorias = estatisticas['greens_por_tentativa'].get(t, 0)
        lucro_por_vitoria = GREEN_VALUES_POR_TENTATIVA.get(t, 0.0)
        lucro_total = vitorias * lucro_por_vitoria
        bloco_estatisticas_financeiro += (
            f"{t}/4 - {vitorias} vitórias * R${lucro_por_vitoria:.2f} = R${lucro_total:.2f}\n"
        )

    perda_total_red = estatisticas['reds_total'] * RED_VALUE
    bloco_estatisticas_financeiro += (
        f"\n============================\n"
        f"Red\n"
        f"{estatisticas['reds_total']} perdas * R${RED_VALUE:.2f} = R${perda_total_red:.2f}"
    )

    resultado_liquido = TOTAL_LUCRO_GREEN - TOTAL_PERDA_RED

    banca_atual_str = f"R${BANCA_ATUAL:.2f}"
    if BANCA_ZERADA:
        banca_atual_str += f" (Zerou com {ENTRADAS_AO_ZERAR} entradas)"

    vizinhos_str = ', '.join(map(str, sorted(alvos)))

    mensagem = (
        f"🏆 RELATÓRIO DE RESULTADOS (Trinta Self)\n"
        f"🎰 Mesa: {mesa}\n"
        f"🔗 API: {link_api}\n"
        f"♻️ Últimos 3 números: {', '.join(map(str, ultimos_3))}\n"
        f"🎯 Alvo: {alvo_numero} + 6 vizinhos\n"
        f"🛡️ Vizinhos: {vizinhos_str}\n"
        f"============================ RESULTADO ============================\n"
        f"{msg_status_texto}\n"
        f"============================\n"
        f"\nRESUMO GERAL (Trinta Self - 4 Tentativas):\n"
        f"📈 Total Entradas: {estatisticas['entradas']}\n"
        f"✅ Total Greens: {estatisticas['greens']}\n"
        f"❌ Total Reds: {estatisticas['reds']}\n"
        f"📊 Total Assertividade: {assertividade:.2f}%\n"
        f"💰 Banca Inicial: R${BANCA_INICIAL:.2f}\n"
        f"🏦 Banca atual: {banca_atual_str}\n"
        f"📈 Resultado: R${resultado_liquido:.2f}\n"
        f"============================\n"
        f"\n📊 Estatísticas por Tentativa:\n"
        f"{bloco_estatisticas_financeiro}"
    )

    # Checagem de meta
    if resultado_liquido >= 100:
        hora_meta = datetime.now(FUSO_BRASILIA).strftime("%H:%M")
        META_HISTORICO.append((hora_meta, resultado_liquido))
        resetar_estatisticas()

    # Monta relatório de metas formatado (se houver)
    if META_HISTORICO:
        relatorio_meta = "🎊 RELATÓRIO DE METAS ATINGIDAS 🎉\n"
        relatorio_meta += "==========================\n\n"

        total_acumulado = 0.0
        for idx, (hora, valor) in enumerate(META_HISTORICO, start=1):
            relatorio_meta += f"🎯 Meta {idx}: {hora} - R${valor:.2f} de lucro\n"
            total_acumulado += valor

        relatorio_meta += (
            "\n=========================\n"
            f"💰 TOTAL ACUMULADO: R${total_acumulado:.2f}\n"
            "========================="
        )

        mensagem += f"\n\n{relatorio_meta}"

    # Envia o relatório completo (resultados + metas)
    enviar_telegram(mensagem)

def disparar_sinal_e_monitorar(nome_mesa, alvo_numero, alvos_finais, ultimos_3, ultimo_checado):
    """
    Envia sinal ao Telegram e adiciona ao monitoramento.
    """
    global monitoramento_sinais, sinais_por_hora, total_sinais_dia

    link_api = MESAS_API.get(nome_mesa)
    ficha_minima = FICHAS_MINIMAS.get(nome_mesa, 0)
    
    alvos_str = ', '.join(map(str, sorted(alvos_finais)))
    ultimos_3_str = ', '.join(map(str, ultimos_3))

    mensagem = (
        f"🚨 **TRINTA SELF** 🚨\n"
        f"🎰 Mesa: {nome_mesa}\n"
        f"💰 Ficha mínima: {ficha_minima}\n"
        f"♻️ Gatilho para Jogada: *{ultimos_3_str}*\n"
        f"🎯 **Alvo: {alvo_numero} + 6 vizinhos**\n"
        f"🛡️ Vizinhos: {alvos_str}\n"
        f"⏳ Tentativas: 4 - (1 / 2 / 2,5 / 3,5)\n"
        f"🔗 API: {link_api}"
    )
    enviar_telegram(mensagem)

    hora_brasilia = datetime.now(FUSO_BRASILIA).hour
    sinais_por_hora[hora_brasilia] += 1
    total_sinais_dia += 1

    print(f"[SINAL ENVIADO] Mesa: {nome_mesa} | Alvo: {alvo_numero} + 6 vizinhos")

    monitoramento_sinais.append({
        'mesa': nome_mesa,
        'alvos': alvos_finais,
        'alvo_numero': alvo_numero,
        'ultimos_3': ultimos_3,
        'tentativas': 0,
        'ultimo_numero_checado': ultimo_checado,
        'link_api': link_api,
    })

# --- FUNÇÕES DE PROCESSAMENTO ---
def extrair_numeros(json_data):
    """Extrai uma lista de números inteiros."""
    try:
        if isinstance(json_data, str):
            return [int(n) for n in re.findall(r'\d+', json_data)]
        elif isinstance(json_data, list):
            return [int(n) for n in json_data if isinstance(n, int)]
        elif isinstance(json_data, dict):
            for chave in ["results", "data", "lastNumbers"]:
                if chave in json_data and isinstance(json_data[chave], list):
                    return [int(n) for n in json_data[chave] if isinstance(n, int)]
            for v in json_data.values():
                if isinstance(v, list) and all(isinstance(n, int) for n in v):
                    return v
        return []
    except Exception as e:
        print(f"[ERRO] Falha ao extrair números: {e}")
        return []

def processar_resultados(provedor, nome_mesa, numeros_recentes):
    """
    Implementa a lógica do padrão Trinta Self.
    """
    global monitoramento_sinais

    if len(numeros_recentes) < 3:
        return

    mesa_key = f"{provedor}:{nome_mesa}"

    # Atualização do histórico
    if len(history[mesa_key]) == 0 or numeros_recentes[0] != history[mesa_key][0]:
        novos_numeros_a_adicionar = []
        for num in numeros_recentes:
            if history[mesa_key] and num == history[mesa_key][0] and len(novos_numeros_a_adicionar) == 0:
                break
            novos_numeros_a_adicionar.append(num)

        for num in reversed(novos_numeros_a_adicionar):
            history[mesa_key].appendleft(num)

    numeros_historico = list(history[mesa_key])

    if len(numeros_historico) < 3:
        return

    # Regra: Um sinal por mesa por vez
    sinal_ativo_na_mesa = any(s['mesa'] == nome_mesa for s in monitoramento_sinais)

    if not sinal_ativo_na_mesa:
        num0 = numeros_historico[0]

        # Gatilho: Se N0 está nos números dos trinta (30-36)
        if num0 in NUMEROS_TRINTA:
            alvo_numero = num0
            alvos_finais_set = get_alvos_roleta(alvo_numero, 6)
            alvos_finais = sorted(list(alvos_finais_set))

            # Pega os últimos 3 números para exibição
            ultimos_3 = numeros_historico[:3]

            print(f"[PADRÃO TRINTA SELF] Mesa: {nome_mesa} | Gatilho: {num0} | Alvo: {alvo_numero} + 6 vizinhos")

            disparar_sinal_e_monitorar(
                nome_mesa,
                alvo_numero,
                alvos_finais,
                ultimos_3,
                num0
            )

# --- MONITORAMENTO DE SINAIS ---
def monitorar_sinais_ativos():
    """Verifica os sinais ativos para Green/Red."""
    global monitoramento_sinais, BANCA_ATUAL, BANCA_ZERADA, ENTRADAS_AO_ZERAR, TOTAL_LUCRO_GREEN, TOTAL_PERDA_RED
    sinais_para_remover = []

    for dados_sinal in list(monitoramento_sinais):
        nome_mesa = dados_sinal['mesa']
        api_url = MESAS_API.get(nome_mesa)
        if not api_url:
            continue

        try:
            resp = requests.get(api_url, timeout=20)
            if resp.status_code == 200:
                numeros = extrair_numeros(resp.json())

                if not numeros or numeros[0] == dados_sinal['ultimo_numero_checado']:
                    continue

                novos = []
                for n in numeros:
                    if n == dados_sinal['ultimo_numero_checado']:
                        break
                    novos.append(n)

                for novo_num in reversed(novos):
                    dados_sinal['tentativas'] += 1
                    max_tentativas = 4
                    resultado_final = None
                    alvo_numero = dados_sinal['alvo_numero']

                    if dados_sinal['tentativas'] <= max_tentativas:
                        print(f"[MONITOR] Mesa: {nome_mesa} - Tentativa {dados_sinal['tentativas']}/4 - Alvo: {alvo_numero} - Sorteado: {novo_num}")

                    # Checagem Green
                    if dados_sinal['tentativas'] <= max_tentativas and novo_num in dados_sinal['alvos']:
                        resultado_final = 'Green'
                        print(f"✅ GREEN - Mesa {nome_mesa} - Sorteado: {novo_num}")

                    # Checagem Red
                    elif dados_sinal['tentativas'] >= max_tentativas:
                        resultado_final = 'Red'
                        print(f"❌ RED - Mesa {nome_mesa} - Tentativas excedidas")

                    if resultado_final:
                        estatisticas['entradas'] += 1

                        if resultado_final == 'Green':
                            tentativa_vitoria = dados_sinal['tentativas']
                            estatisticas['greens'] += 1
                            estatisticas['greens_por_tentativa'][tentativa_vitoria] += 1

                            if not BANCA_ZERADA:
                                lucro = GREEN_VALUES_POR_TENTATIVA.get(tentativa_vitoria, 0.0)
                                BANCA_ATUAL += lucro
                                TOTAL_LUCRO_GREEN += lucro
                                print(f"[FINANCEIRO] GREEN: +R${lucro:.2f} | Nova Banca: R${BANCA_ATUAL:.2f}")

                            enviar_relatorio(dados_sinal, 'Green', tentativa_vitoria, 4, novo_num)

                        elif resultado_final == 'Red':
                            estatisticas['reds'] += 1
                            estatisticas['reds_total'] += 1

                            if not BANCA_ZERADA:
                                perda = RED_VALUE
                                BANCA_ATUAL -= perda
                                TOTAL_PERDA_RED += perda
                                print(f"[FINANCEIRO] RED: -R${perda:.2f} | Nova Banca: R${BANCA_ATUAL:.2f}")

                                # NOVO: Checagem de zeramento com parada total
                                if BANCA_ATUAL <= 0.0:
                                    BANCA_ATUAL = 0.0
                                    BANCA_ZERADA = True
                                    ENTRADAS_AO_ZERAR = estatisticas['entradas']
                                    
                                    # Mensagem de alerta crítico
                                    mensagem_zerou = (
                                        "🚨🚨🚨 ALERTA CRÍTICO 🚨🚨🚨\n"
                                        "============================\n"
                                        "💥 BANCA ZERADA! 💥\n"
                                        "============================\n\n"
                                        f"📊 Total de entradas até zerar: {ENTRADAS_AO_ZERAR}\n"
                                        f"💰 Banca inicial: R${BANCA_INICIAL:.2f}\n"
                                        f"📉 Prejuízo total: R${TOTAL_PERDA_RED - TOTAL_LUCRO_GREEN:.2f}\n\n"
                                        "🛑 BOT PAUSADO AUTOMATICAMENTE!\n"
                                        "Reinicie manualmente para continuar operando."
                                    )
                                    enviar_telegram(mensagem_zerou)
                                    
                                    print("\n" + "="*80)
                                    print("🚨 BANCA ZERADA! BOT PAUSADO!")
                                    print(f"Total de entradas até zerar: {ENTRADAS_AO_ZERAR}")
                                    print(f"Prejuízo total: R${TOTAL_PERDA_RED - TOTAL_LUCRO_GREEN:.2f}")
                                    print("="*80 + "\n")
                                    
                                    # PARA O BOT COMPLETAMENTE
                                    exit(0)

                            enviar_relatorio(dados_sinal, 'Red', max_tentativas=4)

                        sinais_para_remover.append(dados_sinal)
                        break

                    if numeros:
                        dados_sinal['ultimo_numero_checado'] = numeros[0]

        except requests.exceptions.RequestException as e:
            print(f"[ERRO] Falha ao monitorar mesa {nome_mesa}: {e}")
            continue

    for s in sinais_para_remover:
        if s in monitoramento_sinais:
            monitoramento_sinais.remove(s)

# --- SETUP INICIAL ---
def setup_initial_history():
    """Popula o histórico inicial."""
    print("[SETUP] Carregando histórico inicial...")

    headers = {"User-Agent": "Mozilla/5.0"}

    for nome_mesa, api_url in MESAS_API.items():
        provedor = MESAS_PROVEDORES.get(nome_mesa, "Desconhecido")
        mesa_key = f"{provedor}:{nome_mesa}"

        try:
            resp = requests.get(api_url, headers=headers, timeout=20)
            if resp.status_code == 200:
                numeros = extrair_numeros(resp.json())

                if numeros:
                    history[mesa_key].extend(numeros[:500])
                    print(f"[SETUP] Mesa {nome_mesa}: {len(history[mesa_key])} números carregados.")
        except requests.exceptions.RequestException as e:
            print(f"[SETUP] Erro com {nome_mesa}: {e}")

# --- LOOP PRINCIPAL ---
keep_alive()
setup_initial_history()

print("[🤖 BOT INICIADO] Padrão Trinta Self - Monitorando...")
enviar_telegram("🤖 Bot Trinta Self iniciado! Monitoramento ativo.")

while True:
    headers = {"User-Agent": "Mozilla/5.0"}
    bloqueados_upper = [p.upper() for p in PROVEDORES_BLOQUEADOS]
    
    for nome_mesa, api_url in MESAS_API.items():
        provedor = MESAS_PROVEDORES.get(nome_mesa, "Desconhecido")
        if provedor.upper() in bloqueados_upper:
            continue
            
        try:
            resp = requests.get(api_url, headers=headers, timeout=20)
            if resp.status_code == 200:
                numeros = extrair_numeros(resp.json())
                if not numeros:
                    continue
                    
                print(f"[UPDATE] Mesa: {nome_mesa} - Últimos: {numeros[:10]}")
                processar_resultados(provedor, nome_mesa, numeros)
        except requests.exceptions.RequestException as e:
            print(f"[ERRO] Mesa {nome_mesa}: {e}")
            continue

    monitorar_sinais_ativos()

    # Relatórios horários
    agora = datetime.now(FUSO_BRASILIA)

    if agora.minute == 0 and agora.hour != ultima_hora:
        hora_atual = agora.hour
        hora_passada = (hora_atual - 1 + 24) % 24

        enviados_na_hora = sinais_por_hora.get(hora_passada, 0)
        msg_linha_report = f"Das {hora_passada:02d}h as {hora_atual:02d}h: {enviados_na_hora} Sinais"
        relatorio_diario_por_hora.append(msg_linha_report)

        relatorio_por_hora_formatado = '\n'.join(relatorio_diario_por_hora)
        mensagem_final_relatorio = (
            f"📈 **RELATÓRIO DE SINAIS ENVIADOS (Ciclo 22h - 22h)**\n"
            f"--- SINAIS POR HORA ---\n"
            f"{relatorio_por_hora_formatado}"
        )
        enviar_telegram(mensagem_final_relatorio, parse_mode='Markdown')

        print(f"[RELATÓRIO HORÁRIO] {msg_linha_report}")

        sinais_por_hora[hora_atual] = 0

        if hora_atual == 22:
            relatorio_diario_por_hora = []
            print("[RELATÓRIO] Ciclo 22h-22h resetado.")

        ultima_hora = agora.hour

    time.sleep(INTERVALO)
