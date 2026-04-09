# Neurotech Newsletter Bot

Automated newsletter bot that delivers competitive intelligence on neurotech hardware and productivity apps to Slack every 12 hours.

## Features

- **Automated Delivery**: Sends at 12:00 AM and 12:00 PM EST
- **Multi-Source Aggregation**: Google News, RSS feeds, Reddit
- **AI Summaries**: 3-bullet summaries using Claude Haiku
- **Smart Deduplication**: Fuzzy matching prevents repeat content
- **Cost Efficient**: ~$0.04/day for AI summaries

## Coverage

### Neurotech (80% - 16 links)
- EEG headbands (Muse, Neurable, EMOTIV, Neurosity)
- Brain-computer interfaces (Neuralink, Synchron, Kernel)
- Neurostimulation (Apollo Neuro, Flow Neuroscience)
- 570+ companies from market map

### Productivity (20% - 4 links)
- Screen time apps (Opal, Freedom, Cold Turkey)
- Digital wellness (One Sec, Clearspace, Forest)
- Phone addiction solutions

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/YOUR_USERNAME/neurotech-newsletter-bot.git
cd neurotech-newsletter-bot
pip install -r requirements.txt
```

### 2. Configure Secrets

Copy the example env file:
```bash
cp .env.example .env
```

Edit `.env` with your keys:
```
ANTHROPIC_API_KEY=sk-ant-xxxxx
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxxxx
```

### 3. Test Locally

```bash
# Dry run (no Slack delivery)
python src/main.py --dry-run

# Live run
python src/main.py
```

### 4. Deploy to GitHub Actions

1. Push to GitHub
2. Go to Settings → Secrets and variables → Actions
3. Add these secrets:
   - `ANTHROPIC_API_KEY`: Your Anthropic API key
   - `SLACK_WEBHOOK_URL`: Your Slack webhook URL
4. The bot will run automatically at 12am and 12pm EST

## Getting API Keys

### Anthropic API Key
1. Go to https://console.anthropic.com/
2. Create an account or sign in
3. Navigate to API Keys
4. Create a new key

### Slack Webhook URL
1. Go to https://api.slack.com/apps
2. Create a new app (From scratch)
3. Select your workspace
4. Go to "Incoming Webhooks" → Enable
5. Click "Add New Webhook to Workspace"
6. Select #industry-newsletter channel
7. Copy the webhook URL

## Manual Trigger

You can manually run the newsletter from GitHub:

1. Go to Actions tab
2. Select "Neurotech Newsletter"
3. Click "Run workflow"
4. Optionally enable dry run or change hours

## Project Structure

```
neurotech-newsletter-bot/
├── .github/workflows/
│   └── newsletter.yml      # GitHub Actions schedule
├── src/
│   ├── fetchers/           # News source fetchers
│   │   ├── google_news.py  # Google News RSS
│   │   ├── rss_feeds.py    # Company blogs, publications
│   │   └── reddit.py       # Reddit discussions
│   ├── processors/         # Article processing
│   │   ├── deduplicator.py # Remove duplicates, rank
│   │   ├── classifier.py   # Categorize articles
│   │   └── summarizer.py   # AI summaries
│   ├── delivery/
│   │   └── slack.py        # Slack webhook delivery
│   ├── config/
│   │   ├── companies.json  # 580 tracked companies
│   │   └── keywords.json   # Search keywords
│   └── main.py             # Orchestrator
├── data/
│   └── sent_articles.json  # Tracking (auto-generated)
├── requirements.txt
└── README.md
```

## Customization

### Add Companies

Edit `src/config/companies.json`:
```json
{
  "name": "New Company",
  "url": "https://newcompany.com",
  "category": "neurotech"
}
```

### Add Keywords

Edit `src/config/keywords.json`:
```json
{
  "neurotech": {
    "primary": ["new keyword", ...]
  }
}
```

### Change Schedule

Edit `.github/workflows/newsletter.yml`:
```yaml
schedule:
  - cron: '0 5 * * *'   # 12:00 AM EST
  - cron: '0 17 * * *'  # 12:00 PM EST
```

## Cost Breakdown

| Service | Cost |
|---------|------|
| GitHub Actions | Free (2000 mins/month) |
| Google News RSS | Free |
| Reddit API | Free |
| Claude Haiku | ~$0.04/day |
| **Total** | **~$1.20/month** |

## Troubleshooting

### No articles found
- Check if keywords in `keywords.json` are relevant
- Try increasing `--hours` parameter
- Check internet connectivity

### Slack delivery failed
- Verify webhook URL is correct
- Check if webhook is active in Slack settings
- Look for error messages in GitHub Actions logs

### Summaries not working
- Verify `ANTHROPIC_API_KEY` is set correctly
- Check API credit balance
- Bot will use fallback summarizer if API fails

## License

MIT
