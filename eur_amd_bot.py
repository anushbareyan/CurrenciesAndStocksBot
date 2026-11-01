import os
import requests

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
ACBA_API = "https://allratestoday.com/api/open/bank-rates/am/acba?ccy=EUR"

EUR_ALERT_BELOW = 390   # AMD
SNPS_ALERT_ABOVE = 700  # USD
HEADERS = {"User-Agent": "Mozilla/5.0"}


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


def get_snps():
    """SNPS price in USD. Tries Yahoo first, then Stooq."""
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/SNPS",
            headers=HEADERS, timeout=15,
        )
        r.raise_for_status()
        return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except Exception:
        r = requests.get(
            "https://stooq.com/q/l/?s=snps.us&f=sd2t2ohlcv&h&e=csv",
            headers=HEADERS, timeout=15,
        )
        r.raise_for_status()
        row = r.text.strip().splitlines()[1].split(",")
        return float(row[6])  # Close

def send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_ID.split(","):
        try:
            r = requests.post(url, data={"chat_id": chat_id.strip(), "text": text}, timeout=15)
            r.raise_for_status()
        except Exception as e:
            print(f"Failed for {chat_id}: {e}")

if __name__ == "__main__":
    lines, alerts = [], []

    try:
        eur = get_market_rate()
        lines.append(f"💶 Market: 1 EUR = {eur:.2f} AMD")
        if eur < EUR_ALERT_BELOW:
            alerts.append(f"EUR is below {EUR_ALERT_BELOW} AMD ({eur:.2f})")
    except Exception as e:
        lines.append(f"⚠️ Market rate failed: {e}")

    try:
        buy, sell = get_acba()
        lines.append(f"🏦 ACBA (cash): buys {buy:.2f} / sells {sell:.2f} AMD")
    except Exception as e:
        lines.append(f"⚠️ ACBA rate failed: {e}")

    try:
        snps = get_snps()
        lines.append(f"📈 SNPS: ${snps:.2f}")
        if snps > SNPS_ALERT_ABOVE:
            alerts.append(f"SNPS is above ${SNPS_ALERT_ABOVE} (${snps:.2f})")
    except Exception as e:
        lines.append(f"⚠️ SNPS price failed: {e}")

    if alerts:
        lines.insert(0, "🚨 IMPORTANT! " + " | ".join(alerts) + "\n")

    send("\n".join(lines))
