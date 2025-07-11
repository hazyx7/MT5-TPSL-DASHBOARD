import os
import sys
import time
import subprocess
import msvcrt
from datetime import datetime

# Terminal colors
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
WHITE = "\033[97m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
GRAY = "\033[90m"
LIGHT_GRAY = "\033[37m"

# Auto-install MetaTrader5
try:
    import MetaTrader5 as mt5
except ImportError:
    print("Installing MetaTrader5...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "MetaTrader5"])
    import MetaTrader5 as mt5

# Globals
SHOW_DETAILS = False
IN_TP_SL_MODE = False
REFRESH_DELAY = 0.01

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def set_terminal_size():
    if os.name == "nt":
        os.system("mode con: cols=100 lines=30")
    else:
        sys.stdout.write("\x1b[8;30;100t")

def loading_bar(message, steps=24, delay=0.02):
    print(f"{WHITE}{message}{RESET}")
    print("[", end="", flush=True)
    for i in range(steps):
        if i < steps // 3:
            color = GRAY
        elif i < (2 * steps) // 3:
            color = LIGHT_GRAY
        else:
            color = WHITE
        print(f"{color}█{RESET}", end="", flush=True)
        time.sleep(delay)
    print(f"] {WHITE}Done!{RESET}\n")

def startup_check():
    clear_screen()
    set_terminal_size()

    loading_bar("Checking required Pip packages...")

    print(f"{WHITE}Checking MetaTrader 5 connection...{RESET}")
    if not mt5.initialize():
        print(f"{RED}❌ MT5 not running or failed to connect.{RESET}")
        input("Please open MT5 and press Enter to retry...")
        return startup_check()
    loading_bar("")

    print(f"{WHITE}Checking AutoTrading status...{RESET}")
    account = mt5.account_info()
    if account is None or not account.trade_allowed:
        print(f"{RED}❌ AutoTrading is disabled.{RESET}")
        input("Please enable AutoTrading and press Enter to retry...")
        return startup_check()
    loading_bar("")

    print(f"{GREEN}✅ All systems are GO!{RESET}")
    time.sleep(1.2)
    clear_screen()

def color(val):
    if val > 0: return GREEN
    elif val < 0: return RED
    else: return WHITE

def get_trade_data():
    positions = mt5.positions_get()
    account = mt5.account_info()
    balance = account.balance if account else 0.0
    total_pnl = 0.0
    return positions or [], total_pnl, balance

def print_summary(positions, total_pnl, balance):
    print(f"\n{WHITE}========= SUMMARY ========={RESET}\n")
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
    print(f"Total Current P&L  : {color(cur_pl)}${cur_pl:.2f}{RESET}")
    print(f"{GREEN}TP Target          : ${total_tp:.2f}{RESET}")
    print(f"{RED}SL Risk            : ${total_sl:.2f}{RESET}")
    print(f"Risk on Account    : {risk_pct:.2f}%")
    print(f"Account Balance    : ${balance:.2f}")
    print(f"\n{YELLOW}TAB = Toggle Summary/Details | ENTER = Set TP/SL | ESC = Exit{RESET}")

def print_details(positions):
    print(f"\n{WHITE}========= DETAILS ========={RESET}\n")
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
        print(f"TP Price          : {tp:.2f}" if tp > 0 else "TP Price          : Not Set")
        print(f"SL Price          : {sl:.2f}" if sl > 0 else "SL Price          : Not Set")

        if tp > 0 and sl > 0:
            rr = abs(tp - op) / abs(sl - op)
            print(f"R/R Ratio         : {rr:.2f}")
        print()

    print(f"\n{YELLOW}TAB = Toggle Summary/Details | ESC = Exit{RESET}")

def show_tp_sl_setter(positions):
    global IN_TP_SL_MODE

    IN_TP_SL_MODE = True
    clear_screen()

    print(f"{WHITE}========= TP/SL CONFIGURATION ========={RESET}\n")

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
                print(f"{GREEN}{pos.symbol} → Updated.{RESET}")
            elif result.retcode == 10027:
                print(f"{RED}AutoTrading is disabled in MT5.{RESET}")
                input("Enable AutoTrading and press Enter to retry...")
                return show_tp_sl_setter(positions)
            else:
                print(f"{RED}✗ {pos.symbol} FAILED | RetCode: {result.retcode}{RESET}")

            time.sleep(0.2)

        print(f"\n{GREEN}UPDATE COMPLETE{RESET}")
        input("Press Enter to return to summary...")

    except ValueError:
        print(f"{RED}Invalid input. Please enter valid numbers.{RESET}")
        time.sleep(1)
        show_tp_sl_setter(positions)

    IN_TP_SL_MODE = False

def run_loop():
    global SHOW_DETAILS, IN_TP_SL_MODE
    startup_check()

    while True:
        if not IN_TP_SL_MODE:
            clear_screen()
            positions, pnl_total, balance = get_trade_data()

            if SHOW_DETAILS:
                print_details(positions)
                while True:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b'\t':
                            SHOW_DETAILS = False
                            break
                        elif key == b'\x1b':
                            mt5.shutdown()
                            sys.exit()
                    time.sleep(0.05)
            else:
                print_summary(positions, pnl_total, balance)
                for _ in range(int(1 / REFRESH_DELAY)):
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b'\t':
                            SHOW_DETAILS = True
                            break
                        elif key == b'\r':
                            show_tp_sl_setter(positions)
                            break
                        elif key == b'\x1b':
                            mt5.shutdown()
                            sys.exit()
                    time.sleep(REFRESH_DELAY)
        else:
            time.sleep(0.1)

if __name__ == "__main__":
    try:
        run_loop()
    except Exception as e:
        print(f"{RED}Unexpected error: {e}{RESET}")
        input("Press Enter to exit...")
    finally:
        mt5.shutdown()
