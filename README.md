# honest-wait

**English** | [简体中文](README.zh-CN.md)

An agent skill for the part of every product that gets designed last: **what the user sees while something is running.** Dynamic-Island-style pills, toasts, progress bars, status lines, CLI spinners, lock-screen tiles and AI agents' "working..." bubbles all make the same mistakes - a bar that moves on a timer, a percentage nobody measured, an ETA that swings, a "Done" that vanishes, a status that outlives its task, a promo pretending to be a live activity.

honest-wait makes a wait **truthful** (it claims only what the system knows), **calm** (it changes when something changed and interrupts only when the user must act), and **finished** (every activity ends in a readable state, then leaves). It ships with a small replay checker that reads a recorded event trace and returns **STEADY / SHAKY / MISLEADING**.

## Features

- **Wait card** - freeze the activity, who started it, its duration band, surface, end states and the short list of events allowed to interrupt, before any UI is built.
- **Name / Number / Next** - three content slots that fit any surface, with a plan for how they shrink on tiny ones.
- **Progress honesty ladder (P0-P5)** - from "show nothing" to "time left as a range", each rung earned by evidence, with rules for retries, the last 1%, stalls and ETA smoothing.
- **Lifecycle script** - one surface action per app event: start, update, stage, stall, question, alert, done, failed, cancelled, abandoned.
- **Collision rules** - a written priority order, two-at-most display, same-source turn-taking, no starvation.
- **Interruption and announcement budget** - when to auto-expand or buzz, how to speak to screen readers at milestones, reduced motion, privacy on shared surfaces.
- **`honestwait.py` replay checker** - flags silent gaps, backwards progress, hangs at 99%, ETA whiplash, routine alerts, announcement floods, flashes, vanishing or lingering endings, ghosts, unasked activities and priority problems. Standard-library Python, no install.

## Installation

Copy the folder into your agent's skills directory.

| Agent | Location |
|---|---|
| Claude Code | `~/.claude/skills/honest-wait/` or `<project>/.claude/skills/honest-wait/` |
| Codex CLI | `~/.codex/skills/honest-wait/` |
| Cursor | `<project>/.cursor/skills/honest-wait/` |
| GitHub Copilot | `<project>/.github/skills/honest-wait/` |
| Other agents | anywhere the agent reads `SKILL.md` files, or paste `SKILL.md` into the system prompt |

```bash
git clone https://github.com/fangdididi/honest-wait.git ~/.claude/skills/honest-wait
```

## Usage

Ask your agent in plain words; the skill triggers on live status and progress work:

- "Add a live status pill for our video export and make it honest."
- "Our upload bar sits at 99% for half a minute - fix the wait."
- "Two jobs and an incoming call share the top bar. Who wins?"
- "Review the agent's 'thinking...' indicator before we ship."

Run the checker yourself:

```bash
python3 honestwait.py init wait-card.json          # blank wait card
python3 honestwait.py demo demo-trace.jsonl        # sample trace with problems in it
python3 honestwait.py replay demo-trace.jsonl      # -> VERDICT: MISLEADING
python3 honestwait.py replay examples/steady-upload.jsonl --card wait-card.json   # -> STEADY
python3 honestwait.py replay trace.jsonl --json    # machine-readable; exit code 1 unless STEADY
```

A trace is one JSON object per line:

```json
{"t": 0.0, "id": "upload", "type": "start", "source": "user", "priority": 0}
{"t": 6.0, "id": "upload", "type": "update", "progress": 0.25, "units": [6, 24], "eta": 45}
{"t": 18.0, "id": "upload", "type": "update", "progress": 0.46, "units": [11, 24], "reason": "retrying photo 12"}
{"t": 38.0, "id": "upload", "type": "done"}
{"t": 41.0, "id": "upload", "type": "end"}
```

## Example

```
honest-wait replay: 16 events, 3 activities
  WARN ETA_WHIPLASH     export     t=3.0     ETA jumped from ~58s to 20s within 2s; smooth it or show a range
  WARN ANNOUNCE_FLOOD   export     t=4.0     screen-reader announcement 3.0s after the last one; ...
  FAIL BACKWARDS        export     t=18.0    progress fell 30% -> 26% with no stated reason; ...
  FAIL ROUTINE_ALERT    export     t=18.0    alert on routine progress; ...
  WARN FLASH            sync       t=20.1    shown for 0.10s then gone; delay showing short tasks by ~0.4s
  FAIL UNASKED          promo      t=21.0    started by 'marketing': a live status surface is for ...
  WARN HANG_AT_99       export     t=25.0    sat at 99% for 15s; the last step needs its own stage label
  FAIL GHOST            promo      t=40.3    activity never ended; ...
  WARN VANISH           export     t=40.3    final state shown only 0.3s; hold it 1.0-8.0s
VERDICT: MISLEADING
```

## File structure

```
honest-wait/
├── SKILL.md                      # skill instructions (English)
├── SKILL.zh-CN.md                # skill instructions (Chinese)
├── README.md                     # this file
├── README.zh-CN.md               # Chinese README
├── honestwait.py                 # wait card template, demo trace, replay checker
├── examples/
│   ├── steady-upload.jsonl       # a wait done right (incoming call, honest retry, readable ending)
│   └── shaky-export.jsonl        # a wait done wrong
└── LICENSE
```

## License

MIT © fangdididi
