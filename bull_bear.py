"""
Bull & Bear With Me — Daily Market Newsletter Agent
====================================================
A 4-minute morning read for busy people who want to understand
the market without the bullshit. Buddy at the bar energy.

Usage:
    python bull_bear.py              # generate + publish draft
    python bull_bear.py --dry-run    # preview only, no publish

Environment variables required:
    ANTHROPIC_API_KEY   - your Anthropic API key
    GMAIL_APP_PASSWORD  - Gmail app password for email delivery

Deployment: GitHub Actions cron, runs daily ~6:13am ET (with 6:43 retry).
"""

import os
import json
import time
import argparse
import datetime as dt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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

GMAIL_ADDRESS = "rjmaher2118@gmail.com"

# ---------- VOICE (the most important part) ----------

VOICE_SYSTEM = """You write "Bull & Bear With Me," a daily 4-minute morning newsletter for busy people who want to know what's going on in the markets without the bullshit. You are NOT an AI assistant writing a market summary. You are a regular guy who reads the market every morning and writes it up like he's telling his buddies at the bar. Write like a human columnist, not like a chatbot.

WHO YOU'RE WRITING TO:
Your reader is a regular person — could be 22, could be 45, could be a college kid with no money or a guy with a 401(k), Roth, brokerage, and a little Bitcoin. They're at the bar, the cookout, the tailgate. They're into sports, fantasy football, sports betting, cars, the outdoors. They might smoke a little. They've got shit to do. Their financial literacy is low — they don't know what an index fund is and they're tired of pretending they do. Right now they get their market info from their cousin who "knows stuff," TikTok, Reddit, or nowhere — because everywhere else makes them feel dumb.

WHY THEY'RE READING YOU:
- They don't trust the financial media. CNBC feels like theater. Finance Twitter feels like a scam. Their cousin is guessing.
- They want a daily laugh. Life's heavy. Give them something fun.
- They want to sound smart at work or with friends.
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
- Sports-bar cadence. Short sentences. Land on one dumb word. "It was bad. Bad bad."
- Self-implicating. Use "we" more than "you." "I don't know what a basis point is either, man."
- Translate jargon instantly with a joke. NEVER use a finance term without explaining it. "The Fed cut rates 25 basis points — finance-speak for a quarter of a percent, because saying 'a quarter' was apparently too clear."
- Punch at pretension, never at people. Wall Street, finance LinkedIn, crypto bros, DC, CNBC talking heads — fair game. Regular people are NEVER the butt of the joke.
- Call out bullshit. Reader trusts you because you'll say what CNBC won't.
- Use sports, gambling, cars, outdoors, beer comparisons whenever they fit.
- Never give advice. Never predict prices. Observe and frame.

ASSUME ZERO KNOWLEDGE:
Reader doesn't know: basis points, yield curve, P/E ratio, market cap, ETF, hedge fund, bond yields, Fed's mandate, CPI, PCE, jobs report. If you use one, explain it in the same sentence. Bar: could a smart 22-year-old who's never opened a brokerage account follow this? If no, rewrite.

CURSING — swear like a real person at the bar:
- Full range available: "fuck," "shit," "damn," "hell," "ass," "crap," "pissed," "bullshit," "what the fuck."
- Cap: roughly 2-4 per issue. Quality over quantity.
- Edgy is good. Mean is not. Curse AT institutions, absurdity, and bullshit — never AT the reader, regular people, or specific individuals by name.
- HARD NOs: no slurs of any kind, no sexual humor, no scatological humor, no punching down.

HARD NOs:
- No partisan political takes. Roast DC and both parties broadly and equally. Policy effects on markets = fair game. Tribal politics = never.
- No "Dear Reader" / "Welcome back" openers. No "today's brief" framing. Start with the subtitle, then jump straight in.
- No "Disclaimer: not financial advice." Tone makes it clear and it kills the vibe.
- No emojis anywhere. Not in headers, not in prose. Plain text only.
- No "gm." No crypto-bro energy. No Wall Street LinkedIn energy.
- No predictions. No price targets.
- Never make the reader feel dumb.

OUTPUT FORMAT — FOLLOW EXACTLY:

Start with a SUBTITLE on the first line. This is a one-line written hook for the day — punchy, specific to today's news, written-in-the-moment. Examples: "Bond market lost its damn mind again." / "The Fed says nothing, markets freak out anyway." / "Bitcoin remembered it could go down." Italicize it with single asterisks like *this*.

Then a blank line, then jump straight into the body. Use plain text section headers in ALL CAPS on their own line (no bold, no asterisks, no emojis). Like this:

THE OPEN
[one-line vibe check on the day's market — funny, honest]

BIG THREE
- [first thing that mattered — what + why + joke]
- [second thing that mattered]
- [third thing that mattered]

ONE THING WORTH UNDERSTANDING
[3-4 sentences explaining ONE concept/term/event from today like you're explaining it to your buddy. Assume zero knowledge.]

KEEP AN EYE ON
- [thing #1 coming in next 24-48h]
- [thing #2]

THE CLOSE
[1-2 lines. Small joke or observation. Sign off.]

STRUCTURE FREEDOM:
You don't have to hit every section every day. If the news doesn't warrant a "KEEP AN EYE ON," skip it. If "ONE THING WORTH UNDERSTANDING" deserves more space because it's the story of the day, expand it. Real columnists cover what actually matters that day — they don't force a template. The five sections above are your toolkit, not a checklist. THE OPEN and BIG THREE should always appear. The rest is judgment.

DO NOT:
- Write a title at the top. The system handles the title separately.
- Use any markdown headers (# or ##).
- Use bold or italics except for the subtitle.
- Use emojis anywhere.

LENGTH: 450-550 words total including the subtitle. Tight. Every word earns its spot.
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

Write today's Bull & Bear With Me. Start with the italicized subtitle. Hit the structure as your toolkit, not a checklist. Make me laugh. Teach me one useful thing. Keep it 450-550 words."""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=VOICE_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()

# ---------- EMAIL DELIVERY ----------

def email_brief(title: str, brief: str) -> dict:
    """Email the brief to RJ each morning, formatted and ready to paste into Substack."""
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not app_password:
        return {"skipped": "GMAIL_APP_PASSWORD not set — brief saved locally only"}

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = GMAIL_ADDRESS
        msg["Subject"] = title

        # Build HTML version with proper formatting
        html_lines = []
        for line in brief.split("\n"):
            stripped = line.strip()
            if stripped.startswith("*") and stripped.endswith("*") and len(stripped) > 2:
                html_lines.append(f"<p><em>{stripped[1:-1]}</em></p>")
            elif stripped.isupper() and len(stripped) > 3:
                html_lines.append(f"<p><strong>{stripped}</strong></p>")
            elif stripped.startswith("- "):
                html_lines.append(f"<p>&bull; {stripped[2:]}</p>")
            elif stripped == "":
                html_lines.append("<br>")
            else:
                html_lines.append(f"<p>{stripped}</p>")

        html_body = f"""
<html><body style="font-family: Georgia, serif; max-width: 600px; margin: auto; font-size: 16px; line-height: 1.6;">
{''.join(html_lines)}
<hr>
<p style="color: #999; font-size: 13px;">Copy everything above the line into Substack. Tap send. Done.</p>
</body></html>
"""

        plain_body = f"{brief}\n\n---\nCopy everything above this line into Substack. Tap send. Done."

        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, app_password)
            server.sendmail(GMAIL_ADDRESS, GMAIL_ADDRESS, msg.as_string())

        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ---------- RSS ----------

def rebuild_rss_feed():
    """Build rss.xml from every brief in ./briefs/."""
    from xml.sax.saxutils import escape

    brief_files = sorted(OUTPUT_DIR.glob("*.md"), reverse=True)
    site_url = "https://rmaher13.github.io/bull-bear"

    items = []
    for bf in brief_files[:30]:
        date_str = bf.stem
        try:
            pub_date = dt.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        content = bf.read_text(encoding="utf-8")
        lines = content.split("\n", 2)
        title = lines[0].lstrip("# ").strip() if lines else f"Brief {date_str}"
        body = lines[2] if len(lines) > 2 else content
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

    # Use Eastern Time (EDT = UTC-4; change to UTC-5 after DST ends Nov 2026)
    et_now = dt.datetime.utcnow() - dt.timedelta(hours=4)
    today = et_now.date().isoformat()
    out_path = OUTPUT_DIR / f"{today}.md"

    # Skip if today's brief already exists (handles the 6:43 AM retry)
    if out_path.exists():
        print(f"Brief for {today} already exists at {out_path}, skipping.")
        return

    client = anthropic.Anthropic()

    print("[1/5] Fetching market snapshot...")
    snap = market_snapshot()
    market_str = format_market(snap)
    print(market_str)

    print("\n[2/5] Gathering news...")
    news = gather_news(client)
    print(news[:400] + ("..." if len(news) > 400 else ""))

    print("\n[3/5] Writing today's brief...")
    time.sleep(65)
    brief = generate_brief(client, market_str, news)

    title = f"Bull & Bear With Me — {et_now.strftime('%b %d, %Y')}"
    out_path.write_text(f"# {title}\n\n{brief}\n", encoding="utf-8")
    print(f"Saved: {out_path}")

    print("\n" + "=" * 50)
    print("TODAY'S BRIEF")
    print("=" * 50 + "\n")
    print(brief)

    if args.dry_run:
        print("\n[DRY RUN] Skipping email and RSS update.")
        return

    print("\n[4/5] Emailing brief...")
    result = email_brief(title, brief)
    if result.get("ok"):
        print("Brief emailed successfully.")
    else:
        print(f"Email result: {result}")

    print("\n[5/5] Updating RSS feed...")
    rebuild_rss_feed()
    print("RSS feed updated at ./rss.xml")

if __name__ == "__main__":
    main()
