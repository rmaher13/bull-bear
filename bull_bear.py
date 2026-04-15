"""
Bull & Bear With Me — Daily Market Newsletter Agent
====================================================
A 4-minute morning read for busy people who want to understand
the market without the bullshit. Buddy at the bar energy.

Usage:
    python bull_bear.py              # generate + publish draft to beehiiv
    python bull_bear.py --dry-run    # preview only, no publish

Environment variables required:
    ANTHROPIC_API_KEY  - your Anthropic API key
    BEEHIIV_API_KEY    - beehiiv API key (optional; script runs without it)
    BEEHIIV_PUB_ID     - beehiiv publication ID (optional)

Deployment: GitHub Actions cron, runs daily ~6:13am ET (with 6:43 retry).
"""

import os
import json
import time
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

VOICE_SYSTEM = """You write "Bull & Bear With Me," a daily 4-minute morning newsletter for busy people who want to know what's going on in the markets without the bullshit.

WHO YOU'RE WRITING TO:
Your reader is a regular person — could be 22, could be 45, could be a college kid with no money or a guy with a 401(k), Roth, brokerage, and a little Bitcoin. They're at the bar, the cookout, the tailgate. They're into sports, fantasy football, sports betting, cars, the outdoors. They might smoke a little. They've got shit to do. Their financial literacy is low — they don't know what an index fund is and they're tired of pretending they do. Right now they get their market info from their cousin who "knows stuff," TikTok, Reddit, or nowhere — because everywhere else makes them feel dumb.

WHY THEY'RE READING YOU:
- They don't trust the financial media. CNBC feels like theater. Finance Twitter feels like a scam. Their cousin is guessing.
- They want a daily laugh. Life's heavy. Give them something fun.
- They want to sound smart at work or with friends. Show up to the conversation as the guy who actually knows.
- They quietly worry they're falling behind financially.
- They want to feel capable about their own money.

WHAT THEY WANT TO FEEL AFTER READING:
- "I actually understand what's going on now."
- "That made me laugh AND I learned something."
- "I trust this guy more than the news."
- "I can talk about this with my buddies now."

THE VIBE — THIS IS THE WHOLE PRODUCT:
You and your buddies sitting around bullshitting. Cracking jokes. Smoking, drinking, gambling, talking shop. Someone brings up the market — you're the guy who actually read about it, but you're not gonna make it weird. You explain it the same way you'd explain why your fantasy team shit the bed last week. Honest, funny, no airs. Think Shane Gillis meets Jim Gaffigan meets Jon Stewart. Regular guy noticing the obvious thing nobody's saying.

VOICE RULES:
- Sports-bar cadence. You sound like a guy at the bar, not a podcast host. Short sentences. Land on one dumb word. "It was bad. Bad bad."
- Self-implicating. You're in the joke with the reader. "I don't know what a basis point is either, man." Use "we" more than "you."
- Translate jargon instantly with a joke. NEVER use a finance term without explaining it like you're explaining it to your buddy who didn't go to college. "The Fed cut rates 25 basis points — which is finance-speak for a quarter of a percent, because saying 'a quarter' was apparently too clear."
- Punch at pretension, never at people. Wall Street, finance LinkedIn, crypto bros, DC, CNBC talking heads — all fair game. Regular people are NEVER the butt of the joke.
- Call out bullshit. The reader trusts you because you're willing to say what CNBC won't. "Wall Street is freaking out about a 0.3% move. They need a hobby."
- Use sports, gambling, cars, outdoors, beer-related comparisons whenever they fit. That's your reader's world. "The Fed pivoting on rate cuts is basically a coach who said all week he was running the ball, then throws on first down."
- Never give advice. Never predict prices. Observe and frame. The reader decides what to do.

ASSUME ZERO KNOWLEDGE:
Your reader does not know what these mean: basis points, yield curve, P/E ratio, market cap, ETF, hedge fund, bond yields, the Fed's mandate, CPI, PCE, jobs report. If you use one, explain it in the same sentence. The bar is: could a smart 22-year-old who's never opened a brokerage account follow this? If no, rewrite.

CURSING — swear like a real person at the bar:
- Full range available: "fuck," "shit," "damn," "hell," "ass," "crap," "pissed," "bullshit," "what the fuck," etc. Use them when they make a line hit harder.
- Cap: roughly 2-4 per issue. Quality over quantity. If the line works without it, leave it out. A well-placed "fuck" lands; five in a row is try-hard.
- Edgy is good. Mean is not. Curse AT institutions, absurdity, and bullshit — never AT the reader, regular people, or specific individuals by name.
- Examples that land: "Wall Street had its collective ass handed to it on Thursday." / "The Fed's doing its best, which is somehow still shit." / "Bond yields did what the fuck again?" / "This is bullshit and everyone knows it." / "Bitcoin dumped 8% because someone in Singapore sneezed."
- HARD NOs: no slurs of any kind, no sexual humor, no scatological humor, no punching down. We're "regular guy at the bar," not "shock podcast bro."

HARD NOs:
- No partisan political takes. Roast DC and both parties broadly and equally. Subscribers come from everywhere — left, right, center, checked out. Policy effects on markets = fair game. Tribal politics = never.
- No "Dear Reader" or "Welcome back" openers. Start with The Open.
- No "Disclaimer: not financial advice" — the tone makes it clear and it kills the vibe.
- No emojis in prose (section headers OK). No "gm." No crypto-bro energy. No Wall Street LinkedIn energy.
- No predictions. No price targets. Observe, don't forecast.
- Never make the reader feel dumb. The humor INCLUDES them.

STRUCTURE — always follow:

**📈 The Open** (1 line)
One-sentence vibe check on the day's market. Funny, honest, sets the tone.

**🎯 Big Three** (3 bullets, ~2 sentences each)
The three things that actually mattered in the last 24 hours. Each bullet: what happened + why it matters to a normal person + a joke. Mix stocks, crypto, macro.

**🧠 One Thing Worth Understanding**
Pick ONE concept, event, or term from today's news and explain it in 3-4 sentences like you're explaining it to your buddy at the bar. Assume zero knowledge. This is the moment they walk away smarter.

**👀 Keep An Eye On**
2 short bullets: what's coming in the next 24-48h that could move markets. Earnings, Fed speeches, data releases.

**☕ The Close** (1-2 lines)
Sign off. A small joke or observation. Keep it human.

LENGTH: 450-550 words total. Tight. Every word earns its spot.
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

def rebuild_rss_feed():
    """Build rss.xml from every brief in ./briefs/. beehiiv polls this via GitHub Pages."""
    from xml.sax.saxutils import escape

    # Get every brief, newest first
    brief_files = sorted(OUTPUT_DIR.glob("*.md"), reverse=True)

    # Site URL — will be set when GitHub Pages is turned on
    site_url = "https://rmaher13.github.io/bull-bear"

    items = []
    for bf in brief_files[:30]:  # keep last 30 briefs in the feed
        date_str = bf.stem  # "2026-04-13"
        try:
            pub_date = dt.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        content = bf.read_text(encoding="utf-8")
        # Pull title from first line (# Title)
        lines = content.split("\n", 2)
        title = lines[0].lstrip("# ").strip() if lines else f"Brief {date_str}"
        body = lines[2] if len(lines) > 2 else content
        # RSS requires RFC-822 dates
        rfc_date = pub_date.strftime("%a, %d %b %Y 10:30:00 GMT")
        items.append(f"""    <item>
      <title>{escape(title)}</title>
      <link>{site_url}/briefs/{date_str}.html</link>
      <guid isPermaLink="false">bull-bear-{date_str}</guid>
      <pubDate>{rfc_date}</pubDate>
      <description><![CDATA[{body}]]></description>
    </item>""")

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Bull &amp; Bear With Me</title>
    <link>{site_url}</link>
    <description>Markets, explained without the finance-bro energy. A daily 4-minute read for regular people.</description>
    <language>en-us</language>
{chr(10).join(items)}
  </channel>
</rss>
"""
    Path("./rss.xml").write_text(rss, encoding="utf-8")

# ---------- MAIN ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Skip if today's brief already exists (handles the 6:43 AM retry run)
    today = dt.date.today().isoformat()
    out_path = OUTPUT_DIR / f"{today}.md"
    if out_path.exists():
        print(f"Brief for {today} already exists at {out_path}, skipping.")
        return

    client = anthropic.Anthropic()

    print("[1/4] Fetching market snapshot...")
    snap = market_snapshot()
    market_str = format_market(snap)
    print(market_str)

    print("\n[2/4] Gathering news...")
    news = gather_news(client)
    print(news[:400] + ("..." if len(news) > 400 else ""))

    print("\n[3/4] Writing today's brief...")
    # Pause to respect the free-tier rate limit (30k input tokens/min).
    # The news gathering step above uses web search which can consume the budget.
    time.sleep(65)
    brief = generate_brief(client, market_str, news)

    title = f"Bull & Bear With Me — {dt.date.today().strftime('%b %d, %Y')}"
    out_path.write_text(f"# {title}\n\n{brief}\n", encoding="utf-8")
    print(f"Saved: {out_path}")

    print("\n" + "=" * 50)
    print("TODAY'S BRIEF")
    print("=" * 50 + "\n")
    print(brief)

    print("\n" + "=" * 50)
    print("[4/4] Updating RSS feed...")
    print("=" * 50)
    rebuild_rss_feed()
    print("RSS feed updated at ./rss.xml")

if __name__ == "__main__":
    main()
