# api-burn-tuning

> Figure out how an AI platform actually rate-limits you, then compute the fastest stable parameters for a "token burner" (a tool that deliberately consumes API quota/credits).

## Introduction

This is a WorkBuddy / Claude Code skill repository. It's built for anyone who needs to configure a "token burner" against an LLM platform — for example to burn through free quota, farm credits in promotional campaigns, or profile the rate-limit model of a new platform (Zhipu, SiliconFlow, Volcano Ark, Alibaba Bailian, SenseNova, etc.).

The most expensive mistake when configuring a burner is tuning parameters **without knowing what the platform is actually limiting**. Getting the direction wrong can cost you a 400x difference in throughput (measured: 4,000 tokens/min vs 1.9M tokens/min). This skill packages a field-tested methodology plus probing scripts: use a pressure ladder and concurrency ramp to determine whether the platform limits by **rpm** (requests per minute) or **tpm** (tokens per minute) — the optimal strategies for the two are exact opposites — then pick the right burn style and parameters accordingly.

Who it's for: developers and operators who need to drive API usage up on LLM platforms, or anyone wiring a "burn the quota" subroutine into their agent.

**Trigger words**: burn tokens, token burner, consume quota, farm credits, rate limit, 429, rpm, tpm, concurrency, padding length, API usage.

## Features

- **Rate-limit model detection methodology**: don't guess. Ramp request frequency up step by step until you hit 429s, then read the raw 429 error message (`rpm exhausted` / `tpm exhausted`) to identify the limiting dimension. If the message says nothing, run a contrast experiment: "huge single requests at low frequency" vs "tiny requests at high frequency" — whichever trips first is your answer.
- **Head-to-head comparison of three burn styles**: padding style (stuff a long text in, ask for a one-character reply), long-output style (make it generate like crazy), and snowball style (grow the context round by round). Measured results show padding crushes the other two (337K/min vs a few thousand/min) — because "reading" is two orders of magnitude faster than "writing".
- **Single-request size optimization**: measured latency for payloads from 30K to 400K characters, locating the sweet spot around 100K characters (~2.8s per call). Bigger isn't better — past the knee, per-call latency explodes.
- **Candidate parameter bake-off**: run several "padding size × concurrency" combos for 45 seconds each and pick the "fast and stable" one — zero rate-limit hits while using only half the request quota, which also keeps you off the risk-control radar.
- **Five ready-to-run probing scripts**: swap the `KEY` / `BASE` / `MODEL` constants at the top to target a new platform. Results stream into a same-named JSON file as they run, so a crash loses nothing. A local fake OpenAI-compatible server is included so you can debug your own program without spending quota.
- **Credit ↔ token conversion measurement**: there's no universal conversion rate ("writing" costs ~2.7x more than "reading"). The skill shows how to read your dashboard balance precisely via browser automation and measure a per-style conversion rate.
- **A long list of hard-earned lessons**: including a real incident caused by judging "done" from token estimates instead of the real dashboard balance, why network hiccups must not be treated as fatal errors, time-of-day differences (2–7x faster late at night than at noon), and an adaptive 429 backoff strategy that saved 30+ minutes in a single 96-minute run.

## How It Works / Tech Stack

- **Pure Python 3 probing scripts**, standard library only (`urllib.request` + `json`), zero third-party dependencies.
- Targets **OpenAI-compatible `/chat/completions` endpoints** — point `BASE` at any compatible platform.
- Core methodology: **pressure ladder** (request interval from 8–10s down to zero-gap bursts) → **concurrency ramp** (1 → 2 → 3) → **read the raw 429 message** to identify the limit dimension → bake off candidate parameter sets for 45s each → pick the "fast and stable" winner.
- Key insight: under rpm limits, requests are the scarce resource — make each one as large as possible; under tpm limits, hug the quota instead. Platforms often stack multiple limit layers (rpm + a 5-hour credit window + a weekly credit cap), and the window quota usually tops out first.
- Iron rule for the stop condition: **decide from the platform's real remaining balance** (stop at 5% left). Token-based estimates are for progress display only — never let the program stop itself based on them.

## Installation & Usage

Copy this repository's contents into your skills directory, keeping the folder name `api-burn-tuning`:

- WorkBuddy / CodeBuddy: `~/.workbuddy/skills/api-burn-tuning/`
- Claude Code: `~/.claude/skills/api-burn-tuning/`

Restart your session and the skill will be matched automatically via trigger words. Typical workflow:

1. Run `scripts/_限流口径实测.py` to learn whether output tokens count against quota, the input ceiling, rate-limit recovery time, and the single-request padding ceiling.
2. Run `scripts/_烧法对比实测.py` to find the rpm ceiling with a pressure ladder and compare the three burn styles.
3. Run `scripts/_并发实测.py` to ramp concurrency and capture raw 429 messages.
4. Run `scripts/_推荐参数实测.py` to bake off candidate parameter sets and pick the final configuration.

Each script takes 5–10 minutes — **run them in the background**. Results are written to same-named JSON files.

## Project Structure

```
api-burn-tuning/
├── SKILL.md                    # Skill body: methodology + measured data + lessons learned
├── README.md                   # Chinese documentation
├── README_EN.md                # This file
└── scripts/
    ├── _限流口径实测.py         # Probe quota accounting, input ceiling, recovery time, padding ceiling
    ├── _烧法对比实测.py         # Pressure ladder to find rpm ceiling + three-style comparison
    ├── _烧法参数实测.py         # Burn-style parameter probing
    ├── _烧法参数实测2.py        # Burn-style parameter probing (second round)
    ├── _并发实测.py             # Concurrency ramp, capture raw 429 messages
    ├── _推荐参数实测.py         # Candidate parameter bake-off, pick the final set
    ├── _积分换算实测.py         # Credit ↔ token conversion measurement
    ├── _读积分.py               # Read the dashboard credit balance
    └── _假接口.py               # Local fake OpenAI-compatible server for quota-free debugging
```

## Notes & Caveats

- **Scripts need a valid platform API key**: supply it via an environment variable (e.g. `SENSENOVA_API_KEY`) or edit the `KEY` constant at the top of each script.
- **Re-run everything when switching platforms**: 429 error wording and rate-limit models differ across platforms — conclusions don't transfer.
- **Risk control**: pushing throughput to millions of tokens per minute is far beyond normal usage. Run in segments, watch for account anomalies, and **never burn paid quota**.
- **Don't draw conclusions from tiny samples** like "429 after two consecutive calls": use a stepped pressure ladder and record requests/minute at each step.
- Dashboard balance reads lag by tens of seconds — leave a safety margin between checks, or use a ratio threshold (stop at 5% remaining), which is inherently safe.

## License

MIT

## Author

sheen945
