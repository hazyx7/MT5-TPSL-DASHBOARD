import subprocess
import sys

def install_and_import(package):
    try:
        __import__(package)
    except ImportError:
        print(f"Installing missing package: {package}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        __import__(package)

# Ensure required packages are installed
install_and_import("MetaTrader5")
install_and_import("msvcrt")  # On Windows, this is a built-in module and won't install


import os
import sys
import time
import msvcrt
import MetaTrader5 as mt5
from datetime import datetime

# Terminal colors
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
WHITE = "\033[97m"
BLUE = "\033[94m"
YELLOW = "\033[93m"

# Globals
SHOW_DETAILS = False
IN_TP_SL_MODE = False
REFRESH_DELAY = 0.01  # Faster for summary view

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def color(val):
    if val > 0: return GREEN
    elif val < 0: return RED
    else: return WHITE

def print_loading():
    print("Connecting to MetaTrader 5\n[", end="", flush=True)
    for _ in range(10):
        print("█", end="", flush=True)
        time.sleep(0.05)
    print("] Connected!")
    time.sleep(0.3)
    clear_screen()

def get_trade_data():
    positions = mt5.positions_get()
    account = mt5.account_info()
    balance = account.balance if account else 0.0

    total_pnl = 0.0
    return positions or [], total_pnl, balance

def print_summary(positions, total_pnl, balance):
    print("\n====== SUMMARY ======\n")
    buy, sell, total_tp, total_sl, cur_pl = 0, 0, 0.0, 0.0, 0.0

    for pos in positions:
        info = mt5.symbol_info(pos.symbol)
        if not info: continue
        pt, tv = info.point, info.trade_tick_value
        op, tp, sl, vol, typ = pos.price_open, pos.tp, pos.sl, pos.volume, pos.type

        cur_pl += pos.profit
        if typ == mt5.ORDER_TYPE_BUY: buy += 1
        else: sell += 1

        if tp > 0:
            dist = abs(tp - op) / pt
            val = dist * tv * vol
            if (typ == mt5.ORDER_TYPE_BUY and tp < op) or (typ == mt5.ORDER_TYPE_SELL and tp > op):
                val *= -1
            total_tp += val

        if sl > 0:
            dist = abs(sl - op) / pt
            val = dist * tv * vol * -1
            total_sl += val

    risk_pct = abs(total_sl / balance * 100) if balance else 0

    print(f"Trades Summary     : BUY = {buy}   | SELL = {sell}")
    print(f"{color(cur_pl)}Total Current P&L : ${cur_pl:.2f}{RESET}")
    print(f"{GREEN}TP Target         : ${total_tp:.2f}{RESET}")
    print(f"{RED}SL Risk           : ${total_sl:.2f}{RESET}")
    print(f"Risk on Account   : {risk_pct:.2f}%")
    print(f"Account Balance   : ${balance:.2f}")
    print("\nTAB = Toggle Summary/Details | ENTER = Set TP/SL | ESC = Exit")

def print_details(positions):
    print("\n====== DETAILS ======\n")
    if not positions:
        print("No open trades.")
        return

    for pos in positions:
        info = mt5.symbol_info(pos.symbol)
        if not info: continue
        pt = info.point
        sym, vol, typ = pos.symbol, pos.volume, pos.type
        op, tp, sl = pos.price_open, pos.tp, pos.sl
        trade_type = "BUY" if typ == mt5.ORDER_TYPE_BUY else "SELL"

        print(f"{sym} | {trade_type} | Volume: {vol:.2f}")

        if tp > 0:
            print(f"TP Price          : {tp:.2f}")
        else:
            print("TP Price          : Not Set")

        if sl > 0:
            print(f"SL Price          : {sl:.2f}")
        else:
            print("SL Price          : Not Set")

        if tp > 0 and sl > 0:
            rr = abs(tp - op) / abs(sl - op)
            print(f"R/R Ratio         : {rr:.2f}")
        print()
    print("\nTAB = Toggle Summary/Details | ESC = Exit")

def show_tp_sl_setter(positions):
    global IN_TP_SL_MODE
    
    IN_TP_SL_MODE = True
    clear_screen()
    
    print(f"{BLUE}╔══════════════════════════════════════════════╗")
    print(f"║{' ' * 20}TP/SL SETTER{' ' * 20}║")
    print(f"╚══════════════════════════════════════════════╝{RESET}\n")
    
    print(f"Found {len(positions)} open trade(s):\n")
    for i, pos in enumerate(positions, start=1):
        direction = "BUY " if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        print(f" {i}. {pos.symbol} | {direction} | Volume: {pos.volume:.2f} | Open: {pos.price_open:.5f} | TP: {pos.tp:.5f} | SL: {pos.sl:.5f}")
    
    print(f"\n{YELLOW}Enter TP/SL values (0 to skip){RESET}")
    try:
        tp = float(input("TP Price: "))
        sl = float(input("SL Price: "))
        tp = None if tp == 0 else tp
        sl = None if sl == 0 else sl
        
        print("\nApplying TP/SL to all positions...\n")
        time.sleep(0.5)
        
        for pos in positions:
            already_tp = (tp is None or (pos.tp > 0 and abs(pos.tp - tp) < 0.00001))
            already_sl = (sl is None or (pos.sl > 0 and abs(pos.sl - sl) < 0.00001))

            if already_tp and already_sl:
                print(f"{pos.symbol} → Already Set.")
                continue

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": pos.ticket,
                "tp": tp,
                "sl": sl,
                "symbol": pos.symbol,
                "magic": 234000,
                "comment": "Bulk TP/SL Setter",
            }

            result = mt5.order_send(request)

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"{pos.symbol} → Updated.")
            elif result.retcode == 10027:
                print("\nAutoTrading is disabled in MT5.")
                input("Enable AutoTrading and press Enter to retry...")
                return show_tp_sl_setter(positions)
            elif result.retcode == 10025 and already_tp and already_sl:
                print(f"{pos.symbol} → Already Set.")
            else:
                print(f"✗ {pos.symbol} FAILED | RetCode: {result.retcode}")

            time.sleep(0.2)

        print(f"\n{GREEN}╔══════════════════════════════╗")
        print(f"║{' ' * 8}UPDATE COMPLETE{' ' * 8}║")
        print(f"╚══════════════════════════════╝{RESET}")
        input("\nPress Enter to return to summary...")
        
    except ValueError:
        print(f"{RED}Invalid input. Please enter valid numbers.{RESET}")
        time.sleep(1)
        show_tp_sl_setter(positions)
    
    IN_TP_SL_MODE = False

def run_loop():
    global SHOW_DETAILS, IN_TP_SL_MODE
    print_loading()

    while True:
        if not IN_TP_SL_MODE:
            clear_screen()
            positions, pnl_total, balance = get_trade_data()

            if SHOW_DETAILS:
                print_details(positions)
                while True:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b'\t':  # TAB key
                            SHOW_DETAILS = False
                            break
                        elif key == b'\x1b':  # ESC key
                            mt5.shutdown()
                            sys.exit()
                    time.sleep(0.05)
            else:
                print_summary(positions, pnl_total, balance)
                for _ in range(int(1 / REFRESH_DELAY)):
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b'\t':  # TAB key
                            SHOW_DETAILS = True
                            break
                        elif key == b'\r':  # ENTER key
                            show_tp_sl_setter(positions)
                            break
                        elif key == b'\x1b':  # ESC key
                            mt5.shutdown()
                            sys.exit()
                    time.sleep(REFRESH_DELAY)
        else:
            time.sleep(0.1)

# Initialize and run
if not mt5.initialize():
    clear_screen()
    print(f"{RED}❌ Failed to connect to MetaTrader 5.{RESET}")
    print("Make sure MT5 is running and logged in.")
    input("Press Enter to exit...")
    sys.exit()
else:
    try:
        run_loop()
    except Exception as e:
        print(f"{RED}Unexpected error: {e}{RESET}")
        input("Press Enter to exit...")
    finally:
        mt5.shutdown()