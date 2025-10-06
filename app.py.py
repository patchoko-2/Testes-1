# app.py
# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify

# Cria uma instância da aplicação Flask.
app = Flask(__name__)

# Define a rota padrão ('/') da sua aplicação.
@app.route('/')
def index():
    return "<h1>Olá, Flask! Seu bot está rodando no Render.</h1>"

# Define uma rota para uma página de saudação.
@app.route('/saudar/<nome>')
def saudar_usuario(nome):
    return f"<h1>Olá, {nome}! Bem-vindo à sua aplicação Flask.</h1>"

# Define uma rota para processar dados via POST.
@app.route('/processar_dados', methods=['POST'])
def processar_dados():
    dados_recebidos = request.get_json()
    nome = dados_recebidos.get('nome')
    idade = dados_recebidos.get('idade')
    
    if nome and idade:
        mensagem = f"Dados recebidos com sucesso! Nome: {nome}, Idade: {idade}."
        return jsonify({"status": "sucesso", "mensagem": mensagem})
    else:
        return jsonify({"status": "erro", "mensagem": "Dados inválidos."}), 400

# Este bloco só é executado se o script for rodado localmente
if __name__ == '__main__':
    # O host '0.0.0.0' é importante para que o servidor seja acessível
    # a partir de qualquer endereço IP, o que é útil em ambientes como o Render.
    app.run(host='0.0.0.0', debug=True)

```text
# requirements.txt
# Lista de todas as bibliotecas que sua aplicação Flask precisa.
# O Render vai usar este arquivo para instalá-las.
Flask
gunicorn
```text
# start.sh
# Render usa este script para iniciar sua aplicação.
# A variável de ambiente $PORT é fornecida automaticamente pelo Render.
gunicorn --bind 0.0.0.0:$PORT app:app

# Explicação do comando gunicorn:
# gunicorn: É um servidor de produção que o Render usa para rodar aplicações Python.
# --bind 0.0.0.0:$PORT: Diz ao gunicorn para ouvir em todos os endereços de rede, na porta que o Render fornecer.
# app:app: O primeiro 'app' é o nome do seu arquivo Python (app.py). O segundo 'app' é a variável
#          da sua aplicação Flask dentro desse arquivo (app = Flask(__name__)).
