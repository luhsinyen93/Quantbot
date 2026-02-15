"""QuantBot Web API"""

from flask import Flask, jsonify, render_template_string
from datetime import datetime
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QuantBot 控制面板</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0d1117; color: #c9d1d9; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid #30363d; margin-bottom: 30px; }
        h1 { color: #58a6ff; font-size: 24px; }
        .status-badge { padding: 6px 16px; border-radius: 20px; font-size: 14px; font-weight: 600; }
        .status-running { background: #238636; color: #fff; }
        .status-stopped { background: #da3633; color: #fff; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 30px; }
        .stat-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }
        .stat-label { color: #8b949e; font-size: 14px; margin-bottom: 8px; }
        .stat-value { font-size: 28px; font-weight: 700; }
        .stat-value.positive { color: #3fb950; }
        .stat-value.negative { color: #f85149; }
        .section { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        .section-title { font-size: 18px; font-weight: 600; margin-bottom: 16px; color: #58a6ff; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #30363d; }
        th { color: #8b949e; font-weight: 500; font-size: 14px; }
        .trade-buy { color: #3fb950; }
        .trade-sell { color: #f85149; }
        .btn { padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-size: 14px; font-weight: 600; }
        .btn-primary { background: #238636; color: #fff; }
        .btn-danger { background: #da3633; color: #fff; }
        .logs { background: #0d1117; border-radius: 8px; padding: 16px; max-height: 300px; overflow-y: auto; font-family: monospace; font-size: 12px; }
        .log-entry { margin-bottom: 4px; }
        .log-time { color: #8b949e; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 QuantBot 控制面板</h1>
            <span class="status-badge {{ 'status-running' if status.running else 'status-stopped' }}">
                {{ '運行中' if status.running else '已停止' }}
            </span>
        </header>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">總交易次數</div>
                <div class="stat-value">{{ status.total_trades }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">勝率</div>
                <div class="stat-value">{{ "%.1f"|format(status.win_rate * 100) }}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">總盈虧</div>
                <div class="stat-value {{ 'positive' if status.total_pnl > 0 else 'negative' }}">
                    {{ "%.2f"|format(status.total_pnl) }} USDT
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-label">當前持倉</div>
                <div class="stat-value">{{ status.positions }}</div>
            </div>
        </div>
        <div class="section">
        <div class="section-title">⚡ 控制</div>
            <button class="btn btn-primary" onclick="location.reload()">🔄 刷新</button>
        </div>
        <div class="section">
            <div class="section-title">📊 最近交易</div>
            <table>
                <thead><tr><th>時間</th><th>交易對</th><th>方向</th><th>價格</th><th>盈虧</th></tr></thead>
                <tbody>
                    {% for trade in trades %}
                    <tr>
                        <td>{{ trade.time }}</td>
                        <td>{{ trade.symbol }}</td>
                        <td class="{{ 'trade-buy' if trade.side == 'buy' else 'trade-sell' }}">{{ '買入' if trade.side == 'buy' else '賣出' }}</td>
                        <td>{{ "%.4f"|format(trade.price) }}</td>
                        <td class="{{ 'trade-buy' if trade.pnl > 0 else 'trade-sell' }}">{{ "%.2f"|format(trade.pnl) }}</td>
                    </tr>
                    {% else %}
                    <tr><td colspan="5" style="text-align: center; color: #8b949e;">暫無交易記錄</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

_bot_instance = None
_app_logs = []

def init_app(bot_instance):
    global _bot_instance
    _bot_instance = bot_instance

def add_log(message: str, level: str = "info"):
    global _app_logs
    _app_logs.append({'time': datetime.now().strftime('%H:%M:%S'), 'message': message, 'level': level})
    _app_logs = _app_logs[-100:]

@app.route('/')
def index():
    status = {'running': False, 'total_trades': 0, 'win_rate': 0, 'total_pnl': 0, 'positions': 0}
    trades = []
    if _bot_instance:
        try:
            status = _bot_instance.get_status()
            if hasattr(_bot_instance, 'smart_trader'):
                for t in _bot_instance.smart_trader.get_trade_history(10):
                    trades.append({'time': t.exit_time.strftime('%H:%M:%S') if t.exit_time else '-', 'symbol': t.symbol, 'side': t.side, 'price': t.entry_price, 'pnl': t.pnl})
        except: pass
    return render_template_string(HTML_TEMPLATE, status=status, trades=trades)

@app.route('/api/status')
def api_status():
    return jsonify(_bot_instance.get_status() if _bot_instance else {'error': 'Bot not running'})

def run_server(host: str = '0.0.0.0', port: int = 5000):
    add_log(f"Web 服務器啟動: http://{host}:{port}", "info")
    app.run(host=host, port=port, debug=False)