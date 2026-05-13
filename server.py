import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ТВОЙ РАБОЧИЙ КЛЮЧ (через который сервер будет тянуть данные)
MASTER_KEY = "ТВОЙ_ЛИЧНЫЙ_MARKET_KEY" 
# Список ключей твоих "клиентов"
VALID_CLIENT_KEYS = ["AMM-91E52E7C-4A5F", "ADMIN_KEY"]

def get_data_from_arz(path, server_id=None):
    # Формируем запрос к реальному API
    url = f"https://api.arz.market/api/{path}/"
    if server_id:
        url += str(server_id)
    
    headers = {"authKey": MASTER_KEY}
    try:
        # Тянем данные с реального сайта
        resp = requests.get(url, headers=headers, timeout=5)
        return resp.json()
    except:
        return []

@app.route('/api/selectMarketplace/', defaults={'server_id': 0}, methods=['GET', 'POST'])
@app.route('/api/selectMarketplace/<server_id>', methods=['GET', 'POST'])
@app.route('/api/getSelectedMarketplace/<server_id>', methods=['GET'])
def handle_all(server_id):
    # Проверка ключа (из заголовков или параметров)
    key = request.headers.get("authKey") or request.args.get("authKey")
    
    if key not in VALID_CLIENT_KEYS:
        return jsonify({"error": "No access"}), 403

    # Определяем, какой API вызвал бот
    path = "selectMarketplace" if "selectMarketplace" in request.path else "getSelectedMarketplace"
    
    # Получаем реальные данные и отдаем боту
    data = get_data_from_arz(path, server_id)
    return jsonify(data)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
