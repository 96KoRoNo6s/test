import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Твой личный список "валидных" токенов (кому ты разрешил пользоваться ботом)
ALLOWED_TOKENS = ["USER_1_TOKEN", "MY_FRIEND_KEY", "ADMIN_1337"]

# Реальный адрес API рынка
REAL_MARKET_API = "https://api.arz.market/api/selectMarketplace/"

@app.route('/')
def home():
    return "Server is running. Monitoring active."

@app.route('/api/selectMarketplace/<server_id>', methods=['GET', 'POST'])
def proxy_market(server_id):
    # 1. Достаем токен, который прислал бот
    user_token = request.headers.get("authKey") or request.args.get("authKey")
    
    # 2. ПРОВЕРКА: Если токена нет в нашем списке — шлем лесом
    if user_token not in ALLOWED_TOKENS:
        print(f"DEBUG: Попытка взлома или левый ключ: {user_token}")
        return jsonify({"error": "License expired or invalid key"}), 403

    # 3. ПРОКСИРОВАНИЕ: Если ключ верный, идем на настоящий рынок
    # Мы используем СВОЙ системный ключ для запроса к оригиналу
    system_auth_key = "ТВОЙ_ЛИЧНЫЙ_РАБОЧИЙ_MARKET_KEY" 
    
    try:
        # Пересылаем запрос на оригинальный API
        response = requests.get(
            f"{REAL_MARKET_API}{server_id}",
            headers={"authKey": system_auth_key},
            timeout=10
        )
        # Возвращаем данные боту так, будто это ответил оригинал
        return (response.text, response.status_code, response.headers.items())
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

if __name__ == "__main__":
    # Render сам назначит порт через переменную окружения
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
