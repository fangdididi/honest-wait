#!/usr/bin/env python3
"""honest-wait: replay a recorded live-status trace and flag dishonest or noisy waits.

Commands
  init  [card.json]              write a blank wait card to fill in
  demo  [trace.jsonl]            write a small sample trace with a few problems in it
  replay trace.jsonl [--card card.json] [--json]
                                 check the trace and print findings plus a verdict

Trace format: one JSON object per line, sorted by time.
  {"t": 0.0, "id": "export", "type": "start", "source": "user", "priority": 0}
  {"t": 2.1, "id": "export", "type": "update", "progress": 0.12, "units": [3, 25], "eta": 40}
  {"t": 9.0, "id": "export", "type": "stage", "label": "Uploading"}
  {"t": 9.5, "id": "export", "type": "announce", "text": "Export 40 percent", "politeness": "polite"}
  {"t": 30,  "id": "export", "type": "alert", "reason": "failed"}
  {"t": 31,  "id": "export", "type": "ask"}      / "answer"
  {"t": 40,  "id": "export", "type": "done"}     / "fail" / "cancel"
  {"t": 43,  "id": "export", "type": "end"}      (the surface is gone)
  {"t": 44,  "type": "visible", "ids": ["call", "export"]}   (what the surface showed)
Only "t", "id" and "type" are required. Unknown fields are ignored.
Standard library only. Python 3.8+.
"""
import json, sys

DEFAULTS = {
    "silent_gap_s": 8.0,        # no event and no self-ticking value for this long = looks frozen
    "show_delay_s": 0.4,        # surfaces shown and gone faster than this are a flash
    "done_min_s": 1.0,          # final state must stay at least this long
    "done_max_s": 8.0,          # ...and not overstay
    "eta_whiplash": 0.5,        # ETA moving more than 50% within the window
    "eta_window_s": 10.0,
    "alerts_per_activity": 2,
    "announce_min_gap_s": 10.0,
    "hidden_max_s": 60.0,       # an activity kept off the surface this long while running
    "self_ticking": False,      # true when the surface draws its own clock/countdown
}

CARD = {
    "activity": "what is running, in the user's words (e.g. 'Exporting Q3 report')",
    "started_by": "user | system | other-person",
    "duration_band": "instant(<0.1s) | short(<1s) | medium(1-10s) | long(10s-2min) | very-long(2min-1h) | hours",
    "surface": "pill/island | toast | status bar | inline row | CLI line | lock-screen tile | chat bubble",
    "name_slot": "one mark that says what it is",
    "number_slot": "one glance value, 6 characters or fewer",
    "next_slot": "what the user can do now, or what happens next",
    "progress_rung": "P0..P5 (see SKILL.md), and the evidence that earns it",
    "end_states": ["done", "fail", "cancel", "abandoned"],
    "must_notice_now": ["events that justify an alert; everything else is quiet"],
    "thresholds": DEFAULTS,
}

SAMPLE = [
    {"t": 0.0, "id": "export", "type": "start", "source": "user", "priority": 0},
    {"t": 0.5, "id": "export", "type": "update", "progress": 0.05, "eta": 60},
    {"t": 1.0, "id": "export", "type": "announce", "text": "Export started", "politeness": "polite"},
    {"t": 3.0, "id": "export", "type": "update", "progress": 0.21, "eta": 20},
    {"t": 4.0, "id": "export", "type": "announce", "text": "21 percent", "politeness": "polite"},
    {"t": 6.0, "id": "export", "type": "announce", "text": "30 percent", "politeness": "polite"},
    {"t": 6.0, "id": "export", "type": "update", "progress": 0.30, "eta": 55},
    {"t": 18.0, "id": "export", "type": "update", "progress": 0.26},
    {"t": 18.0, "id": "export", "type": "alert", "reason": "progress"},
    {"t": 20.0, "id": "sync", "type": "start", "source": "system", "priority": 0},
    {"t": 20.1, "id": "sync", "type": "end"},
    {"t": 21.0, "id": "promo", "type": "start", "source": "marketing", "priority": 1},
    {"t": 21.0, "type": "visible", "ids": ["promo", "export"]},
    {"t": 25.0, "id": "export", "type": "update", "progress": 0.99},
    {"t": 40.0, "id": "export", "type": "done"},
    {"t": 40.3, "id": "export", "type": "end"},
]


def load(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                ev = json.loads(line)
            except ValueError as e:
                sys.exit(f"line {n}: not JSON ({e})")
            if "t" not in ev or "type" not in ev:
                sys.exit(f"line {n}: needs 't' and 'type'")
            out.append(ev)
    out.sort(key=lambda e: float(e["t"]))
    return out


def replay(events, th):
    F = []  # (severity, code, id, t, message)
    def add(sev, code, aid, t, msg):
        F.append((sev, code, aid, round(float(t), 2), msg))

    acts = {}
    for ev in events:
        t = float(ev["t"]); aid = ev.get("id"); typ = ev["type"]
        if typ == "visible":
            ids = ev.get("ids", [])
            if len(ids) > 2:
                add("WARN", "CROWDED", ",".join(ids), t, f"{len(ids)} activities on one surface; show two at most and queue the rest")
            if len(ids) == 2:
                a, b = (acts.get(i, {}) for i in ids)
                if a and b and a.get("priority", 0) < b.get("priority", 0):
                    add("WARN", "PRIORITY_FLIP", ids[0], t, f"'{ids[0]}' holds the main spot but '{ids[1]}' has the higher priority")
            for i, st in acts.items():
                if st.get("open"):
                    if i in ids:
                        st["hidden_since"] = None
                    elif st.get("hidden_since") is None:
                        st["hidden_since"] = t
            continue
        if aid is None:
            continue
        st = acts.setdefault(aid, {"open": False, "last": None, "progress": None, "etas": [], "alerts": 0,
                                   "last_announce": None, "final_t": None, "ended": False, "priority": 0,
                                   "hidden_since": None, "start_t": None, "asked": None})
        # silent gap check (before handling the event)
        if st["open"] and st["last"] is not None and not th["self_ticking"] and typ not in ("announce",):
            gap = t - st["last"]
            if gap > th["silent_gap_s"] and st["final_t"] is None:
                add("WARN", "SILENT_GAP", aid, st["last"], f"{gap:.1f}s with no visible change; show a stall state ('Waiting on network...') or a self-ticking value")
        if typ != "announce":
            st["last"] = t
        if st.get("hidden_since") is not None and st["open"] and t - st["hidden_since"] > th["hidden_max_s"]:
            add("WARN", "STARVED", aid, st["hidden_since"], f"running but off the surface for {t - st['hidden_since']:.0f}s")
            st["hidden_since"] = t

        if typ == "start":
            st.update(open=True, start_t=t, priority=ev.get("priority", 0))
            src = ev.get("source", "user")
            if src not in ("user", "system", "other-person"):
                add("FAIL", "UNASKED", aid, t, f"started by '{src}': a live status surface is for something the user is actually waiting on, not promotion")
        elif typ == "update":
            p = ev.get("progress")
            if p is not None:
                if st["progress"] is not None and p < st["progress"] - 1e-9 and not ev.get("reason"):
                    add("FAIL", "BACKWARDS", aid, t, f"progress fell {st['progress']:.0%} -> {p:.0%} with no stated reason; add 'reason' (e.g. 'retrying chunk 4') or a stage change")
                if p >= 0.99 and p < 1:
                    st["stuck99"] = t
                st["pct_seen"] = True
                st["progress"] = p
            if "units" in ev:
                st["units"] = ev["units"]
            if "eta" in ev:
                eta = float(ev["eta"])
                for (pt, pe) in st["etas"]:
                    if t - pt <= th["eta_window_s"]:
                        expected = pe - (t - pt)
                        if expected > 0 and abs(eta - expected) / expected > th["eta_whiplash"]:
                            add("WARN", "ETA_WHIPLASH", aid, t, f"ETA jumped from ~{expected:.0f}s to {eta:.0f}s within {t - pt:.0f}s; smooth it or show a range")
                            break
                st["etas"] = [(pt, pe) for (pt, pe) in st["etas"] if t - pt <= th["eta_window_s"]] + [(t, eta)]
        elif typ == "alert":
            st["alerts"] += 1
            if ev.get("reason") in (None, "progress", "update", "tick"):
                add("FAIL", "ROUTINE_ALERT", aid, t, "alert on routine progress; alerts are for must-notice-now events (failed, arrived, needs an answer)")
            if st["alerts"] > th["alerts_per_activity"]:
                add("WARN", "ALERT_SPAM", aid, t, f"{st['alerts']} alerts for one activity (budget {th['alerts_per_activity']})")
        elif typ == "ask":
            st["asked"] = t
        elif typ == "answer":
            st["asked"] = None
        elif typ == "announce":
            pol = ev.get("politeness", "polite")
            la = st["last_announce"]
            if la is not None and t - la < th["announce_min_gap_s"] and pol != "assertive":
                add("WARN", "ANNOUNCE_FLOOD", aid, t, f"screen-reader announcement {t - la:.1f}s after the last one; announce milestones, not every change")
            if pol == "assertive" and not ev.get("urgent"):
                add("WARN", "LOUD_ANNOUNCE", aid, t, "assertive announcement for a non-urgent change; keep assertive for failures and questions")
            st["last_announce"] = t
        elif typ in ("done", "fail", "cancel"):
            st["final_t"] = t; st["final"] = typ
            if typ == "done" and st["progress"] is not None and st["progress"] < 1 and st.get("stuck99"):
                hang = t - st["stuck99"]
                if hang > th["silent_gap_s"]:
                    add("WARN", "HANG_AT_99", aid, st["stuck99"], f"sat at 99% for {hang:.0f}s; the last step needs its own stage label")
            if st["asked"] is not None:
                add("WARN", "UNANSWERED", aid, t, "finished while a question was still open; close the question first")
        elif typ == "end":
            dur = t - (st["start_t"] if st["start_t"] is not None else t)
            if st["final_t"] is None:
                if dur < th["show_delay_s"]:
                    add("WARN", "FLASH", aid, t, f"shown for {dur:.2f}s then gone; delay showing short tasks by ~{th['show_delay_s']}s")
                else:
                    add("FAIL", "NO_ENDING", aid, t, "surface removed without a done/fail/cancel state; the user can't tell what happened")
            else:
                linger = t - st["final_t"]
                if linger < th["done_min_s"]:
                    add("WARN", "VANISH", aid, t, f"final state shown only {linger:.1f}s; hold it {th['done_min_s']}-{th['done_max_s']}s")
                elif linger > th["done_max_s"]:
                    add("WARN", "LINGER", aid, t, f"final state held {linger:.0f}s; it now occupies the surface for nothing")
            st["open"] = False; st["ended"] = True

    last_t = float(events[-1]["t"]) if events else 0
    for aid, st in acts.items():
        if st["open"]:
            add("FAIL", "GHOST", aid, last_t, "activity never ended; it will sit on the surface after the work is gone")
        if st.get("pct_seen") and not st.get("units"):
            add("INFO", "UNEARNED_PERCENT", aid, st.get("start_t") or 0, "shows a percentage but the trace never reports counted units; make sure the number comes from measured work (rung P4)")
    return F, acts


def verdict(F):
    fails = sum(1 for f in F if f[0] == "FAIL")
    warns = sum(1 for f in F if f[0] == "WARN")
    if fails:
        return "MISLEADING"
    if warns:
        return "SHAKY"
    return "STEADY"


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return 0
    cmd = argv[0]
    if cmd == "init":
        path = argv[1] if len(argv) > 1 else "wait-card.json"
        json.dump(CARD, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"wrote {path}"); return 0
    if cmd == "demo":
        path = argv[1] if len(argv) > 1 else "demo-trace.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            for ev in SAMPLE:
                fh.write(json.dumps(ev) + "\n")
        print(f"wrote {path}; now run: python3 honestwait.py replay {path}"); return 0
    if cmd == "replay":
        if len(argv) < 2:
            sys.exit("usage: honestwait.py replay trace.jsonl [--card card.json] [--json]")
        th = dict(DEFAULTS)
        if "--card" in argv:
            card = json.load(open(argv[argv.index("--card") + 1], encoding="utf-8"))
            th.update({k: v for k, v in card.get("thresholds", {}).items() if k in DEFAULTS})
        events = load(argv[1])
        F, acts = replay(events, th)
        v = verdict(F)
        if "--json" in argv:
            print(json.dumps({"verdict": v, "findings": [dict(zip(("severity", "code", "id", "t", "message"), f)) for f in F]}, indent=2))
            return 0 if v == "STEADY" else 1
        print(f"honest-wait replay: {len(events)} events, {len(acts)} activities")
        for sev, code, aid, t, msg in sorted(F, key=lambda f: (f[3], f[0])):
            print(f"  {sev:<4} {code:<16} {aid:<10} t={t:<7} {msg}")
        if not F:
            print("  no findings")
        print(f"VERDICT: {v}")
        return 0 if v == "STEADY" else 1
    sys.exit(f"unknown command '{cmd}'; try --help")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
