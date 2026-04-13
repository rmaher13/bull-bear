"""
Bull & Bear With Me — Daily Market Newsletter Agent
====================================================
A 4-minute morning read for the working person who wants to understand
the market without the finance-bro jargon. Dad humor meets Jon Stewart.

Usage:
    python bull_bear.py              # generate + publish draft to beehiiv
    python bull_bear.py --dry-run    # preview only, no publish

Environment variables required:
    ANTHROPIC_API_KEY  - your Anthropic API key
    BEEHIIV_API_KEY    - beehiiv API key (optional; script runs without it)
    BEEHIIV_PUB_ID     - beehiiv publication ID (optional)

Deployment: GitHub Actions cron, runs daily ~6:30am ET.
"""

import os
import json
import argparse
import datetime as dt
from pathlib import Path
import urllib.request
import urllib.error

import anthropic

# ---------- CONFIG ----------

MODEL = "claude-sonnet-4-6"   # quality matters — this is the voice

CRYPTO_TICKERS = ["BTC_USD", "ETH_USD"]
CRYPTO_DISPLAY = {"BTC_USD": "Bitcoin", "ETH_USD": "Ethereum"}

OUTPUT_DIR = Path("./briefs")
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------- VOICE (the most important part) ----------

VOICE_SYSTEM = """You write "Bull & Bear With Me," a daily 4-minute morning newsletter for regular working people who want to understand the stock market, crypto, and the economy without feeling dumb. Your reader is a parent with a full-time job and a 401(k) they half-understand. They want to feel in the loop, not lectured.

VOICE — this is the whole product, get it right:
- Sports-bar cadence. You sound like a guy explaining the market to a buddy over beers, not a podcast host. Think Shane Gillis meets Jim Gaffigan meets Jon Stewart. Regular guy noticing the obvious thing nobody's saying.
- Self-implicating. You're in the joke with the reader, not above it. "I don't know what a basis point is either, man." Use "we" more than "you."
- Punch at pretension, not at people. Wall Street analysts, finance LinkedIn, crypto bros, DC — all fair game. Regular people are never the butt of the joke.
- Affectionate mockery. The humor comes from pointing at something everyone sees and saying the quiet part out loud. ("The Fed has two jobs. Two. And they're somehow bad at both.")
- Rhythm matters. Short sentences. Long pauses become line breaks. Land on one dumb word. "The CPI report came out today. It was bad. Bad bad."
- Translate jargon instantly with a joke. "The Fed cut rates 25 basis points — which is finance-speak for a quarter of a percent, because apparently saying 'a quarter' was too clear."
- Use absurd-but-true comparisons. "Rate cuts just got harder to argue for. Which is like your doctor telling you to hit 150 pounds and you roll in at 247."
- Never give financial advice. You observe, explain, and riff. The reader decides.

CURSING — yes, swear like a real person:
- Use "shit," "damn," "hell," "ass," "crap," "pissed" when they actually make a line hit harder. A well-placed "shit" lands; five in a row is try-hard.
- Cap: roughly 1-3 swears per issue, max. Quality over quantity. If the line works without it, leave it out.
- NEVER use slurs, never punch down, never sexual or scatological. We're talking "regular guy at the bar" not "edgy podcast bro."
- Examples that land: "The Fed is doing its best, which is somehow still shit." / "Inflation's at 3.3%. That's not great, Bob." / "Bond traders had a hell of a week." / "Wall Street had its collective ass handed to it on Thursday."
- Never curse AT the reader or AT regular people. Curse at institutions, abstractions, and absurdity. Wall Street, the Fed, DC, crypto bros, your own dumb portfolio decisions.

HARD NOs:
- No partisan political takes. Roast DC and both parties broadly and equally. Subscribers come from everywhere — left, right, center, checked out. Don't pick sides on candidates, parties, or hot-button culture stuff. Policy effects on markets = fair game. Tribal politics = never.
- No sexual or shock humor. Wrong register for morning coffee.
- No emojis in prose (the section headers have them, that's fine). No "gm." No crypto-bro energy. No Wall Street LinkedIn energy.
- Never make the reader feel dumb. The humor INCLUDES them, never excludes them.

STRUCTURE — always follow:

**📈 The Open** (1 line)
One-sentence vibe check on the day's market. Funny, honest, sets the tone.

**🎯 Big Three** (3 bullets, ~2 sentences each)
The three things that actually mattered in the last 24 hours. Each bullet: what happened + why it matters to a normal person + a joke. Mix stocks, crypto, macro — whatever's real news.

**🧠 One Thing Worth Understanding**
Pick ONE concept, event, or term from today's news and explain it in 3-4 sentences like you're explaining it to a friend over coffee. This is the "you learned something" moment. Make it genuinely useful.

**👀 Keep An Eye On**
2 short bullets: what's coming in the next 24-48h that could move markets. Earnings, Fed speeches, data releases, crypto unlocks, etc.

**☕ The Close** (1-2 lines)
Sign off. A small joke, an observation, or a nudge. Keep it human.

LENGTH: ~450-550 words total. Tight. Every word earns its spot.

HARD RULES:
- No "Dear Reader" or "Welcome back" openers. Start with The Open.
- No "Disclaimer: not financial advice" — the tone already makes that clear, and it breaks the vibe.
- Never predict prices. You can note what analysts or consensus expect, but you don't call tops and bottoms.
- If a news item involves a specific stock or crypto being hyped, be skeptical by default. Your reader is a regular person, not a degenerate.
"""

# ---------- MARKET DATA ----------

def fetch_crypto(instrument: str) -> dict:
    """Crypto.com public API — no auth needed."""
    url = f"https://api.crypto.com/exchange/v1/public/get-tickers?instrument_name={instrument}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        row = data["result"]["data"][0]
        return {
            "name": CRYPTO_DISPLAY.get(instrument, instrument),
            "price": float(row["a"]),
            "change_pct": float(row["c"]) * 100,
        }
    except Exception as e:
        return {"name": CRYPTO_DISPLAY.get(instrument, instrument), "error": str(e)}

def fetch_stock_index(symbol: str) -> dict:
    """Pull index quote from Yahoo Finance's public chart endpoint. No API key."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        result = data["chart"]["result"][0]["meta"]
        price = result["regularMarketPrice"]
        prev = result["chartPreviousClose"]
        return {
            "symbol": symbol,
            "price": price,
            "change_pct": ((price - prev) / prev) * 100,
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

def market_snapshot() -> dict:
    """Pull S&P, Nasdaq, Dow, BTC, ETH."""
    return {
        "sp500": fetch_stock_index("^GSPC"),
        "nasdaq": fetch_stock_index("^IXIC"),
        "dow": fetch_stock_index("^DJI"),
        "btc": fetch_crypto("BTC_USD"),
        "eth": fetch_crypto("ETH_USD"),
    }

def format_market(snap: dict) -> str:
    lines = ["MARKET SNAPSHOT (last close / 24h):"]
    labels = {
        "sp500": "S&P 500", "nasdaq": "Nasdaq", "dow": "Dow",
        "btc": "Bitcoin", "eth": "Ethereum",
    }
    for k, lbl in labels.items():
        d = snap[k]
        if "error" in d:
            lines.append(f"- {lbl}: data unavailable")
            continue
        arrow = "▲" if d.get("change_pct", 0) >= 0 else "▼"
        price = d.get("price", 0)
        pct = d.get("change_pct", 0)
        lines.append(f"- {lbl}: ${price:,.2f} {arrow} {pct:+.2f}%")
    return "\n".join(lines)

# ---------- NEWS GATHERING ----------

def gather_news(client: anthropic.Anthropic) -> str:
    """Use Claude + web_search to pull the last 24h of market-moving news."""
    today = dt.date.today().isoformat()
    prompt = f"""Today is {today}. Search the web for the most important financial news from the last 24 hours that would matter to a regular working person with a 401(k) and maybe a little crypto.

Cover a mix of:
- Stock market movers (big earnings, big single-day moves, sector stories)
- Crypto news (only if genuinely newsworthy — price moves, regulation, adoption)
- Macro/Fed/economy (rates, inflation data, jobs, GDP, Fed speak)
- Anything a normal person might see on TV or hear at work and wonder about

Return 8-12 bullets. Each bullet: one factual sentence + source in parentheses. Skip celebrity/crypto-bro gossip. Skip wonky finance-industry-only stuff. Focus on what moves portfolios and what a normal person would actually care about."""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": prompt}],
    )
    text = "\n".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return text.strip()

# ---------- BRIEF GENERATION ----------

def generate_brief(client: anthropic.Anthropic, market: str, news: str) -> str:
    today = dt.date.today().strftime("%A, %B %d, %Y")
    user_msg = f"""Date: {today}

{market}

NEWS FROM THE LAST 24H:
{news}

Write today's Bull & Bear With Me. Hit the structure. Make me laugh at least once. Teach me one useful thing. Keep it 450-550 words."""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=VOICE_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()

# ---------- PUBLISHING ----------

def publish_to_beehiiv(title: str, body_markdown: str) -> dict:
    """Creates a DRAFT in beehiiv. You review and tap send."""
    api_key = os.environ.get("BEEHIIV_API_KEY")
    pub_id = os.environ.get("BEEHIIV_PUB_ID")
    if not api_key or not pub_id:
        return {"skipped": "beehiiv credentials not set — brief saved locally only"}

    url = f"https://api.beehiiv.com/v2/publications/{pub_id}/posts"
    payload = {
        "title": title,
        "subtitle": "Markets, explained without the finance-bro energy.",
        "body_content": body_markdown,
        "status": "draft",
        "content_tags": ["markets", "daily", "bull-and-bear"],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return {"ok": True, "response": json.loads(r.read())}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"{e.code} {e.reason}", "body": e.read().decode()}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ---------- MAIN ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    client = anthropic.Anthropic()

    print("[1/4] Fetching market snapshot...")
    snap = market_snapshot()
    market_str = format_market(snap)
    print(market_str)

    print("\n[2/4] Gathering news...")
    news = gather_news(client)
    print(news[:400] + ("..." if len(news) > 400 else ""))

    print("\n[3/4] Writing today's brief...")
    brief = generate_brief(client, market_str, news)

    today = dt.date.today().isoformat()
    title = f"Bull & Bear With Me — {dt.date.today().strftime('%b %d, %Y')}"
    out_path = OUTPUT_DIR / f"{today}.md"
    out_path.write_text(f"# {title}\n\n{brief}\n", encoding="utf-8")
    print(f"Saved: {out_path}")

    print("\n[4/4] Publishing draft to beehiiv...")
    if args.dry_run:
        print("Dry run — skipped.")
    else:
        result = publish_to_beehiiv(title, brief)
        print(json.dumps(result, indent=2)[:500])

    print("\n" + "=" * 50)
    print("TODAY'S BRIEF")
    print("=" * 50 + "\n")
    print(brief)

if __name__ == "__main__":
    main()
