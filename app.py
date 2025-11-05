import os
import sqlite3
import requests
import time
from flask import Flask
import threading

app = Flask(__name__)

class SimpleTradingBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.init_db()
        self.last_update_id = 0
    
    def init_db(self):
        conn = sqlite3.connect('/tmp/trades.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS trades
                     (id INTEGER PRIMARY KEY, symbol TEXT, entry_price REAL, 
                      size REAL, strategy TEXT, status TEXT DEFAULT 'open',
                      exit_price REAL, pnl REAL)''')
        conn.commit()
        conn.close()
        print("✅ Database initialized")
    
    def send_message(self, chat_id, text):
        try:
            url = f"{self.base_url}/sendMessage"
            data = {"chat_id": chat_id, "text": text}
            response = requests.post(url, json=data)
            return response.status_code == 200
        except:
            return False
    
    def get_updates(self):
        try:
            url = f"{self.base_url}/getUpdates"
            params = {"offset": self.last_update_id + 1, "timeout": 30}
            response = requests.get(url, params=params)
            return response.json().get("result", [])
        except:
            return []
    
    def handle_message(self, message):
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
        print(f"📨 Received: {text}")
        
        if text == "/start":
            self.send_message(chat_id, 
                "📗 FREE Trading Journal Bot\n\n"
                "Commands:\n"
                "/add SYMBOL PRICE SIZE STRATEGY\n"
                "/view - Show recent trades\n"
                "/close SYMBOL EXIT_PRICE\n"
                "/stats - Performance stats\n\n"
                "Examples:\n"
                "/add BTC 35000 0.1 swing\n"
                "/close BTC 36000\n"
                "/view\n"
                "/stats")
        
        elif text.startswith("/add"):
            parts = text.split()
            if len(parts) != 5:
                self.send_message(chat_id, "❌ Use: /add SYMBOL PRICE SIZE STRATEGY\nExample: /add BTC 35000 0.1 swing")
                return
            
            _, symbol, price, size, strategy = parts
            try:
                conn = sqlite3.connect('/tmp/trades.db')
                c = conn.cursor()
                c.execute("INSERT INTO trades (symbol, entry_price, size, strategy) VALUES (?, ?, ?, ?)",
                         (symbol.upper(), float(price), float(size), strategy))
                conn.commit()
                conn.close()
                self.send_message(chat_id, f"✅ Trade added:\n{symbol.upper()} @ ${price}\nSize: {size}\nStrategy: {strategy}")
            except Exception as e:
                self.send_message(chat_id, f"❌ Error: {str(e)}")
        
        elif text == "/view":
            conn = sqlite3.connect('/tmp/trades.db')
            c = conn.cursor()
            c.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 10")
            trades = c.fetchall()
            conn.close()
            
            if not trades:
                self.send_message(chat_id, "📭 No trades found")
                return
            
            response = "📋 Recent Trades:\n\n"
            for trade in trades:
                id, symbol, entry, size, strategy, status, exit_price, pnl = trade
                response += f"#{id} {symbol}: ${entry} x {size}\n"
                response += f"  Strategy: {strategy} - {status}\n"
                if status == 'closed':
                    response += f"  Exit: ${exit_price} | PnL: ${pnl:.2f}\n"
                response += "\n"
            
            self.send_message(chat_id, response)
        
        elif text.startswith("/close"):
            parts = text.split()
            if len(parts) != 3:
                self.send_message(chat_id, "❌ Use: /close SYMBOL EXIT_PRICE\nExample: /close BTC 36000")
                return
            
            _, symbol, exit_price = parts
            try:
                conn = sqlite3.connect('/tmp/trades.db')
                c = conn.cursor()
                c.execute("SELECT id, entry_price, size FROM trades WHERE symbol=? AND status='open' ORDER BY id DESC LIMIT 1", 
                         (symbol.upper(),))
                trade = c.fetchone()
                
                if trade:
                    trade_id, entry_price, size = trade
                    pnl = (float(exit_price) - entry_price) * size
                    c.execute("UPDATE trades SET status='closed', exit_price=?, pnl=? WHERE id=?", 
                             (float(exit_price), pnl, trade_id))
                    conn.commit()
                    self.send_message(chat_id, f"✅ Trade closed:\n{symbol.upper()} @ ${exit_price}\nPnL: ${pnl:.2f}")
                else:
                    self.send_message(chat_id, f"❌ No open trade found for {symbol.upper()}")
                conn.close()
            except Exception as e:
                self.send_message(chat_id, f"❌ Error: {str(e)}")
        
        elif text == "/stats":
            conn = sqlite3.connect('/tmp/trades.db')
            c = conn.cursor()
            
            c.execute("SELECT COUNT(*), SUM(pnl) FROM trades WHERE status='closed'")
            total_trades, total_pnl = c.fetchone()
            total_pnl = total_pnl or 0
            
            c.execute("SELECT COUNT(*) FROM trades WHERE status='closed' AND pnl > 0")
            winning_trades = c.fetchone()[0]
            
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            conn.close()
            
            response = f"📊 Trading Stats:\n\n"
            response += f"Total Trades: {total_trades}\n"
            response += f"Win Rate: {win_rate:.1f}%\n"
            response += f"Total PnL: ${total_pnl:.2f}\n"
            if total_trades > 0:
                response += f"Avg PnL: ${total_pnl/total_trades:.2f}"
            
            self.send_message(chat_id, response)
        
        else:
            self.send_message(chat_id, "❌ Unknown command. Use /start for help.")
    
    def run(self):
        print("🚀 Trading Bot Started...")
        while True:
            try:
                updates = self.get_updates()
                for update in updates:
                    self.last_update_id = update["update_id"]
                    if "message" in update:
                        self.handle_message(update["message"])
                time.sleep(1)
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(5)

@app.route('/')
def home():
    return "🤖 Trading Bot is running!"

@app.route('/health')
def health():
    return "OK"

def start_bot():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("❌ ERROR: Please set BOT_TOKEN environment variable")
        return
    
    bot = SimpleTradingBot(token)
    bot.run()

# Start bot when app starts
bot_thread = threading.Thread(target=start_bot)
bot_thread.daemon = True
bot_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
