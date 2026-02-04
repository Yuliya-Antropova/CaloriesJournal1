# Deploy to Railway (hands-off)

## What you get
- Docker-based deploy (predictable)
- Polling worker (no webhook)
- SQLite stored on a mounted volume at `/data` (so it survives restarts)

## Steps (minimum clicks)
1) Put your code into GitHub (private repo recommended).
2) Railway → New Project → Deploy from GitHub.
3) Railway will detect Dockerfile and build.
4) Add a Volume mounted to `/data`.
5) Set Variables:
   - BOT_TOKEN (from @BotFather)
   - TZ=Asia/Yerevan
   - DB_PATH=/data/bot.db
   - (optional) BETA_WHITELIST=your_tg_id
6) Deploy.

## Notes
- If you accidentally shared BOT_TOKEN publicly, rotate it immediately in @BotFather:
  /revoke then set the new token in Railway Variables.
