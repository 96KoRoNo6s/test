from flask import Flask, jsonify, request

app = Flask(__name__)

# Имитируем базу данных разрешенных ключей
VALID_KEYS = ["SUPER_SECRET_TOKEN_123", "ADMIN_KEY"]

@app.route('/api/selectMarketplace/<server_id>', methods=['GET', 'POST'])
def mock_market(server_id):
    # Проверяем токен, который прислал бот
    auth_key = request.headers.get("authKey") or request.args.get("authKey")
    
    if auth_key not in VALID_KEYS:
        return jsonify({"error": "Invalid License"}), 403

    # Если ключ верный, отдаем реальные данные (или свои)
    # Тут должна быть логика: твой сервер идет на настоящий arz.market, 
    # забирает данные и отдает их клиенту.
    return jsonify({
        "status": "ok",
        "server": server_id,
        "data": [
            {"LavkaUid": "1", "items_sell": ["456"], "price_sell": [1000], "count_sell": [5]}
        ]
    })

if __name__ == '__main__':
    app.run(port=5000)
