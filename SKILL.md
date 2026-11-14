---
name: honest-wait
description: Design, build, or review the live status a user sees while something runs - a Dynamic-Island-style pill, a toast, a progress bar, a status line, a CLI spinner, a lock-screen tile, or an agent's "working..." bubble. Use when adding progress or live status to an upload, export, build, deploy, order, delivery, timer, call, payment, sync, AI agent run, or any task that takes longer than a second; when two activities compete for one surface; or when a wait "feels" broken (frozen bar, stuck at 99%, ETA that jumps, status that vanishes or never leaves, screen reader that never stops talking).
---

# honest-wait

## What this is

Every long task shows the user *something* while it runs. That something is usually designed last, in a hurry, and it lies in small ways: a bar that creeps at a fixed speed whatever the work is doing, a percentage nobody measured, an ETA that swings from 20 seconds to a minute, a "Done!" that disappears before anyone could read it, a status pill that stays after the work has died, a promo dressed up as a live activity.

honest-wait is a method for making a wait **truthful, calm, and finished**:

- **Truthful** - the surface claims only what the system actually knows.
- **Calm** - it changes when something changed, interrupts only when the user must act or notice now, and speaks to screen readers at milestones rather than on every tick.
- **Finished** - every activity ends in a state the user can read: done, failed, cancelled, or abandoned, and then it leaves.

It works on any surface and in any stack. It gives you a frozen *wait card*, three content slots, a ladder of progress honesty, a lifecycle script, rules for when activities collide, an interruption and announcement budget, and a replay checker (`honestwait.py`) that reads a recorded event trace and returns **STEADY / SHAKY / MISLEADING**.

## When to use it

- You are adding live status to a task that takes more than about a second.
- You are building a Dynamic Island / live-activity component, a toast system, a job tray, a CLI progress line, or an agent "thinking" indicator.
- Two or more activities can be in flight at once and must share one surface.
- Users report the wait feels wrong: "it froze", "it says 99% forever", "it said done but nothing happened", "VoiceOver keeps reading numbers".
- Before shipping, as a review gate on an existing progress UI.

Skip it for work under ~100 ms (show nothing) and for pure marketing surfaces (they do not belong on a live-status surface at all).

## Step by step

### 1. Freeze the wait card

Write it down before any UI. `python3 honestwait.py init wait-card.json` gives a blank one.

| Field | Ask |
| --- | --- |
| Activity | What is running, in the user's words ("Exporting Q3 report", not "job 8812"). |
| Started by | The user, the system on their behalf, or another person (a caller, a courier). Anything else - a campaign, a re-engagement nudge - stops here: it is not a live status. |
| Duration band | instant < 0.1 s · short < 1 s · medium 1-10 s · long 10 s-2 min · very long 2 min-1 h · hours. The band decides almost everything below. |
| Surface | Where it shows and how much room there is. |
| End states | Which of done / fail / cancel / abandoned can happen, and what each one looks like. |
| Must notice now | The short list of events that justify an interruption. Write it now so nobody adds "50% reached" later. |

Band defaults: **instant** - nothing. **short** - nothing for the first ~0.4 s, then a quiet busy mark (so fast tasks never flash). **medium** - a busy mark plus a label of what is happening. **long** - real progress (rung P2 or higher) and a way to leave. **very long / hours** - progress, a way to leave and come back, and a final state that survives a reload.

### 2. Fill the three slots: Name, Number, Next

Any live status, however small, carries three things. Design them in this order and cut until they fit.

1. **Name** - one mark that says what this is: an icon, a cover, an avatar, a short label. If the user sees only this, do they know which task it is?
2. **Number** - the single value a glance needs: minutes left, 7/24, a score, a gate, a code. Six characters or fewer. If you need two numbers, you have not chosen yet.
3. **Next** - what the user can do (Cancel, Approve, Open) or what happens next ("then emailing it to you"). This lives in the expanded or secondary view.

On a tiny surface (a split capsule, a CLI column) only Name and a shortened Number survive. Decide in advance what the Number shrinks to ("18 min" -> "18", "482 913" -> a ring).

### 3. Climb the progress ladder only as far as your evidence goes

| Rung | Shows | Earned when |
| --- | --- | --- |
| P0 | Nothing | The work ends before the user would wonder. |
| P1 | Busy mark + what is happening ("Contacting server") | You know it is alive but not how far along. |
| P2 | Named stages ("Packing -> Uploading -> Checking") | The work has real, ordered phases. |
| P3 | Counted units ("7 of 24 photos") | You can count finished pieces. |
| P4 | Percentage | The percentage is computed from measured work (bytes, units weighted by size), not from elapsed time. |
| P5 | Time left, as a range ("about 2-3 min") | You have a stable rate over enough of the work. Show a range or round hard; never a precise countdown from a guess. |

Rules on the ladder:
- **Never go backwards silently.** If the count must drop (a retry, a recount), say why in the label ("Retrying photo 12").
- **Give the last step its own stage.** "Finishing up" beats a bar parked at 99%.
- **Smooth the ETA.** Average the rate, update the displayed time at most every few seconds, and only let it jump when you also say why ("Slower connection").
- **Show stalls honestly.** If nothing has changed for a while (8 s is a sane default for a foreground task), switch to a stall label ("Waiting for network...") instead of letting a bar look frozen - or animate a self-ticking value only when the underlying thing really is ticking (a clock, a countdown).
- **Do not fake motion.** An indeterminate shimmer that never changes is fine at P1; a bar that advances on a timer is a lie.

### 4. Script the whole lifecycle

Write one line per event before writing code. Each app event maps to exactly one surface action.

| App event | Surface does |
| --- | --- |
| Starts | Appears (after the short-band delay if relevant) with Name and a first Number or label. |
| Value moves | Updates in place. No animation louder than the change. |
| Value ticks every second | Nothing per tick from your code; the surface draws its own clock. |
| New stage | Swaps the label with a soft transition. |
| Stalls | Shows the stall label; resumes normal state when events return. |
| Needs an answer | Opens and stays open until answered; then closes the question before anything else. |
| Must notice now (failed, arrived, code received) | One interruption: expand briefly or raise a sound/haptic, then settle. |
| Done | Shows the final state long enough to read (about 1-8 s, longer if it carries a result to open), then leaves. |
| Failed | Says what failed and what to do (Retry, Details). Stays until seen or dismissed. |
| Cancelled | Confirms the cancel briefly, then leaves. |
| Abandoned (crash, tab closed, worker died) | On next load, show the last known state as "Interrupted" with a way to resume - never resurrect it as running. |

The script is also your test plan: every row should appear in a recorded trace (step 7).

### 5. Decide who wins when activities collide

Write the order down; do not let it emerge from whatever started first.

1. **Needs an answer** (approve, pay, accept a call)
2. **Failed** and not yet seen
3. **The thing the user is watching** (they just started it, or it is about to finish)
4. **Background work** the user only needs to know exists

Then: show at most two at a time (one main, one secondary) and queue the rest. Activities from the **same source** (three orders from one shop, several runs of one agent) take turns in one slot rather than splitting it. A lower-priority activity should not be starved off the surface for minutes; rotate it in or show a count ("+2").

### 6. Spend the interruption and announcement budget carefully

**Interruptions** (auto-expand, sound, haptic, banner): only for the must-notice-now list from the wait card. A routine budget is two per activity - typically "needs you" and "finished/failed". Never interrupt for progress.

**Screen readers**:
- Put the status text in a polite live region (`role="status"` on the web, or the platform's equivalent). A visual progress bar alone is not announced.
- Announce milestones - start, each stage, roughly every quarter, the end - and keep at least ~10 s between routine announcements.
- Use assertive announcements only for failures and questions.
- Respect reduced-motion settings: replace springs and shimmers with fades or static states.
- Never rely on colour alone for failed vs done; pair it with a word or a mark.

**Privacy**: a live surface is often visible to others (lock screen, shared screen). Show "Payment approved", not the card number; "Code ready - tap to view", not the code, unless the user chose otherwise.

### 7. Record a real trace and replay it

Make the app (or a test) log one JSON line per event: `start`, `update`, `stage`, `alert`, `ask`, `answer`, `announce`, `done`/`fail`/`cancel`, `end`, plus optional `visible` lines saying what the surface showed. Then:

```bash
python3 honestwait.py replay trace.jsonl --card wait-card.json
```

It flags, among others:

| Code | Means |
| --- | --- |
| SILENT_GAP | Nothing visible changed for longer than the stall threshold. |
| BACKWARDS | Progress fell with no stated reason. |
| HANG_AT_99 | Parked near the end with no final stage. |
| ETA_WHIPLASH | The time-left value swung more than 50% within a few seconds. |
| ROUTINE_ALERT / ALERT_SPAM | Interrupting for progress, or more interruptions than the budget. |
| ANNOUNCE_FLOOD / LOUD_ANNOUNCE | Screen-reader chatter, or assertive speech for something routine. |
| FLASH | Shown and gone faster than a person can read. |
| VANISH / LINGER | Final state too short to read, or overstaying. |
| NO_ENDING / GHOST | Removed with no final state, or never removed. |
| UNASKED | Something nobody is waiting on is using the live surface. |
| PRIORITY_FLIP / CROWDED / STARVED | Collision rules broken. |
| UNEARNED_PERCENT (info) | A percentage with no counted units behind it; check rung P4 is really earned. |

**Verdict**: any FAIL -> **MISLEADING** (do not ship); only WARNs -> **SHAKY** (fix or justify each one in the card); nothing -> **STEADY**. Thresholds live in the card's `thresholds` block, so a game timer and a nightly backup can use different numbers.

### 8. Write the result up

Report: the wait card, the Name/Number/Next for each surface size, the chosen rung with its evidence, the lifecycle script, the collision order, the replay verdict with each finding either fixed or justified, and anything you could not test (e.g. real screen reader, slow network).

## Examples

**An agent run in a chat app.** Started by the user, band "very long". Name: the agent's avatar; Number: "step 3/7"; Next: "Stop". Rung P2 (named steps), not P4 - the agent cannot know what fraction is left. Stall label after 8 s without a tool event: "Waiting on search results...". Interruption budget: "needs your approval" and "finished". Several runs of the same agent share one slot and take turns.

**A file export in a desktop app.** Band "long". P4 from bytes written; P5 shown as "about 1 min" only after 20% is done. The final 5% (writing the index) becomes the stage "Finishing up". Done state holds 4 s with "Open" as Next.

**A shaky trace.** `python3 honestwait.py demo` writes a trace that reads MISLEADING: its bar drops from 30% to 26% without a reason, it alerts on progress, a marketing "activity" takes the surface and never leaves, and "Done" vanishes after 0.3 s. Compare with `examples/steady-upload.jsonl`, which handles an incoming call, a retry that lowers the count (with a reason), and a readable ending - STEADY.

## Tips

- Design the failure state first; it is the one that ships broken.
- If you cannot name the Number, you are probably at P1 or P2 - be honest about it.
- Delay showing short tasks; a flicker reads as a glitch.
- Treat "the surface is still showing it" as data that must be cleaned up on crash, logout, and reload.
- A live surface earns trust slowly and loses it in one promo. Keep it for things the user is truly waiting on.
- Keep the trace logger in the product (behind a flag): it turns "it felt stuck" bug reports into replayable evidence.
