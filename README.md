# GitHub Watchdog

This is the off-machine watchdog for `comp-price-strategy`.

The goal is no longer "check one exact checkpoint file at one exact minute." The goal is:

1. prove the laptop is still alive from a recent heartbeat
2. independently check whether today's scrape finished by a daytime deadline

## Files in the watchdog repo

The watchdog repo contains one synced file at a fixed path:

- `state/comp-price-strategy-heartbeat.json`

Do not change that path. The laptop and workflow both assume it.

## How it works

There are two separate local jobs:

1. `com.avandaro.comp-price-strategy`
   - runs `python main.py daily-run`
   - owns the scraper

2. `com.avandaro.comp-price-strategy-heartbeat`
   - runs `python main.py heartbeat --sync-github`
   - owns off-machine liveness

This split is intentional. The heartbeat job is lightweight and keeps GitHub updated even while the scrape is still running.

The GitHub workflow then checks:

1. Is the heartbeat fresh enough to prove the laptop/network is alive?
2. If it is after the daily completion deadline, did today's scrape reach `success` or `review_needed`?

## GitHub schedule

The workflow runs at:

- `6:35 AM` and `6:50 AM`
- `11:35 AM` and `11:50 AM`
- `2:35 PM` and `2:50 PM`
- `6:35 PM` and `6:50 PM`

All in `America/Chicago`.

The second run in each window is a backstop because GitHub scheduled workflows can be delayed or dropped.

## Laptop setup

Configure these env vars in the local scraper project:

- `HEARTBEAT_MACHINE_NAME`
  - optional
  - if omitted, the heartbeat uses a generic machine label instead of your real hostname
- `HEARTBEAT_GITHUB_REPO`
  - format: `owner/repo`
- `HEARTBEAT_GITHUB_TOKEN`
  - GitHub token with `Contents: Read and write` permission on the watchdog repo

The heartbeat sync always uses the watchdog repo's default branch and the fixed path:

- branch: repo default branch
- path: `state/comp-price-strategy-heartbeat.json`

Do not set `HEARTBEAT_GITHUB_BRANCH` or `HEARTBEAT_GITHUB_PATH` to anything custom.

## Initial seed

Before enabling the GitHub Actions schedule, seed the heartbeat file once from the laptop:

```bash
cd /Users/ederaguirre/Claude/_Projects/comp-price-strategy
source .venv/bin/activate
python main.py heartbeat --sync-github --json
```

That should create or update:

- `state/comp-price-strategy-heartbeat.json`

Only after that should you enable the workflow schedule.

## GitHub repo setup

1. Create a small dedicated watchdog repo.
2. Keep its default branch as the branch the workflow runs from.
3. Copy `ops/github_watchdog/watchdog.workflow.yml` into `.github/workflows/watchdog.yml`.
4. Copy `ops/github_watchdog/check_heartbeat.py` into `ops/github_watchdog/check_heartbeat.py`.
5. Create the directory `state/`.
6. Add repo secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
7. Seed the heartbeat from the laptop once before trusting the schedule.

## Manual checks

Local:

```bash
cd /Users/ederaguirre/Claude/_Projects/comp-price-strategy
source .venv/bin/activate
python main.py heartbeat --json
python main.py heartbeat --sync-github --json
```

Validator:

```bash
cd /Users/ederaguirre/Claude/_Projects/comp-price-strategy
source .venv/bin/activate
python ops/github_watchdog/check_heartbeat.py \
  --heartbeat-path reports/heartbeat.json \
  --timezone America/Chicago
```

## Why use a separate repo

If you keep the watchdog repo public, GitHub-hosted runner usage is free there.
Only the small heartbeat JSON is exposed. The scraper data stays on the laptop.
