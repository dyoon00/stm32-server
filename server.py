from flask import Flask, request, jsonify

app = Flask(__name__)

received_data = []

@app.route('/', methods=['GET'])
def index():
    rows = ""
    for d in reversed(received_data):
        rows += f"<tr><td>{d.get('timestamp','')}</td><td><pre>{d.get('raw','')}</pre></td></tr>"
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>STM32 서버</title>
        <meta charset="utf-8">
        <meta http-equiv="refresh" content="3">
        <style>
            body {{ font-family: Arial; padding: 20px; background: #f0f0f0; }}
            h1 {{ color: #333; }}
            table {{ width: 100%; border-collapse: collapse; background: white; }}
            th, td {{ padding: 10px; border: 1px solid #ddd; text-align: left; }}
            th {{ background: #4CAF50; color: white; }}
            pre {{ margin: 0; }}
        </style>
    </head>
    <body>
        <h1>STM32 수신 데이터</h1>
        <p>3초마다 자동 새로고침</p>
        <table>
            <tr><th>시간</th><th>데이터</th></tr>
            {rows if rows else "<tr><td colspan='2'>수신된 데이터 없음</td></tr>"}
        </table>
    </body>
    </html>
    """

@app.route('/data', methods=['POST'])
def receive_data():
    import json
    from datetime import datetime
    data = request.get_json()
    received_data.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw": json.dumps(data, ensure_ascii=False, indent=2)
    })
    print("STM32 수신:", data)
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
