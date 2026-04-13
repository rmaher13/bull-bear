# Bull & Bear With Me

A daily 4-minute morning newsletter for working people who want to understand the market without the finance-bro energy.

## Files

- `bull_bear.py` — the agent. Pulls S&P/Nasdaq/Dow/BTC/ETH prices + web news, writes the brief, saves it, publishes a draft to beehiiv.
- `.github/workflows/daily_brief.yml` — runs the agent every morning at 6:30am ET, free.
- `briefs/` — your archive of every issue.

## Setup

Don't try to do this yourself — I'll walk you through it step by step in chat. When you're ready to set up, tell me and we'll go one click at a time.

## Daily loop once live

1. **6:30 AM ET** — agent writes the brief, puts it in beehiiv as a draft.
2. **You get an email from beehiiv** — "Draft ready."
3. **30-60 seconds** — scan on your phone, tap send, or tweak and send.
4. After 10 clean drafts you trust, flip the script to auto-publish. Truly hands-off.

## Costs

- GitHub Actions: free
- beehiiv: free under 2,500 subs
- Anthropic API: ~$5/month at daily cadence
- **Total: ~$5/month.** One paid subscriber at $15 breaks you even 3x over.
