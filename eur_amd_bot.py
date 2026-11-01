import os
import requests

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
ACBA_API = "https://allratestoday.com/api/open/bank-rates/am/acba?ccy=EUR"


def get_market_rate():
    r = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=15)
    r.raise_for_status()
    return r.json()["rates"]["AMD"]


def find_eur(node):
    """Walk the JSON and return the first dict that looks like an EUR entry."""
    if isinstance(node, dict):
        vals = [str(v).upper() for v in node.values() if isinstance(v, str)]
        keys = {k.lower() for k in node}
        if "EUR" in vals and ({"buy", "sell"} <= keys or {"bank_buys", "bank_sells"} <= keys):
            return node
        for v in node.values():
            hit = find_eur(v)
            if hit:
                return hit
    elif isinstance(node, list):
        for v in node:
            hit = find_eur(v)
            if hit:
                return hit
    return None


def get_acba():
    r = requests.get(ACBA_API, timeout=15)
    r.raise_for_status()
    row = find_eur(r.json())
    if not row:
        raise ValueError(f"EUR not found in ACBA response: {r.text[:300]}")
    low = {k.lower(): v for k, v in row.items()}
    buy = low.get("buy", low.get("bank_buys"))
    sell = low.get("sell", low.get("bank_sells"))
    return float(buy), float(sell)


def send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
    r.raise_for_status()


if __name__ == "__main__":
    lines = []
    try:
        lines.append(f"💶 Market: 1 EUR = {get_market_rate():.2f} AMD")
    except Exception as e:
        lines.append(f"⚠️ Market rate failed: {e}")
    try:
        buy, sell = get_acba()
        lines.append(f"🏦 ACBA (cash): buys {buy:.2f} / sells {sell:.2f} AMD")
    except Exception as e:
        lines.append(f"⚠️ ACBA rate failed: {e}")
    send("\n".join(lines))
