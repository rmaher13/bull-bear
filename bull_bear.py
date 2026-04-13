name: Daily Bull & Bear

on:
  schedule:
    - cron: "30 10 * * *"
  workflow_dispatch:

jobs:
  generate:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install anthropic

      - name: Generate brief
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          BEEHIIV_API_KEY: ${{ secrets.BEEHIIV_API_KEY }}
          BEEHIIV_PUB_ID: ${{ secrets.BEEHIIV_PUB_ID }}
        run: python bull_bear.py

      - name: Archive brief
        run: |
          git config user.name "brief-bot"
          git config user.email "bot@users.noreply.github.com"
          git add briefs/ rss.xml
          git diff --staged --quiet || git commit -m "brief: $(date -u +%Y-%m-%d)"
          git push
