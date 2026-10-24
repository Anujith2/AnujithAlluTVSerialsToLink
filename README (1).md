# RDX File to Link Bot

A Telegram bot that generates direct download and streaming links for Telegram files.

## Branding

- Bot name: **RDX File to Link Bot**
- Channel: **RDX MOVIE HD**
- Telegram: [https://t.me/rdxmovie_hd](https://t.me/rdxmovie_hd)
- Generated routes: `/watch/rdxbot-...` and `/rdxbot-...`

## Deployment

Configure the variables in `config_sample.env`, then deploy with Docker, Heroku, or a VPS. Keep all secrets in environment variables and never commit them to GitHub.

> The internal Python package remains named `KPS` to preserve imports and startup compatibility. This internal name is not shown to users.

## Environment Variables

Copy `config_sample.env` to `config.env` (VPS / Docker), or add the variables under
**Settings → Config Vars** (Heroku). Every variable is a separate key: do not combine
them into one.

### Required

| Variable | Description | Example |
|---|---|---|
| `API_ID` | Telegram API ID from [my.telegram.org/apps](https://my.telegram.org/apps). Numbers only, no quotes. | `1234567` |
| `API_HASH` | Telegram API hash from the same page. | `abc123def456...` |
| `BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather). | `123456789:ABCdef...` |
| `BIN_CHANNEL` | ID of the storage channel. The bot must be an admin there. | `-1001234567890` |
| `OWNER_ID` | Your Telegram user ID. Several IDs separated by a space. | `123456789 987654321` |
| `OWNER_USERNAME` | Your Telegram username. | `@YourUsername` |
| `DATABASE_URL` | MongoDB connection string. | `mongodb+srv://user:pass@host/db` |
| `FQDN` | Your domain, without `https://`. | `your-app.herokuapp.com` |
| `HAS_SSL` | `True` if the site is served over HTTPS. | `True` |
| `NO_PORT` | `True` to hide the port in generated links. | `True` |
| `PORT` | Web server port (VPS / Docker only; Heroku sets it automatically). | `8080` |

### Optional

| Variable | Default | Description |
|---|---|---|
| `NAME` | `RDXF2L` | Application name |
| `MAX_BATCH_FILES` | `50` | Maximum files per batch |
| `SET_COMMANDS` | `True` | Register bot commands on startup |
| `FORCE_CHANNEL_ID` | empty | Users must join this channel first |
| `CHANNEL` | `False` | Process channel messages |
| `BANNED_CHANNELS` | empty | Space-separated channel IDs to reject |
| `MULTI_TOKEN1` ... `MULTI_TOKEN49` | empty | Extra bot tokens for load balancing |
| `TOKEN_ENABLED` | `False` | Require a token for access |
| `TOKEN_TTL_HOURS` | `24` | Token validity in hours |
| `SHORTEN_ENABLED` | `False` | Shorten token links |
| `SHORTEN_MEDIA_LINKS` | `False` | Shorten media links |
| `URL_SHORTENER_API_KEY` | empty | Shortener API key |
| `URL_SHORTENER_SITE` | empty | Shortener site |
| `GLOBAL_RATE_LIMIT` | `False` | Enable global rate limiting |
| `MAX_GLOBAL_REQUESTS_PER_MINUTE` | `4` | Global requests per minute |
| `RATE_LIMIT_ENABLED` | `False` | Enable per-user rate limiting |
| `MAX_FILES_PER_PERIOD` | `2` | Files allowed per period |
| `RATE_LIMIT_PERIOD_MINUTES` | `1` | Rate-limit window in minutes |
| `MAX_QUEUE_SIZE` | `100` | Maximum queued requests |
| `UPSTREAM_REPO` | empty | Your fork URL, used for auto-update |
| `UPSTREAM_BRANCH` | `main` | Branch used for auto-update |
| `SLEEP_THRESHOLD` | `60` | Flood-wait sleep threshold (seconds) |
| `WORKERS` | `8` | Number of workers |
| `BIND_ADDRESS` | `0.0.0.0` | Address the web server binds to |
| `PING_INTERVAL` | `120` | Keep-alive ping interval (seconds) |

## Heroku Setup

1. Add all **Required** variables above under **Settings → Config Vars**.
2. Set `FQDN` to `your-app.herokuapp.com`, `HAS_SSL` to `True` and `NO_PORT` to `True`.
3. Do **not** set `PORT` manually; Heroku assigns it.
4. Restart the dyno after changing variables (Heroku usually does this automatically).

## Troubleshooting

| Error in logs | Cause | Fix |
|---|---|---|
| `ValueError: Missing required Telegram API configuration` | `API_ID`, `API_HASH` or `BOT_TOKEN` is missing or empty. A single variable such as `TELEGRAM_API` is not read by the bot. | Add `API_ID`, `API_HASH` and `BOT_TOKEN` as three separate variables. |
| Bot starts but links do not open | `FQDN`, `HAS_SSL` or `NO_PORT` is wrong. | Use the bare domain in `FQDN` and match `HAS_SSL` to your site. |
| Bot cannot store files | Bot is not an admin of `BIN_CHANNEL`, or the ID is wrong. | Add the bot as admin and use the full `-100...` channel ID. |
