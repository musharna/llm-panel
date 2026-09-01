Review a Python tool for REAL DEFECTS. The complete source is below; you need not look
anything up. Report only defects you can point at, most severe first, each with a concrete
failure scenario (inputs -> wrong behaviour). Do not restate what the code does, do not
praise it, do not propose style refactors. If something looks wrong but is actually correct,
say so rather than padding the list.

WHAT IT IS. `llm-panel` asks several different LLMs (judges) the same question INDEPENDENTLY,
then optionally runs an ANONYMISED rebuttal round where each judge answers the others'
findings without knowing who wrote them. It dispatches to several transports (codex CLI,
opencode, claude CLI, ollama), classifies every failure, accounts for cost, and writes a run
directory: panel.md (assembled prose), <judge>.md, <judge>.rebuttal.md, <judge>.prompt.md,
and run.json (the structured record a separate renderer consumes).

PAY PARTICULAR ATTENTION TO:
1. `ask()` -- the transport dispatcher, and by far the largest function. Session reuse
   (`--thread`), timeouts, streaming, per-transport argument construction. What input makes
   it hang, mis-parse a response, or attribute one judge's output to another?
2. `_classify_error` with PROVIDER_DECLINED / PROVIDER_UNAVAILABLE. The tool prints
   "`harness` failures are OUR plumbing, not the model saying no", so this classification is
   load-bearing: it assigns BLAME. What real error lands in the wrong bucket, and in which
   direction does the mistake fall?
3. `run_rebuttals()` -- ANONYMITY IS A CORRECTNESS PROPERTY, not a nicety. If anything in the
   assembled round-2 prompt lets a judge identify which reviewer wrote which finding (its own
   text quoted back, a stable ordering, a name leaking through a path, a model-specific
   formatting tic), round two is contaminated and the tool cannot say so. Also: what happens
   to a judge that fails in round 1 but is still cited in round 2?
4. `cost_note()` / `summary_table()` -- billed money vs subscription/plan quota. This is where
   the numbers ORIGINATE. Can spend be double-counted, dropped, or attributed to the wrong
   judge? What is written when a transport reports no cost at all?
5. `emit()` and the run.json emission -- this is a CONTRACT with a separate renderer. Which
   fields can be absent or null? A downstream `{j["secs"]:.1f}` already crashed on a null.
6. `agent_can_write()` / MUTATING_TOOLS -- judges must not be able to edit or run anything.
   This is a SECURITY boundary and it has failed before: a config granting write via a `tools`
   key was not caught by a check that only inspected `permission`. What config shape still
   gets through?
7. `consensus_view()` with CITE / BARE_LINE -- citation extraction from free prose.
8. Credential resolution (`stored_providers`, PROVIDER_ENV, HOST_AUTH) and run-directory
   placement (`STATE`, `repo_key`, `thread_key`). A judge silently running unauthenticated,
   or a run landing where nothing can find it, are both real failures.
9. Anywhere a failure is swallowed, or a number is presented as measured when it was not.

Answer as one independent judge; you will not see the others this round. Do not hedge toward
a consensus you cannot see.

--- FILE: llm-panel ---
#!/usr/bin/env python3
"""Put one question to several models independently, then show every answer in full.

Judges never see each other's answers -- that independence is the whole point of a
panel. A judge that fails is REPORTED as failed, never silently dropped: a panel that
quietly loses two judges still looks like a panel.

Failures are reported in two CLASSES, because they license opposite conclusions:
  refused  -- the model/provider said no (out of credits, rate limited, auth).
              That is a fact about the judge.
  harness  -- our own plumbing broke (timeout, state-DB lock, missing binary).
              That is a fact about US, and must never be read as the judge declining.

`refused` is claimed ONLY on a structured provider error, which is positive evidence
we reached the provider and it said no. Everything ambiguous defaults to `harness`,
because the two errors are not symmetric: crediting a model with a refusal it never
made corrupts the panel's finding, while over-blaming our own plumbing just means we
re-run it. (Caught by this rule: a dead ollama daemon first reported as `refused`.)

  llm-panel "question"                     # default roster
  llm-panel --diff "review my changes"     # attach the working-tree diff
  llm-panel --judges codex,big-pickle "q"  # pick the roster
  llm-panel --rebut --diff "review this"    # + a round where judges answer each other
  llm-panel --thread design "..."           # persistent conversation; judges remember
  llm-panel --list                         # print the roster (offline; no network)
  llm-panel --check                        # actually ping each judge and report
  llm-panel --show                         # reprint the last panel

NOT every judge is equally equipped, and it matters when you read the answers:
codex and opencode judges get READ-ONLY access to the repo (they can grep and read
files to check a claim), while ollama judges answer from the prompt ALONE -- that
transport is a plain completion call with no tool loop. An ollama judge saying "I
cannot verify that" means it had no way to look, not that looking failed.

Synthesis is deliberately NOT automatic. Read the disagreements yourself, or pass
--synthesize to have one judge compare the others (it is told which answer is whose).

Why each opencode judge gets its own XDG_DATA_HOME
--------------------------------------------------
Every `opencode run` writes to ONE shared SQLite DB (~/.local/share/opencode/
opencode.db). Run judges in parallel and they contend on it: measured 2026-08-20,
12 concurrent writers produced 1 "database is locked" failure in 24 calls, while the
same 24 calls with per-judge data dirs produced 0. A judge lost that way used to be
printed as DID NOT ANSWER -- blaming the model for our own contention.

The dirs are PERSISTENT, not per-run, and that is load-bearing: a cold data dir must
re-snapshot the repo, measured at 42.5s vs 5.2s on a 24GB repo. Warmed, the same call
took 3.4s. So we pay the cold start once per (judge, repo), then run faster than the
shared DB ever did.

Residual, stated honestly: two llm-panel runs going at once still share a given
judge's dir. That is 2 concurrent writers, far below the 12 that reproduced the lock,
but it is not zero -- and if it ever bites, it is reported as `harness`, not as the
judge refusing.
"""
import argparse, concurrent.futures as cf, datetime, json, os, pathlib, re, shutil, subprocess, sys, time
import base64
import fcntl
import hashlib
import threading
import urllib.error, urllib.request

# name -> (kind, model-id).  kind: "codex" uses the ChatGPT plan; "opencode" uses opencode run.
ROSTER = {
    "codex":       ("codex",    "gpt-5.6-sol"),
    "big-pickle":  ("opencode", "opencode/big-pickle"),
    "nemotron":    ("opencode", "opencode/nemotron-3-ultra-free"),
    "lightning":   ("opencode", "opencode/nemotron-3.5-lightning-free"),
    "deepseek":    ("opencode", "opencode/deepseek-v4-flash-free"),
    "mimo":        ("opencode", "opencode/mimo-v2.5-free"),
    "hy3":         ("opencode", "opencode/hy3-free"),
    "muse":        ("opencode", "opencode/muse-spark-1.2-contributor-free"),
    # Reachable only once HuggingFace credits reset or PRO is bought (they 402 today).
    "glm":         ("opencode", "huggingface/zai-org/GLM-5.2"),
    "qwen":        ("opencode", "huggingface/Qwen/Qwen3-235B-A22B-Thinking-2507"),
    "kimi":        ("opencode", "huggingface/moonshotai/Kimi-K3"),
    "deepseek-pro":("opencode", "huggingface/deepseek-ai/DeepSeek-V4-Pro"),
    # --- OpenRouter: one key covers all of these, and it is the ONLY route to Grok.
    # Needs OPENROUTER_API_KEY in the environment; without it they report `harness`.
    # `or-glm-free` costs nothing, but OpenRouter's :free catalogue ROTATES (Qwen's
    # free tier was delisted in early Aug 2026) -- if it starts failing, check the id
    # before assuming the account is broken.
    "or-glm-free": ("opencode", "openrouter/z-ai/glm-5.2:free"),
    "or-glm":      ("opencode", "openrouter/z-ai/glm-5"),
    "or-grok":     ("opencode", "openrouter/x-ai/grok-4.6"),
    "or-kimi":     ("opencode", "openrouter/moonshotai/kimi-k3"),
    "or-qwen":     ("opencode", "openrouter/qwen/qwen3-235b-a22b-thinking-2507"),
    "or-deepseek": ("opencode", "openrouter/deepseek/deepseek-v3.2"),
    # --- Anthropic through the `claude` CLI, which uses the claude.ai SUBSCRIPTION
    # rather than metered API billing -- the same arrangement as the codex judge on
    # ChatGPT Plus. Verified: with ANTHROPIC_API_KEY unset the CLI answers on the
    # claude.ai login; with it set the CLI itself warns that the key "takes
    # precedence over your claude.ai login", i.e. that path bills per token. So the
    # transport strips the key. Going through opencode's anthropic/* models instead
    # would bill the API at $5/M in, $25/M out.
    # NOT in the default roster: when Claude wrote the work under review, a Claude
    # judge shares the author's blind spots and is not an independent second opinion.
    # --- vision judges (direct OpenRouter HTTP; see VISION note in ask()) -----------
    "vis-grok":      ("orvision", "x-ai/grok-4.6"),
    "vis-kimi":      ("orvision", "moonshotai/kimi-k3"),
    "vis-gemini":    ("orvision", "google/gemini-2.5-flash"),
    "vis-gpt":       ("orvision", "openai/gpt-5.6"),
    "claude-opus":   ("claude",   "opus"),
    "claude-sonnet": ("claude",   "sonnet"),
    # Local; needs `ollama serve` (start it, and stop it when done -- it pins VRAM).
    # `ollama list` returns EMPTY when the daemon is down, which reads as "no models
    # installed" rather than "cannot see them" -- check the daemon before believing it.
    "local-llama": ("ollama",   "llama3.1:latest"),      # 4.9GB, already present
    "local-qwen":  ("ollama",   "qwen3-coder:30b"),      # 19GB, must be pulled first
    "local-small": ("ollama",   "qwen3:0.6b"),           # 522MB, smoke-test only
}

# A judge whose provider key is absent should say so in a second, not burn the whole
# timeout and then look like the model went quiet. Presence is all this checks -- an
# invalid key still fails later, and reports as the provider refusing.
PROVIDER_ENV = {"openrouter/": "OPENROUTER_API_KEY", "huggingface/": "HF_TOKEN"}
# Provider name as it appears in opencode's auth.json, per model-id prefix.
PROVIDER_AUTH = {"openrouter/": "openrouter", "huggingface/": "huggingface"}

# opencode keeps `opencode auth login` credentials at $XDG_DATA_HOME/opencode/auth.json.
# We override XDG_DATA_HOME per judge (see docstring), which would hide those creds from
# every judge -- so capture the REAL location once, at import, before any override.
HOST_AUTH = (pathlib.Path(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"))
             / "opencode" / "auth.json")


def stored_providers():
    """Providers with a credential in the host auth.json. Empty on any read failure."""
    try:
        return set(json.loads(HOST_AUTH.read_text()))
    except Exception:
        return set()
DEFAULT = ["codex", "big-pickle", "nemotron", "deepseek"]

# ollama is deliberately absent: that transport uses the HTTP API, not the CLI.
BINARY = {"codex": "codex", "opencode": "opencode", "claude": "claude"}
STATE = pathlib.Path(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")) / "llm-panel"


def die(msg, code=1):
    sys.stderr.write(f"llm-panel: {msg}\n"); sys.exit(code)


def now():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def strip_ansi(s):
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", s)


def find_session_id(obj, depth=0):
    """Dig a session/thread id out of a codex JSON event. Codex has moved this field
    between releases, so match on any of the known spellings rather than one path."""
    if depth > 6:
        return None
    if isinstance(obj, dict):
        for k in ("session_id", "sessionId", "thread_id", "threadId",
                  "conversation_id", "conversationId"):
            v = obj.get(k)
            if isinstance(v, str) and v:
                return v
        for v in obj.values():
            r = find_session_id(v, depth + 1)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_session_id(v, depth + 1)
            if r:
                return r
    return None


def codex_session_id(session_file, repo):
    """The resumable codex id, or None if we cannot vouch for it.

    Shared by ask() and the "N judges resuming" banner ON PURPOSE: they used to
    disagree, because the banner only asked whether the file was non-empty. It
    therefore announced "1 judge resuming" for a session ask() then refused to
    resume -- a status line reporting the opposite of what happened.
    """
    mark = read_session(session_file)
    if not mark:
        return None
    try:
        rec = json.loads(mark)
    except ValueError:
        return None                      # bare id (old format or hand-edited)
    if rec.get("sandbox") == "read-only" and rec.get("cwd") == repo and rec.get("id"):
        return rec["id"]
    return None


def read_session(f):
    try:
        return f.read_text().strip() or None if f else None
    except OSError:
        return None


def result(name, status, text, secs, meta=None):
    return {"name": name, "status": status, "text": text, "secs": round(secs, 1), "meta": meta or {}}


STREAM_ECHO = False       # set by --stream


class _LineEcho:
    """Echo streamed chunks to the console, one whole line at a time, per judge.

    Judges stream CONCURRENTLY onto one terminal, so echoing raw chunks the moment
    they arrive interleaves two models mid-word and the transcript is unreadable.
    Buffering per judge and flushing only on a newline keeps each line attributable.
    Echo goes to stderr because stdout carries panel.md at the end -- piping the
    report to a file must not collect the live chatter as well.
    """

    def __init__(self):
        self.buf, self.lock = {}, threading.Lock()

    def feed(self, judge, piece):
        with self.lock:
            *lines, rest = (self.buf.get(judge, "") + piece).split("\n")
            self.buf[judge] = rest
            for ln in lines:
                sys.stderr.write(f"  [{judge}] {ln}\n")
            if lines:
                sys.stderr.flush()

    def close(self, judge):
        """Flush a trailing partial line: the last chunk rarely ends in a newline."""
        with self.lock:
            rest = self.buf.pop(judge, "")
        if rest.strip():
            sys.stderr.write(f"  [{judge}] {rest}\n")
            sys.stderr.flush()


ECHO = _LineEcho()


def write_live(live_path, piece, judge=None):
    """Append one streamed chunk to <judge>.live.md, and echo it if --stream is on.

    A failed write here must never kill a judge that is answering correctly: the
    live file is a convenience for watching, not the record. The record is the
    <judge>.md written by emit() when the answer completes.
    """
    if live_path is not None:
        try:
            with open(live_path, "a") as lf:
                lf.write(piece)
        except OSError:
            pass
    if STREAM_ECHO and judge:
        ECHO.feed(judge, piece)


def emit(rundir, judge, prompt, res, live, tag=""):
    """Persist one judge's INPUT and OUTPUT the moment it finishes, and echo if --live.

    Both halves matter. The per-judge prompt was never saved, so for the rebuttal
    round -- where every judge gets a DIFFERENT prompt containing the others'
    anonymised reviews -- there was no way to answer "what did this judge actually
    see?" after the fact. Writing on completion rather than at the end also means a
    panel killed halfway still leaves the answers it did collect.
    """
    (rundir / f"{judge}{tag}.prompt.md").write_text(prompt)
    (rundir / f"{judge}{tag}.md").write_text(res["text"] or "")
    if live:
        head = f"\n===== {judge}{tag} — {res['status']} in {res['secs']}s ====="
        sys.stdout.write(f"{head}\n{res['text']}\n")
        sys.stdout.flush()


# HTTP statuses that genuinely mean "we reached the provider and it declined":
# auth, payment, policy, rate limit. Everything else -- a bad model id (404), a
# malformed request (400), a provider outage (5xx), or a non-API error such as a
# config error -- is OUR mistake or the provider FAILING, neither of which is a
# judgment about the question. Unknown codes default to `harness`, the safe
# direction. Structuredness alone never proved refusal: under the old rule a
# stale roster id would have been reported as the model saying no.
PROVIDER_DECLINED = {401: "auth rejected", 402: "out of credits",
                     403: "forbidden by the provider"}
# Retryable: the provider was reached and would not serve RIGHT NOW. This is not a
# judgment about the question (so not `refused`) and not necessarily our bug (so not
# `harness`) -- a 429 can equally be this panel's own parallel launches hitting one
# provider at once. We cannot tell which from the response, so we say so and report
# how many judges in THIS run shared that provider, which is the evidence a reader
# needs to decide whether to blame us.
PROVIDER_UNAVAILABLE = {429: "rate limited", 503: "service unavailable",
                        529: "overloaded"}


def _classify_error(name, err, secs, meta, peers=1):
    status = err.get("status")
    label = f"{err['name'] or 'error'}" + (f" {status}" if status else "")
    if status in PROVIDER_DECLINED:
        return result(name, "refused", f"{label} ({PROVIDER_DECLINED[status]}): "
                      f"{err['message']}", secs, meta)
    if status in PROVIDER_UNAVAILABLE:
        blame = (f" This run sent {peers} judges to that provider at once, so it may be "
                 f"self-inflicted; re-running with fewer judges would tell you."
                 if peers > 1 else " Only this judge used that provider in this run.")
        return result(name, "unavailable", f"{label} ({PROVIDER_UNAVAILABLE[status]}): "
                      f"{err['message']}{blame}", secs, meta)
    return result(name, "harness", f"{label}: {err['message']} -- this is a transport or "
                  f"configuration failure on our side, not the model declining.", secs, meta)


EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


def ask(name, prompt, repo, timeout, agent="panelist", session_file=None,
        keep_alive="60s", peers=1, live_path=None, effort=None, images=None,
        vision_check=None):
    """Return a result dict. Never raises -- a judge's failure is data, not an exception.

    status: "ok" | "refused" (the model/provider said no) | "harness" (our plumbing broke).
    """
    kind, model = ROSTER[name]
    t0 = time.time()
    if images and vision_check:
        prompt = (f"BEFORE ANYTHING ELSE, quote verbatim on its own first line the exact "
                  f"text of: {vision_check}. If you cannot read it in the image, write "
                  f"CANNOT_SEE and stop.\n\n{prompt}")
    if images and kind not in ("orvision", "claude"):
        return result(name, "unavailable",
                      f"this judge cannot receive images: the {kind} transport does not "
                      f"forward them as vision content (verified -- grok and kimi answer "
                      f"CANNOT_SEE through opencode while reading the same image correctly "
                      f"over the raw API). Use vis-grok / vis-kimi / vis-gemini / vis-gpt or "
                      f"a claude judge for visual questions.", time.time() - t0)
    try:
        if kind == "codex":
            # `exec resume` accepts neither -C nor -s: it inherits cwd and sandbox from
            # the recorded session, and passing them is an error. Hence two flag sets.
            # codex validates this: "minimal" is REJECTED, low/medium/high/xhigh/max
            # are accepted (probed). High stays the default -- a judge that reasons
            # less is a cheaper judge, not a faster one to trust.
            base = ["--json", "--skip-git-repo-check",
                    "-c", f"model_reasoning_effort={effort or 'high'}"]
            # `exec resume` inherits the RECORDED cwd and sandbox, so resuming an id we
            # cannot vouch for silently hands the judge whatever sandbox that session was
            # created with. We therefore store a marker beside the id and refuse to resume
            # unless WE created it, read-only, for THIS repo. A bare id (old format, or
            # hand-edited) is not resumable -- we start a fresh sandboxed session instead.
            sid = codex_session_id(session_file, repo)
            if sid:
                cmd = ["codex", "exec", "resume"] + base + ["-m", model, sid, prompt]
            else:
                cmd = ["codex", "exec"] + base + ["-C", repo, "-s", "read-only", "-m", model, prompt]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               stdin=subprocess.DEVNULL)
            if r.returncode != 0:
                # Ambiguous exits default to `harness`: see classification note above.
                return result(name, "harness", f"codex exec exited {r.returncode}: "
                              f"{r.stderr.strip()[:500]}", time.time() - t0)
            out = None
            for line in r.stdout.splitlines():
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                m = ev.get("msg") if isinstance(ev.get("msg"), dict) else ev
                item = m.get("item") or {}
                if item.get("type") in ("agent_message", "assistant_message") and item.get("text"):
                    out = item["text"]
                for k in ("message", "text", "last_agent_message"):
                    if m.get("type") in ("agent_message", "agent-message") and isinstance(m.get(k), str):
                        out = m[k]
                if session_file is not None and not sid:
                    got = find_session_id(ev)
                    if got:
                        session_file.parent.mkdir(parents=True, exist_ok=True)
                        session_file.write_text(json.dumps(
                            {"id": got, "sandbox": "read-only", "cwd": repo, "model": model}))
                        sid = got
            if out:
                return result(name, "ok", out, time.time() - t0)
            return result(name, "harness", "codex produced no agent message", time.time() - t0)

        if kind == "orvision":
            # Direct OpenRouter chat/completions with an image_url content block.
            # Verified 2026-08-21 against ground truth (a 3-column table + "PROMPTS"
            # sidebar): grok-4.6, kimi-k3, gemini-2.5-flash and gpt-5.6 all read it
            # correctly. deepseek-v3.2, qwen3-235b and glm-5/5.2 return
            # 404 "No endpoints found that support image input" -- they are text-only.
            key = os.environ.get("OPENROUTER_API_KEY")
            if not key:
                return result(name, "harness", "no $OPENROUTER_API_KEY for the vision "
                              "transport (it talks to OpenRouter directly, not through "
                              "opencode)", time.time() - t0)
            content = [{"type": "text", "text": prompt}]
            for img in (images or []):
                try:
                    b64 = base64.b64encode(pathlib.Path(img).read_bytes()).decode()
                except OSError as e:
                    return result(name, "harness", f"cannot read image {img}: {e}",
                                  time.time() - t0)
                suffix = pathlib.Path(img).suffix.lower().lstrip(".") or "png"
                mime = {"jpg": "jpeg"}.get(suffix, suffix)
                content.append({"type": "image_url",
                                "image_url": {"url": f"data:image/{mime};base64,{b64}"}})
            payload = json.dumps({"model": model, "max_tokens": 16000,
                                  "messages": [{"role": "user", "content": content}]}).encode()
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions", data=payload,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    d = json.load(resp)
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")[:300]
                # A model with no image endpoint says so plainly; that is the provider
                # declining, not our plumbing breaking.
                if "image input" in body or e.code in PROVIDER_DECLINED:
                    return result(name, "refused", f"OpenRouter {e.code}: {body}",
                                  time.time() - t0)
                return result(name, "harness", f"OpenRouter {e.code}: {body}", time.time() - t0)
            except urllib.error.URLError as e:
                return result(name, "harness", f"cannot reach OpenRouter ({e.reason})",
                              time.time() - t0)
            ch = (d.get("choices") or [{}])[0]
            text = ((ch.get("message") or {}).get("content") or "").strip()
            u = d.get("usage") or {}
            meta = {"tokens": {"input": u.get("prompt_tokens") or 0,
                               "output": u.get("completion_tokens") or 0},
                    "cost": (d.get("usage") or {}).get("cost")}
            if not text:
                return result(name, "harness", f"empty response (finish_reason="
                              f"{ch.get('finish_reason')})", time.time() - t0, meta)
            if ch.get("finish_reason") not in (None, "stop", "end_turn"):
                meta["note"] = f"finish_reason {ch.get('finish_reason')!r}"
                return result(name, "incomplete", text, time.time() - t0, meta)
            return result(name, "ok", text, time.time() - t0, meta)

        if kind == "claude":
            # ANTHROPIC_API_KEY is REMOVED so this runs on the subscription.
            # --disallowedTools is what actually sandboxes it: --allowedTools is an
            # auto-approve allowlist, not a restriction, and a judge given
            # "Read,Grep,Glob" that way still created a file when asked (verified).
            env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
            # stream-json + --include-partial-messages is what makes a Claude judge
            # watchable, and it costs nothing to use: the run STILL ends with the same
            # `result` event carrying total_cost_usd, session_id, usage and stop_reason.
            # An earlier version used plain `--output-format json` on the belief that
            # only it reported cost -- that was simply wrong (verified: identical
            # result-event keys, 7 text deltas alongside them).
            if images:
                # Verified: a claude judge reads a PNG with its Read tool and reports its
                # contents correctly. It needs the path, so name the files explicitly.
                paths = "\n".join(str(pathlib.Path(i).resolve()) for i in images)
                prompt = (f"{prompt}\n\n---\nUse your Read tool on each of these image "
                          f"files before answering, and say what you actually see:\n{paths}")
            cmd = [BINARY["claude"], "-p", prompt,
                   "--output-format", "stream-json", "--verbose",
                   "--include-partial-messages",
                   "--model", model,
                   "--disallowedTools", "Write,Edit,NotebookEdit,Bash"]
            if effort:                       # same five levels as codex, verified
                cmd += ["--effort", effort]
            sid = read_session(session_file)
            if sid:
                cmd += ["--resume", sid]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, cwd=repo, env=env, stdin=subprocess.DEVNULL)
            # stderr is drained on its own thread. Reading it only after stdout is
            # exhausted would deadlock the moment claude writes more than a pipe
            # buffer's worth of warnings while we are still consuming deltas.
            errbuf = []
            th = threading.Thread(
                target=lambda: errbuf.extend(p.stderr), daemon=True)
            th.start()
            # subprocess.run(timeout=) is gone with the streaming loop, so the deadline
            # becomes an explicit watchdog. It raises the SAME TimeoutExpired the
            # handler below already knows how to report, with the partial answer
            # attached, so a slow judge still tells you what it managed to say.
            d, deltas = {}, []
            killer = threading.Timer(timeout, p.kill)
            killer.start()
            try:
                for line in p.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if ev.get("type") == "stream_event":
                        se = ev.get("event") or {}
                        if se.get("type") == "content_block_delta":
                            piece = (se.get("delta") or {}).get("text") or ""
                            if piece:
                                deltas.append(piece)
                                write_live(live_path, piece, name)
                    elif ev.get("type") == "result":
                        d = ev
                p.wait()
            finally:
                killer.cancel()
                if STREAM_ECHO:
                    ECHO.close(name)
            if not d:
                if p.returncode is not None and p.returncode < 0:
                    raise subprocess.TimeoutExpired(cmd, timeout,
                                                    output="".join(deltas))
                th.join(timeout=2)
                return result(name, "harness", f"claude produced no result event (exit "
                              f"{p.returncode}): "
                              f"{strip_ansi(''.join(errbuf))[-300:]}", time.time() - t0)
            u = d.get("usage") or {}
            meta = {"tokens": {"input": (u.get("input_tokens") or 0)
                                        + (u.get("cache_read_input_tokens") or 0)
                                        + (u.get("cache_creation_input_tokens") or 0),
                               "output": u.get("output_tokens") or 0},
                    "cost": d.get("total_cost_usd"), "billing": "subscription"}
            if session_file is not None and d.get("session_id"):
                session_file.parent.mkdir(parents=True, exist_ok=True)
                session_file.write_text(d["session_id"])
            text = (d.get("result") or "").strip()
            if d.get("is_error"):
                return result(name, "harness", f"claude reported an error: {text[:400]}",
                              time.time() - t0, meta)
            stop = d.get("stop_reason")
            if text and stop not in (None, "end_turn", "stop"):
                meta["note"] = f"stop_reason {stop!r}, not 'end_turn'"
                return result(name, "incomplete", text, time.time() - t0, meta)
            if not text:
                return result(name, "harness", "claude returned an empty result",
                              time.time() - t0, meta)
            return result(name, "ok", text, time.time() - t0, meta)

        if kind == "ollama":
            # Use the HTTP API, NOT `ollama run`. The CLI streams through a terminal
            # renderer and emits cursor-control codes even when piped -- a real answer
            # came back as "catches all exceptions with\x1b[4D\x1b[K\nwith a bare".
            # Those codes mean "back up 4 columns and erase", so stripping them naively
            # DUPLICATES the overwritten text rather than cleaning it. The API returns
            # the string itself, plus token counts, and a `context` we can replay.
            host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
            if not host.startswith("http"):
                host = "http://" + host
            # keep_alive: qwen3-coder:30b holds 21GB of a 24GB card, and this GPU is
            # shared with other sessions' work. Ollama's default is 5m resident AFTER the
            # answer is returned, which monopolises the card for nothing. Hold briefly by
            # default; --keep-alive raises it when you are mid-conversation on a thread.
            # stream=True: this and the claude transport are the two that can stream.
            # opencode emits its whole answer as a single JSON text event and codex
            # emits only item.completed (re-verified: 4 events, zero deltas), so there
            # is nothing to follow there. Chunks are appended to <judge>.live.md as
            # they arrive, which is what `tail -f` needs to show a judge thinking.
            payload = {"model": model, "prompt": prompt, "stream": True,
                       "keep_alive": keep_alive}
            if session_file is not None:                     # ollama resumes by replaying
                try:                                          # the opaque context array
                    ctx = json.loads(session_file.read_text())
                    if isinstance(ctx, list) and ctx:
                        payload["context"] = ctx
                except (OSError, ValueError):
                    pass
            req = urllib.request.Request(f"{host}/api/generate",
                                         data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
            try:
                chunks, d = [], {}
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    for raw_line in resp:
                        if not raw_line.strip():
                            continue
                        d = json.loads(raw_line.decode())
                        piece = d.get("response") or ""
                        if piece:
                            chunks.append(piece)
                            write_live(live_path, piece, name)
                d["response"] = "".join(chunks)
                if STREAM_ECHO:
                    ECHO.close(name)
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")[:300]
                return result(name, "harness", f"ollama HTTP {e.code}: {body} "
                              f"(is the model pulled? `ollama pull {model}`)", time.time() - t0)
            except urllib.error.URLError as e:
                return result(name, "harness", f"cannot reach the ollama daemon at {host} "
                              f"({e.reason}). Start it with `ollama serve`.", time.time() - t0)
            if session_file is not None and isinstance(d.get("context"), list):
                session_file.parent.mkdir(parents=True, exist_ok=True)
                session_file.write_text(json.dumps(d["context"]))
            meta = {"tokens": {"input": d.get("prompt_eval_count") or 0,
                               "output": d.get("eval_count") or 0}, "cost": 0}
            text = (d.get("response") or "").strip()
            if not text:
                return result(name, "harness", f"ollama returned an empty response "
                              f"(done_reason={d.get('done_reason')})", time.time() - t0, meta)
            return result(name, "ok", text, time.time() - t0, meta)

        # --- opencode ---------------------------------------------------------
        # Own data dir: see the module docstring. Without it, parallel judges
        # contend on one SQLite DB and a loser looks like a judge that declined.
        # Credentials can arrive two ways -- an env var, or `opencode auth login`. A guard
        # that only knew about the env var would call a perfectly good stored credential
        # "missing", so check both before declaring a judge unreachable.
        for prefix, var in PROVIDER_ENV.items():
            if model.startswith(prefix) and not os.environ.get(var) \
                    and PROVIDER_AUTH[prefix] not in stored_providers():
                return result(name, "harness", f"no credential for {PROVIDER_AUTH[prefix]}: "
                              f"neither ${var} in the environment nor an entry in "
                              f"{HOST_AUTH}. This is a missing key on our side, not a "
                              f"refusal by the model.", time.time() - t0)
        env = dict(os.environ)
        statedir = STATE / "state" / name
        statedir.mkdir(parents=True, exist_ok=True)
        # Carry the host credentials into the isolated dir, or `opencode auth login` keys
        # would be invisible to every judge. Re-copied when the source changes, so a
        # refreshed/rotated token propagates on the next run.
        if HOST_AUTH.is_file():
            dest = statedir / "opencode" / "auth.json"
            try:
                if not dest.is_file() or dest.stat().st_mtime < HOST_AUTH.stat().st_mtime:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(HOST_AUTH, dest)
            except OSError:
                pass  # fall through; the provider will report the failure honestly
        env["XDG_DATA_HOME"] = str(statedir)
        # --format json: parse events structurally. The old parser stripped ANSI and
        # dropped lines starting with ">"/"@", then flagged failure on the SUBSTRING
        # "Error:" -- so a reviewer whose first sentence quoted an error message was
        # marked FAILED and their whole review discarded.
        # --agent: judges must not be able to edit the repo they are judging.
        # opencode's DEFAULT agent is `build`, which has write tools -- verified
        # 2026-08-20 by asking a judge to create a file in a scratch repo, which it
        # did. The panel runs judges concurrently in a live working tree, so this
        # is not hypothetical. `panelist` (opencode.jsonc) denies edit/bash/webfetch.
        cmd = ["opencode", "run", "--format", "json", "--agent", agent, "-m", model]
        if effort:
            # opencode calls this a "variant" and it is PROVIDER-specific, so unlike
            # codex/claude the level is passed through rather than validated here.
            # Accepted is not the same as honoured: a model with no reasoning setting
            # takes the flag and ignores it, and opencode reports no error either way.
            cmd += ["--variant", effort]
        sid = read_session(session_file)
        if sid:
            cmd += ["-s", sid]          # verified to survive across processes
        r = subprocess.run(cmd + [prompt], capture_output=True, text=True,
                           timeout=timeout, cwd=repo, env=env, stdin=subprocess.DEVNULL)
        texts, err, meta = [], None, {}
        for line in r.stdout.splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            typ, part = ev.get("type"), (ev.get("part") or {})
            if session_file is not None and not sid and ev.get("sessionID"):
                sid = ev["sessionID"]
                session_file.parent.mkdir(parents=True, exist_ok=True)
                session_file.write_text(sid)
            if typ == "text" and part.get("text"):
                texts.append(part["text"])
            elif typ == "error":
                e = ev.get("error") or {}
                d = e.get("data") if isinstance(e.get("data"), dict) else {}
                err = {"name": e.get("name"), "status": d.get("statusCode"),
                       "message": d.get("message") or str(e)[:400]}
            elif typ == "step_finish":
                # The provider's OWN finish reason. "stop" means it said its piece;
                # "tool-calls" or "length" mean it was cut off mid-work. Judged by
                # length instead, a legitimate one-line answer and a truncated
                # preamble are indistinguishable -- grok returned 159 bytes of
                # "I'll inspect the source..." and was counted as a full view.
                if part.get("reason"):
                    meta["finish"] = part["reason"]
                # An agentic judge takes MANY steps (read, grep, read, answer) and each
                # emits its own step_finish. Overwriting kept only the LAST step, which
                # reported "858 in / 8741 out" for a run that had just read a whole repo.
                # Sum instead: every step is a separate billed call.
                if isinstance(part.get("tokens"), dict):
                    tot = meta.setdefault("tokens", {"input": 0, "output": 0})
                    for k in ("input", "output"):
                        tot[k] += part["tokens"].get(k) or 0
                    meta["steps"] = meta.get("steps", 0) + 1
                if part.get("cost") is not None:
                    meta["cost"] = meta.get("cost", 0) + part["cost"]
        body = "\n".join(texts).strip()
        raw = strip_ansi(r.stdout + r.stderr)
        # opencode's OWN messages are plain lines; every event it emits under
        # --format json is a JSON object. Scanning `raw` for opencode's warnings
        # therefore also scanned the model's answer and its tool output -- and the
        # source under review contains the literal guard string, so any judge that
        # READ the file it was reviewing had its answer discarded as "unsandboxed".
        # Observed live: two rebuttals destroyed this way. Match chrome only.
        chrome = "\n".join(l for l in raw.splitlines()
                           if l.strip() and not l.lstrip().startswith("{")).lower()

        # --- classification -------------------------------------------------
        # Order matters and each step answers a DIFFERENT question:
        #   1. was the judge sandboxed at all?   (if not, nothing it says counts)
        #   2. did its answer COMPLETE?          (text + no error + clean exit)
        #   3. if there is no answer, whose fault is that?
        # The previous version was a flat sequence of substring tests over the raw
        # stream, so a lock message printed AFTER a finished review threw the review
        # away (measured: 67,517 tokens over 8 steps, discarded), while a non-empty
        # body short-circuited a fatal error and shipped a truncated review as whole.
        #
        # opencode does not FAIL on a bad --agent: it warns and silently falls back
        # to `build`, which can write to the repo. An answer produced that way came
        # from an agent we did not sandbox, so refuse it rather than print it as a
        # clean review. (This fired for real: `panelist` was declared mode:subagent,
        # which `run --agent` rejects, so every judge silently ran write-capable.)
        if "falling back to default agent" in chrome:
            # Quote opencode's own line. This fires intermittently under concurrent
            # launches and has never reproduced on demand (12/12 clean when probed),
            # so the one occurrence we DO get must carry its own evidence rather than
            # a generic message that tells the next investigator nothing.
            said = next((l.strip() for l in raw.splitlines()
                         if "falling back" in l.lower()
                         and not l.lstrip().startswith("{")), "")
            return result(name, "harness", f"opencode ignored --agent {agent} and fell back to "
                          f"the default (write-capable) agent, so this judge was NOT sandboxed "
                          f"and its answer is discarded. opencode said: {said!r}. Known causes: "
                          f"the agent is declared a subagent (run --agent needs a PRIMARY "
                          f"one), or an intermittent failure under concurrent launches that "
                          f"has never reproduced on demand -- re-running alone usually works.",
                          time.time() - t0, meta)
        # 2. Did it finish? An answer is complete only if nothing else went wrong.
        unfinished = meta.get("finish") not in (None, "stop")
        broke = err is not None or r.returncode != 0 or unfinished
        if body and not broke:
            return result(name, "ok", body, time.time() - t0, meta)
        if body and broke:
            if err:
                why = (f"{err['name'] or 'error'}"
                       + (f" {err['status']}" if err.get("status") else "")
                       + f": {err['message']}")
            elif unfinished:
                why = (f"the provider stopped with reason {meta['finish']!r}, not 'stop' -- "
                       f"the judge was cut off before it finished answering")
            else:
                why = f"exited {r.returncode}"
            meta["note"] = why
            # Keep the text -- it may be most of a good review -- but never let a
            # truncated answer be counted as an answer.
            return result(name, "incomplete", body, time.time() - t0, meta)

        # 3. No answer at all. Whose fault?
        if "database is locked" in chrome:
            return result(name, "harness", "opencode's state DB was locked (parallel-run "
                          "contention on our side, NOT a refusal by this model)",
                          time.time() - t0, meta)
        if err:
            return _classify_error(name, err, time.time() - t0, meta, peers)
        detail = raw.strip()[:600] or f"exited {r.returncode} with no output"
        return result(name, "harness", detail, time.time() - t0, meta)

    except subprocess.TimeoutExpired as e:
        def tail(b):
            if not b:
                return ""
            txt = b.decode("utf-8", "replace") if isinstance(b, bytes) else str(b)
            return strip_ansi(txt).strip()[-400:]
        partial = tail(e.stdout) or tail(e.stderr)
        note = f" Last output before the timeout: {partial!r}" if partial else \
               " The process produced NO output at all before the timeout."
        return result(name, "harness", f"timed out after {timeout}s (our limit, not a "
                      f"refusal).{note}", time.time() - t0)
    except FileNotFoundError as e:
        return result(name, "harness", f"transport missing: {e}", time.time() - t0)
    except Exception as e:  # never let one judge's crash take down the panel
        return result(name, "harness", f"{type(e).__name__}: {e}", time.time() - t0)


REBUT_INSTRUCTIONS = (
    "You already reviewed this material independently. Below are the findings of the OTHER "
    "reviewers. They did not see your review, and their identities are withheld from you on "
    "purpose.\n\n"
    "Each reviewer NUMBERED their findings. Refer to one as <Letter><number> -- B7 is "
    "Reviewer B's finding 7. Take a position on each finding that touches yours:\n"
    "  UPHOLD:  B7 -- you stand by your own claim despite theirs; say what proves it.\n"
    "  REJECT:  B7 -- theirs is wrong or overstated; point at the specific code or "
    "logic that makes it wrong.\n"
    "  CONCEDE: B7 -- you were wrong; say exactly what changed your mind.\n"
    "  MISSED:  B7 -- they caught something real that you did not; confirm it against "
    "the code rather than taking their word.\n\n"
    "Start each point with one of those four labels verbatim, then the reference, THEN your "
    "argument. Cite the reference even when you also describe the finding: a position that "
    "only restates a finding in your own words cannot be matched to the finding it answers, "
    "so it is dropped from the panel's grouped view and argues with nobody.\n\n"
    "Two rules that matter more than agreeing:\n"
    "1. Do NOT concede merely because someone disagreed with you. Concede only when you can "
    "point at what proves you wrong. A correct finding stays correct when it is unpopular.\n"
    "2. Do NOT invent agreement. If a finding is unverifiable from what you have, say so "
    "instead of endorsing it.\n\n"
    "Reviews from the other reviewers follow.\n\n")


# New feature, not a bug fix: ROOT_CAUSE_OK
# Filesystem writes below are read back live after a real run: # BOUNDARY_OK
def run_rebuttals(judges, results, prompt, repo, timeout, agent, rundir, log, live=False,
                  effort=None, images=None):
    """Round 2: each judge answers the OTHERS' findings. Round 1 is never overwritten.

    Judges see each other ANONYMIZED. Naming the models invites deference to whichever
    one is famous or expensive, which is the opposite of what a panel is for -- the point
    is to weigh the argument, not the byline. The legend is printed for the READER, who
    does need to know who said what.
    """
    answered = [j for j in judges if results[j]["status"] == "ok"]
    if len(answered) < 2:
        return ["", "_Rebuttal round skipped: it needs at least two answers to argue about._"], {}
    letters = {j: chr(ord("A") + i) for i, j in enumerate(answered)}

    prompts = {}

    def one(me):
        others = [o for o in answered if o != me]
        blocks = "\n\n".join(f"### Reviewer {letters[o]}\n{results[o]['text']}" for o in others)
        # session_file=None ON PURPOSE. Rebuttals used to run inside the judge's
        # --thread session, which wrote the OTHER judges' findings into its history:
        # on the next turn its "independent" answer had already read everyone else's,
        # destroying the one property the panel exists to provide. The judge's own
        # review is replayed in the prompt instead, so it keeps its context without
        # the thread ever recording what its rivals said.
        prompts[me] = (f"{prompt}\n\n---\n\nYour own review was:\n\n{results[me]['text']}"
                       f"\n\n---\n\n{REBUT_INSTRUCTIONS}{blocks}")
        r = ask(me, prompts[me], repo, timeout, agent, None, "60s",
                sum(1 for k in answered if provider_of(k) == provider_of(me)),
                None, effort, images)
        emit(rundir, me, prompts[me], r, live, tag=".rebuttal")
        return r

    log(f"llm-panel: rebuttal round — {len(answered)} judges answering each other\n")
    with cf.ThreadPoolExecutor(max_workers=len(answered)) as ex:
        rebuts = {r["name"]: r for r in [f.result() for f in [ex.submit(one, j) for j in answered]]}

    out = ["\n---\n", "## Rebuttal round", "",
           "Round 1 above is untouched. Here each judge answers the others' findings, having "
           "been shown them anonymously.", "",
           "Legend (withheld from the judges, shown to you): "
           + ", ".join(f"Reviewer {letters[j]} = {j}" for j in answered), ""]
    for j in answered:
        r = rebuts[j]
        out += [f"\n### {j} (Reviewer {letters[j]}) responds — {r['secs']}s", ""]
        # Mirror the main renderer. It used to print anything that was not ok/refused
        # as "our harness failed", so a rate-limited rebuttal was blamed on us and an
        # `incomplete` one had its partial text thrown away.
        if r["status"] == "ok":
            out += [r["text"], ""]
        elif r["status"] == "incomplete":
            out += [f"**PARTIAL REBUTTAL — cut off ({r['meta'].get('note', 'unknown')}).**",
                    "", r["text"], ""]
        elif r["status"] == "refused":
            out += [f"**NO REBUTTAL — the model/provider refused.** {r['text']}", ""]
        elif r["status"] == "unavailable":
            out += [f"**NO REBUTTAL — the provider would not serve right now.** "
                    f"{r['text']}", ""]
        else:
            out += [f"**NO REBUTTAL — our harness failed, not the model.** {r['text']}", ""]


    # A concession under evidence and a concession under social pressure look identical
    # in the tally, so count but do not interpret.
    tally = {}
    for j in answered:
        if rebuts[j]["status"] != "ok":
            continue
        # Colon OR em/en dash, with an optional qualifier. The old rf"^\s*\**{k}:" counted
        # 3 of one judge's 57 positions because it wrote "MISSED — ..." rather than
        # "MISSED: ...". A bare hyphen is excluded on purpose ("REJECT-worthy ...").
        counts = {k: len(re.findall(rf"^\s*\**{k}\**[^:\u2014\u2013]{{0,24}}?\s*[:\u2014\u2013]\s",
                                    rebuts[j]["text"], re.M | re.I))
                  for k in ("UPHOLD", "REJECT", "CONCEDE", "MISSED")}
        if any(counts.values()):
            tally[j] = counts
    if tally:
        out += ["", "**Positions taken** (labels the judges used; a concession may be evidence "
                "OR deference — read the text to tell which):", ""]
        for j, c in tally.items():
            out += [f"- {j}: " + ", ".join(f"{k.lower()} {v}" for k, v in c.items() if v)]
    return out, rebuts


def collect_diff(repo):
    def git(*a):
        r = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)
        if r.returncode != 0:
            die(f"git {' '.join(a)} failed: {r.stderr.strip()[:300]}", 7)
        return r.stdout
    # `git diff HEAD` fails outright before the first commit, so --diff could not
    # review a brand-new repository at all. Staged-vs-empty-tree works either way.
    has_head = subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "HEAD"],
                              capture_output=True).returncode == 0
    diff = git("diff", "HEAD") if has_head else git("diff", "--cached")
    untracked = git("ls-files", "--others", "--exclude-standard")
    if not diff.strip() and not untracked.strip():
        die("--diff found no uncommitted changes; nothing to review", 8)
    out = ["Here are the uncommitted changes in this repository. Review them.", "",
           "```diff", diff.rstrip(), "```"]
    files = [f for f in untracked.splitlines() if f.strip()]
    if files:
        # The prompt tells judges these ARE the uncommitted changes, so sending bare
        # filenames meant a brand-new file -- the likeliest place for a fresh defect --
        # was reviewed by nobody while the panel looked complete.
        out += ["", "Untracked files (new, not yet in git):"]
        shown, budget = 0, 200_000
        for f in files:
            if shown >= 40 or budget <= 0:
                out += ["", f"... and {len(files) - shown} more untracked files not shown"]
                break
            try:
                # Read at most the cap. The previous version read the WHOLE file and
                # truncated afterwards, so one stray multi-GB untracked file would be
                # pulled into memory before the budget was ever consulted.
                with open(pathlib.Path(repo) / f, encoding="utf-8", errors="replace") as fh:
                    data = fh.read(20_000)
                    if fh.read(1):
                        data += "\n... [truncated]"
            except (OSError, IsADirectoryError):
                out += ["", f"--- {f} (unreadable or not text) ---"]
                shown += 1
                continue
            budget -= len(data)
            shown += 1
            out += ["", f"--- {f} ---", "```", data.rstrip(), "```"]
    return "\n".join(out)


def cost_note(meta):
    tok, cost = meta.get("tokens") or {}, meta.get("cost")
    bits = []
    if tok:
        step = f" over {meta['steps']} steps" if meta.get("steps", 0) > 1 else ""
        bits.append(f"{tok.get('input', '?')} in / {tok.get('output', '?')} out{step}")
    if cost is not None:
        bits.append("free" if not cost else f"${cost:.4f}")
    return ", ".join(bits)


def summary_table(judges, results):
    """A scoreboard above the reviews: who answered, how long, what it cost.

    The per-judge facts were only ever available by reading four essays to the end
    and then the Cost section at the bottom. Which judge failed, and which one cost
    a hundred times the others, are the two things you want BEFORE reading anything.
    """
    rows = [("judge", "status", "time", "tokens", "cost")]
    for j in judges:
        r = results[j]
        tok = r["meta"].get("tokens") or {}
        cost = r["meta"].get("cost")
        money = ("—" if cost is None else "free" if not cost
                 else f"${cost:.4f}" + (" *" if r["meta"].get("billing") == "subscription"
                                        else ""))
        rows.append((j, r["status"], f"{r['secs']}s",
                     f"{tok.get('input', 0):,}/{tok.get('output', 0):,}" if tok else "—",
                     money))
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "|".join(["---"] * len(rows[0])) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    if any(results[j]["meta"].get("billing") == "subscription" for j in judges):
        out += ["", "`*` = charged against a subscription plan, not invoiced."]
    return out


CITE = re.compile(r"([A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,6}):(\d+)")
# Judges do NOT agree on how to cite. Measured across one 4-judge panel: codex and
# local-qwen wrote `bug.py:14`, claude-sonnet wrote `(line 14)`, and or-deepseek wrote
# no line numbers at all. Matching only the first form reported 2/4 consensus on a
# defect that 3 of the 4 had actually located -- an undercount is worse than no table,
# because it reads as disagreement rather than as a citation style this code cannot see.
BARE_LINE = re.compile(r"\blines?\s+(\d+)", re.I)


def consensus_view(judges, results):
    """Which judges pointed at the same place. Mechanical overlap, NOT agreement.

    A review panel's whole value is knowing which findings stand alone and which
    several independent models reached; four essays in a row hide that -- you have
    to diff them in your head. Rows are file:line citations, columns are judges.

    Deliberately NOT model-generated: asking a model to summarise the panel puts a
    thirteenth opinion between you and the twelve, and it is the step most likely to
    quietly drop a minority finding. This groups only on literal citations, so it
    can be wrong in exactly one direction -- two judges citing one line may still be
    saying opposite things -- and the caveat below says so rather than implying a vote.
    """
    answered = [j for j in judges if results[j]["status"] in ("ok", "incomplete")]
    cites, bare, silent = {}, {}, []
    for j in answered:
        txt = results[j]["text"] or ""
        named = CITE.findall(txt)
        for f, ln in named:
            # A judge citing the same line five times is one finding, not five.
            cites.setdefault((f.split("/")[-1], int(ln)), set()).add(j)
        loose = {int(n) for n in BARE_LINE.findall(txt)}
        if loose:
            bare[j] = loose
        if not named and not loose:
            silent.append(j)
    # A bare "line 14" only resolves if the panel is looking at ONE file. With two
    # files in the diff it could mean either, and guessing would invent consensus --
    # the exact failure this table exists to avoid.
    files = {f for f, _ in cites}
    if len(files) == 1:
        only_file = next(iter(files))
        for j, lines in bare.items():
            for ln in lines:
                cites.setdefault((only_file, ln), set()).add(j)
        unresolved = []
    else:
        unresolved = sorted(bare)
    shared = {k: v for k, v in cites.items() if len(v) > 1}
    if not shared:
        return []
    out = ["", "---", "", "## Where the judges pointed at the same code", "",
           "| location | " + " | ".join(answered) + " | judges |",
           "|" + "|".join(["---"] * (len(answered) + 2)) + "|"]
    for (f, ln), who in sorted(shared.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        marks = ["✓" if j in who else "·" for j in answered]
        out.append(f"| `{f}:{ln}` | " + " | ".join(marks) + f" | {len(who)}/{len(answered)} |")
    only = {k: v for k, v in cites.items() if len(v) == 1}
    if only:
        singles = ", ".join(f"`{f}:{ln}` ({next(iter(w))})"
                            for (f, ln), w in sorted(only.items())[:8])
        out += ["", f"Cited by one judge only: {singles}"
                    + (" …" if len(only) > 8 else "")]
    # Naming who the table CANNOT represent matters more than the table. A judge that
    # cites no line is absent from every row, and a blank column reads as "disagreed"
    # when it means "this code could not see what it said".
    if silent:
        out += ["", f"**Not represented above: {', '.join(silent)}** — "
                    f"{'this judge' if len(silent) == 1 else 'these judges'} cited no "
                    f"line numbers, so {'it is' if len(silent) == 1 else 'they are'} "
                    f"missing from every row regardless of what "
                    f"{'it' if len(silent) == 1 else 'they'} found. A blank cell is not "
                    f"a disagreement."]
    if unresolved:
        out += ["", f"Ignored bare `line N` references from {', '.join(unresolved)}: more "
                    f"than one file is cited in this panel, so a bare line number is "
                    f"ambiguous and was not guessed at."]
    out += ["", "This counts CITATIONS, not agreement: two judges can cite one line and "
                "say opposite things about it. Use it to find where to look, then read "
                "the reviews in full."]
    return out


CONFIG_DIR = pathlib.Path(os.environ.get("XDG_CONFIG_HOME")
                          or os.path.expanduser("~/.config")) / "opencode"
MUTATING_TOOLS = ("write", "edit", "patch", "bash")


def agent_can_write(agent):
    """Can this opencode agent modify the repo?  True / False / None (unknown).

    The fallback guard only catches opencode REJECTING our agent. It cannot catch
    the agent existing but no longer denying the write tool -- an edited config,
    or `--agent build`, produces no warning at all and the judge silently gets
    write tools in the tree it is reviewing. Read from OUR config, which is where
    that permission is actually declared. A tool key that is ABSENT means opencode
    enables it, so absence counts as writable, not as safe.
    """
    for fn in ("opencode.jsonc", "opencode.json"):
        path = CONFIG_DIR / fn
        if not path.is_file():
            continue
        try:
            raw = re.sub(r"^\s*//.*$", "", path.read_text(), flags=re.M)
            cfg = json.loads(raw)
        except (OSError, ValueError):
            return None
        spec = (cfg.get("agent") or {}).get(agent)
        if spec is None:
            return None
        tools = spec.get("tools") or {}
        return any(tools.get(t, True) for t in MUTATING_TOOLS)
    return None


def provider_of(judge):
    """Which upstream service this judge talks to -- what a rate limit is shared across."""
    kind, model = ROSTER[judge]
    if kind == "opencode":
        return model.split("/", 1)[0]      # openrouter / huggingface / opencode
    return kind                            # codex / ollama


def repo_key(repo):
    """Stable per-repository directory name: readable basename + hash of the path."""
    base = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(repo.rstrip("/")) or "root")[:40]
    return f"{base}-{hashlib.sha256(repo.encode()).hexdigest()[:12]}"


def thread_key(name, repo):
    """Thread state is keyed by (name, REPO), not name alone.

    Keying by name let `--cwd repoA --thread design` and `--cwd repoB --thread design`
    share sessions -- and `codex exec resume` inherits the RECORDED working directory,
    so the repoB judge resumed inside repoA and answered about the wrong tree. The hash
    also separates names that sanitise identically ("a/b" and "a_b").
    """
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:40]
    return f"{safe}-{hashlib.sha256(f'{name}\0{repo}'.encode()).hexdigest()[:12]}"


def run_check(judges, repo, timeout, agent):
    """Actually ping each judge. --list makes a claim; this one observes it."""
    sys.stderr.write(f"llm-panel: pinging {len(judges)} judges...\n")
    with cf.ThreadPoolExecutor(max_workers=max(1, len(judges))) as ex:
        rows = [f.result() for f in
                [ex.submit(ask, j, "Reply with exactly: PONG", repo, timeout, agent, None,
                           "60s", sum(1 for k in judges if provider_of(k) == provider_of(j)))
                 for j in judges]]
    print(f"{'judge':<15}{'transport':<11}{'status':<9}{'secs':>6}  detail")
    for r in sorted(rows, key=lambda x: x["name"]):
        kind, _ = ROSTER[r["name"]]
        detail = "" if r["status"] == "ok" else r["text"].replace("\n", " ")[:70]
        print(f"{r['name']:<15}{kind:<11}{r['status']:<9}{r['secs']:>6}  {detail}")
    bad = [r for r in rows if r["status"] == "harness"]
    print(f"\nok={sum(1 for r in rows if r['status']=='ok')}  "
          f"refused={sum(1 for r in rows if r['status']=='refused')}  "
          f"unavailable={sum(1 for r in rows if r['status']=='unavailable')}  "
          f"incomplete={sum(1 for r in rows if r['status']=='incomplete')}  harness={len(bad)}")
    if bad:
        print("`harness` failures are OUR plumbing, not the model saying no.")
    return 0 if not bad else 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?")
    ap.add_argument("-f", "--file")
    ap.add_argument("--diff", action="store_true")
    # default=None, not the roster string: the code needs to distinguish "user said
    # nothing" from "user chose these". Sniffing sys.argv for "--judges" missed the
    # equals form (--judges=codex), so --check silently re-expanded the roster AFTER
    # the write-safety check had already passed on a smaller set.
    ap.add_argument("--judges", default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="ping every selected judge and report what actually happened")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--runs", action="store_true",
                    help="list past panel runs for this repo (newest first) with their "
                         "judges and outcomes, and where each one is on disk")
    ap.add_argument("--all-repos", action="store_true",
                    help="with --runs, list runs for every repo, not just this one")
    ap.add_argument("--stream", action="store_true",
                    help="echo tokens inline as they arrive, prefixed by judge. Only the "
                         "judges that actually stream can honour this (ollama and claude); "
                         "opencode sends one blob and codex sends no deltas, so those still "
                         "appear only when they finish")
    ap.add_argument("--thread", metavar="NAME",
                    help="keep a persistent conversation under NAME: every judge resumes its "
                         "own session, so follow-up turns remember the earlier ones")
    ap.add_argument("--rebut", action="store_true",
                    help="round 2: each judge answers the others' findings (anonymized)")
    ap.add_argument("--synthesize", metavar="JUDGE")
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--agent", default="panelist",
                    help="opencode agent for judges; default denies edit/bash (see opencode.jsonc)")
    ap.add_argument("--live", action="store_true",
                    help="print each judge's answer the moment it lands, instead of "
                         "holding everything until the slowest one finishes")
    ap.add_argument("--save-here", action="store_true",
                    help="also copy panel.md into the reviewed repo after the run "
                         "(off by default: judges of later panels could read it)")
    ap.add_argument("--unsafe-agent", action="store_true",
                    help="run even though the chosen opencode agent is not verified "
                         "read-only (it may write to the repo under review)")
    ap.add_argument("--keep-alive", default="60s",
                    help="how long a local (ollama) model stays resident in VRAM after "
                         "answering; the GPU is shared, so the default is short")
    ap.add_argument("--image", action="append", metavar="PATH",
                    help="attach an image for the judges to look at (repeatable). Only "
                         "vision-capable judges accept it: vis-grok, vis-kimi, vis-gemini, "
                         "vis-gpt and the claude judges. Everyone else reports "
                         "`unavailable` rather than answering blind")
    ap.add_argument("--vision-check", metavar="TEXT",
                    help="ground-truth control for --image runs: each judge must first "
                         "quote a specific thing visible in the image. Any judge whose "
                         "answer does not contain TEXT is reported as unverified rather "
                         "than believed. A judge asserting 'I can see it' is not evidence.")
    ap.add_argument("--effort", choices=EFFORT_LEVELS, default=None,
                    help="reasoning effort for judges that have the setting: claude "
                         "(--effort), codex (model_reasoning_effort) and opencode "
                         "(--variant, provider-specific). ollama models have no "
                         "equivalent and ignore it. Default: codex stays at high, "
                         "the others use their own defaults")
    ap.add_argument("--timeout", type=int, default=None)
    a = ap.parse_args()

    global STATE, STREAM_ECHO
    STREAM_ECHO = a.stream
    repo = os.path.abspath(a.cwd)
    if not os.path.isdir(repo):
        die(f"--cwd is not a directory: {repo}")
    # STATE follows XDG_CACHE_HOME, which the caller controls and could point INSIDE
    # the repo -- putting every finished answer back where judges can read it while
    # slower judges are still running.
    if str(STATE) == repo or str(STATE).startswith(repo.rstrip("/") + os.sep):
        STATE = pathlib.Path.home() / ".llm-panel"
        sys.stderr.write(f"llm-panel: XDG_CACHE_HOME points inside the reviewed repo, "
                         f"where judges could read earlier answers; using {STATE}\n")
    # Panel output lives OUTSIDE the reviewed repo. It used to be written to
    # <repo>/.panel, which judges can read: opencode judges have read/grep/glob
    # over their cwd and the codex judge gets a read-only sandbox rooted at the
    # same tree. Round 1 was safe only by accident (per-judge files are written
    # after every judge returns), but the rebuttal round, turn 2 of a --thread,
    # and every later panel in that repo all ran with earlier answers sitting on
    # disk -- so "judges never see each other's answers" was defeated through the
    # filesystem rather than the prompt.
    outdir = STATE / "runs" / repo_key(repo)

    if a.list:
        print(f"{'judge':<15}{'transport':<11}model")
        for n, (k, m) in ROSTER.items():
            need = next((v for pre, v in PROVIDER_ENV.items() if m.startswith(pre)), "")
            have = (os.environ.get(need) or
                    next((PROVIDER_AUTH[pre] in stored_providers()
                          for pre in PROVIDER_AUTH if m.startswith(pre)), False)) if need else True
            flag = "" if not need or have else f"  [no {need} and no stored login]"
            print(f"{'*' if n in DEFAULT else ' '}{n:<14}{k:<11}{m}{flag}")
        print("\n* = in the default roster.  This listing is OFFLINE -- it reports what is")
        print("configured, not what answers today.  Run --check to actually ping them.")
        print("codex/opencode judges can READ the repo; ollama judges answer from the")
        print("prompt alone (no tool loop), so they cannot verify a claim against code.")
        return

    if a.show:
        last = sorted(outdir.glob("*/panel.md")) if outdir.exists() else []
        if not last:
            die(f"no panel run found under {outdir}")  # runs are kept outside the repo
        sys.stdout.write(last[-1].read_text()); return

    if a.runs:
        # Every run already persisted its prompt, each judge's prompt, each judge's
        # answer and the assembled panel.md -- but nothing ever listed them, so the
        # history was only reachable by knowing the cache layout by heart.
        roots = sorted((STATE / "runs").glob("*")) if a.all_repos else [outdir]
        rows = []
        for root in roots:
            if not root.is_dir():
                continue
            for rd in sorted(root.glob("*/"), reverse=True):
                pm = rd / "panel.md"
                judges_ran = sorted(f.stem for f in rd.glob("*.md")
                                    if f.name not in ("panel.md", "prompt.md")
                                    and not f.name.endswith((".prompt.md", ".live.md")))
                # Read the WHOLE report, not a prefix: the "N of M judges answered"
                # line is the LAST thing written, so a first-4KB scan reported every
                # finished run as unfinished (it did, on the first try).
                head = pm.read_text().splitlines() if pm.is_file() else []
                when = head[0].replace("# Panel — ", "").strip() if head else "(unfinished)"
                answered = next((l.strip("* ") for l in reversed(head)
                                 if "judges answered" in l), "")
                # The prompt is the only thing that tells two runs apart at a glance.
                q = ""
                if (rd / "prompt.md").is_file():
                    q = " ".join((rd / "prompt.md").read_text().split())[:70]
                rows.append((rd, when, judges_ran, answered, q,
                             root.name if a.all_repos else ""))
        if not rows:
            die(f"no panel runs recorded under {STATE / 'runs'}")
        for rd, when, js, answered, q, which in rows:
            tag = f"[{which}] " if which else ""
            print(f"{tag}{when}  —  {answered or 'no summary (run did not finish)'}")
            print(f"    judges: {', '.join(js) or '(none completed)'}")
            if q:
                print(f"    asked:  {q}…")
            print(f"    {rd}")
        print(f"\n{len(rows)} run(s). Full report: cat <dir>/panel.md · one judge: "
              f"<dir>/<judge>.md · what that judge was SHOWN: <dir>/<judge>.prompt.md")
        print("Streaming judges also leave <judge>.live.md, written as the tokens arrived.")
        return

    explicit_timeout = a.timeout is not None
    if a.timeout is None:
        a.timeout = 900
    judges = [j.strip() for j in (a.judges if a.judges is not None
                                  else ",".join(DEFAULT)).split(",") if j.strip()]
    # Duplicates silently overwrote each other in `results`, so `--judges codex,codex`
    # printed one answer twice and claimed "2 of 2 judges answered".
    seen, unique = set(), []
    for j in judges:
        if j in seen:
            sys.stderr.write(f"llm-panel: {j} listed more than once; asking it once\n")
            continue
        seen.add(j)
        unique.append(j)
    judges = unique
    unknown = [j for j in judges if j not in ROSTER]
    if unknown:
        die(f"unknown judge(s): {', '.join(unknown)} (see --list)")
    if a.synthesize and a.synthesize not in ROSTER:
        die(f"unknown synthesizer: {a.synthesize} (see --list)")
    if not judges:
        die("no judges selected: --judges parsed to an empty list")

    stale = pathlib.Path(repo) / ".panel"
    if stale.is_dir():
        sys.stderr.write(
            f"llm-panel: WARNING {stale} exists from an older version. It sits inside the "
            f"tree the judges can read, so they may find earlier judges' answers there. "
            f"Delete it to keep this panel independent.\n")

    # A missing binary is ONE judge's problem. Dying here meant an absent opencode
    # cancelled the whole panel before Codex was ever asked -- and ollama judges
    # were refused for want of a CLI this program no longer uses (it speaks HTTP).
    # ask() reports a missing transport as that judge's `harness` failure instead.
    for j in judges:
        kind = ROSTER[j][0]
        if kind in BINARY and not shutil.which(BINARY[kind]):
            sys.stderr.write(f"llm-panel: `{BINARY[kind]}` is not on PATH, so {j} will "
                             f"report a transport failure; the other judges still run\n")

    # The synthesizer runs the same way a judge does, in the same repo, so it must
    # clear the same bar. The guard used to consult `judges` only, so
    # `--judges codex --synthesize big-pickle --agent build` skipped it entirely.
    if any(ROSTER[j][0] == "opencode" for j in judges + ([a.synthesize] if a.synthesize else [])):
        writable = agent_can_write(a.agent)
        if writable is not False and not a.unsafe_agent:
            why = ("it is not defined in your opencode config" if writable is None
                   else "its config does not deny write/edit/patch/bash")
            die(f"agent '{a.agent}' is not verified read-only ({why}), so a judge could "
                f"modify the very repo it is reviewing. Fix the agent definition, or pass "
                f"--unsafe-agent if you really mean it.", 9)

    if a.check:
        if a.judges is None:
            judges = list(ROSTER)
        # 180s is plenty when the box is idle, but this laptop shares cores with
        # other sessions' jobs; honour an explicit --timeout so contention does not
        # get misread as 13 dead judges.
        cap = a.timeout if explicit_timeout else 180
        sys.exit(run_check(judges, repo, cap, a.agent))

    if a.file:
        if a.prompt:
            die("give a prompt as an argument or via --file, not both")
        a.prompt = sys.stdin.read() if a.file == "-" else pathlib.Path(a.file).read_text()
    elif not a.prompt and not sys.stdin.isatty():
        a.prompt = sys.stdin.read()
    if not a.prompt or not a.prompt.strip():
        die("no prompt given (--list shows judges, --check pings them, --show reprints)")
    if a.diff:
        a.prompt = a.prompt.rstrip() + "\n\n" + collect_diff(repo)

    stamp = datetime.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    # pid in the name: two panels started in the same SECOND used to share a
    # rundir and overwrite each other's per-judge files and panel.md.
    rundir = outdir / f"{stamp}-{os.getpid()}"
    rundir.mkdir(parents=True, exist_ok=True)
    (rundir / "prompt.md").write_text(a.prompt)

    sessions = {}
    if a.thread:
        tdir = STATE / "threads" / thread_key(a.thread, repo)
        tdir.mkdir(parents=True, exist_ok=True)
        # A thread is a conversation; two panels running it at once both compute the
        # same turn number, overwrite turn-001.md, and race to write the same session
        # file, after which the next turn resumes whichever id landed last and the
        # other conversation is silently forgotten. Serialise instead of interleaving.
        _lock = open(tdir / ".lock", "w")
        try:
            fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            die(f"another llm-panel run is already using thread '{a.thread}' in this "
                f"repository. Wait for it, or use a different --thread name.", 10)
        sessions = {j: tdir / f"{j}.session" for j in judges}
        resuming = [j for j in judges if (codex_session_id(sessions[j], repo)
                                          if ROSTER[j][0] == "codex"
                                          else read_session(sessions[j]))]
        turn = len(list(tdir.glob("turn-*.md"))) + 1
        sys.stderr.write(f"llm-panel: thread '{a.thread}', turn {turn} — "
                         f"{len(resuming)} judge(s) resuming, {len(judges)-len(resuming)} starting "
                         f"fresh{': ' + ', '.join(resuming) if resuming else ''}\n")
        (tdir / f"turn-{turn:03d}.md").write_text(a.prompt)

    sys.stderr.write(f"llm-panel: asking {len(judges)} judges in parallel "
                     f"({', '.join(judges)}) — this takes as long as the slowest one\n")
    results = {}
    with cf.ThreadPoolExecutor(max_workers=len(judges)) as ex:
        peers = {}
        for j in judges:
            peers[provider_of(j)] = peers.get(provider_of(j), 0) + 1
        futs = {ex.submit(ask, j, a.prompt, repo, a.timeout, a.agent,
                          sessions.get(j), a.keep_alive,
                          peers[provider_of(j)],
                          rundir / f"{j}.live.md", a.effort, a.image, a.vision_check): j for j in judges}
        # Heartbeat. ollama and claude judges stream token-by-token; opencode emits
        # its whole answer as ONE json text event and codex only emits item.completed,
        # so for THOSE the honest live signal is "still working, N seconds in" rather
        # than a token feed that does not exist. Do not promise streaming for all.
        pending, t_start = set(futs), time.time()
        while pending:
            done, pending = cf.wait(pending, timeout=20)
            for fut in done:
                r = fut.result()
                results[r["name"]] = r
                note = cost_note(r["meta"])
                sys.stderr.write(f"  · {r['name']}: {r['status']} ({r['secs']}s"
                                 + (f", {note}" if note else "") + ")\n")
                emit(rundir, r["name"], a.prompt, r, a.live)
            if pending:
                waiting = sorted(futs[f] for f in pending)
                sys.stderr.write(f"  … {int(time.time() - t_start)}s — still working: "
                                 f"{', '.join(waiting)}\n")
                sys.stderr.flush()

    hdr = f"# Panel — {now()}"
    if a.thread:
        alive = [j for j in judges if (codex_session_id(sessions[j], repo)
                                       if ROSTER[j][0] == "codex"
                                       else read_session(sessions[j]))]
        hdr += f"\n\n**Thread `{a.thread}`** — judges carrying memory of earlier turns: " \
               + (", ".join(alive) if alive else "none yet (first turn)")
    lines = [hdr, "", f"Judges: {', '.join(judges)}", ""]
    lines += summary_table(judges, results) + [""]
    lines += consensus_view(judges, results)
    lines += ["", "## Question", "", a.prompt, ""]
    for j in judges:
        r = results[j]
        _, model = ROSTER[j]
        note = cost_note(r["meta"])
        head = f"\n---\n\n## {j}  (`{model}`) — {r['secs']}s" + (f", {note}" if note else "")
        lines += [head, ""]
        if r["status"] == "ok":
            lines += [r["text"], ""]
        elif r["status"] == "incomplete":
            lines += [f"**INCOMPLETE — this judge started answering and then failed "
                      f"({r['meta'].get('note', 'unknown')}). What it produced is below, "
                      f"but it is a PARTIAL review: treat silence on any point as "
                      f"'never got there', not 'found nothing'.**", "", r["text"], ""]
        elif r["status"] == "refused":
            lines += [f"**DID NOT ANSWER — the model/provider refused.** {r['text']}", ""]
        elif r["status"] == "unavailable":
            lines += [f"**DID NOT ANSWER — the provider would not serve right now.** "
                      f"{r['text']} This is retryable and says nothing about the question.", ""]
        else:
            lines += [f"**DID NOT ANSWER — our harness failed, not the model.** {r['text']}", ""]

    answered = [j for j in judges if results[j]["status"] == "ok"]
    partial = [j for j in judges if results[j]["status"] == "incomplete"]
    refused = [j for j in judges if results[j]["status"] == "refused"]
    unavail = [j for j in judges if results[j]["status"] == "unavailable"]
    broke = [j for j in judges if results[j]["status"] == "harness"]
    # Money and quota are not the same thing, so report them apart: metered judges
    # add up to a bill, subscription judges (codex on ChatGPT Plus, claude on
    # claude.ai) consume plan quota and their dollar figures are notional.
    metered = sum(results[j]["meta"].get("cost") or 0 for j in judges
                  if results[j]["meta"].get("billing") != "subscription")
    plan = sum(results[j]["meta"].get("cost") or 0 for j in judges
               if results[j]["meta"].get("billing") == "subscription")
    tok = sum((results[j]["meta"].get("tokens") or {}).get("input", 0) for j in judges)
    out_tok = sum((results[j]["meta"].get("tokens") or {}).get("output", 0) for j in judges)
    lines += ["\n---\n", "### Cost", "",
              f"- billed: **${metered:.4f}**" + ("" if metered else " (nothing metered)"),
              f"- on subscription plans (notional, no invoice): ${plan:.4f}" if plan else
              "- on subscription plans: none used",
              f"- tokens: {tok:,} in / {out_tok:,} out across {len(judges)} judges", ""]
    for j in judges:
        m = results[j]["meta"]
        c = m.get("cost")
        tag = " (plan quota)" if m.get("billing") == "subscription" else ""
        lines += [f"  - {j}: " + (f"${c:.4f}{tag}" if c is not None else "no cost reported")
                  + f", {results[j]['secs']}s, {results[j]['status']}"]
    lines += ["", f"**{len(answered)} of {len(judges)} judges answered.**"]
    if partial:
        lines += [f"**Answered only partially: {', '.join(partial)}** — they failed mid-answer, "
                  f"so their reviews are truncated and are NOT counted above."]
    if refused:
        lines += [f"**Refused: {', '.join(refused)}** — their view is missing from this panel."]
    if unavail:
        lines += [f"**Temporarily unavailable: {', '.join(unavail)}** — rate-limited or "
                  f"overloaded, not a judgment. Re-run them before drawing conclusions."]
    if broke:
        lines += [f"**Harness failed for: {', '.join(broke)}** — that is OUR plumbing, not a "
                  f"judgment by those models. Re-run them before concluding anything."]

    if a.rebut:
        rlines, _ = run_rebuttals(judges, results, a.prompt, repo, a.timeout,
                                  a.agent, rundir, sys.stderr.write, a.live, a.effort,
                                  a.image)
        lines += rlines

    if a.synthesize:
        if len(answered) < 2:
            lines += ["", "_Synthesis skipped: fewer than two judges answered._"]
        else:
            blob = "\n\n".join(f"### Reviewer {j}\n{results[j]['text']}" for j in answered)
            sp = ("Below are independent reviews of the same material by different models. "
                  "Do not average them. Report: (1) points every reviewer agrees on, "
                  "(2) points where they DISAGREE, naming who said what and which is better "
                  "supported, (3) anything only one reviewer caught. Be concise.\n\n" + blob)
            sys.stderr.write(f"  · synthesizing with {a.synthesize}\n")
            s = ask(a.synthesize, sp, repo, a.timeout, a.agent, None, a.keep_alive,
                    1, None, a.effort, a.image)
            lines += [f"\n---\n\n## Synthesis (by `{a.synthesize}`)", "",
                      s["text"] if s["status"] == "ok"
                      else f"**SYNTHESIS FAILED ({s['status']})** — {s['text']}"]

    doc = "\n".join(lines)
    (rundir / "panel.md").write_text(doc)
    # Machine-readable sibling of panel.md. Anything that wants to RENDER a run should read
    # this rather than re-parse the prose: status, cost and timing are already structured
    # here, and a reporter scraping markdown goes stale the moment the wording changes.
    (rundir / "run.json").write_text(json.dumps({
        "stamp": stamp, "when": now(), "repo": repo, "thread": a.thread,
        "effort": a.effort, "rebut": bool(a.rebut), "synthesize": a.synthesize,
        "images": [str(pathlib.Path(i).resolve()) for i in (a.image or [])],
        # Who "Reviewer A" actually was. The rebuttal round anonymises judges from EACH
        # OTHER on purpose, but the reader is not the one being kept honest -- without
        # this map every cross-reference in round 2 is unresolvable prose.
        "letters": {chr(ord("A") + i): j
                    for i, j in enumerate(j for j in judges
                                          if results[j]["status"] in ("ok", "incomplete"))},
        "prompt": a.prompt,
        "judges": [{
            "name": j,
            "transport": ROSTER[j][0],
            "model": ROSTER[j][1],
            "status": results[j]["status"],
            "secs": results[j]["secs"],
            "meta": results[j]["meta"],
            "note": results[j]["meta"].get("note"),
        } for j in judges],
    }, indent=1))
    print(doc)
    sys.stderr.write(f"\n[panel written to {rundir}]\n")
    if a.save_here:
        # Written only AFTER judging, and off by default: anything left inside the
        # repo is readable by the NEXT panel's judges.
        dest = pathlib.Path(repo) / f"panel-{stamp}.md"
        dest.write_text(doc)
        sys.stderr.write(f"[copy saved in the repo at {dest} — future judges can read it]\n")

    # FAIL LOUD ON A DEGRADED BENCH. A 5-judge panel once came back with three judges at
    # `harness (0.0s)` -- no request ever left the machine, the key was simply absent from
    # a non-interactive shell -- and the run still printed a normal-looking report and
    # exited 0. A panel's whole value is cross-family independence, so losing 60% of the
    # bench is not a footnote: it silently turns a five-family panel into a two-family one,
    # and the reader cannot tell from the report that anything was missing.
    broken = [j for j in judges if results[j]["status"] == "harness"]
    if broken:
        sys.stderr.write(
            f"\n!! DEGRADED PANEL: {len(broken)} of {len(judges)} judges never ran "
            f"({', '.join(broken)}).\n"
            f"!! These are OUR failures, not refusals. This panel is missing "
            f"{len(broken)} of its {len(judges)} families.\n")
        for j in broken:
            first = (results[j]["text"] or "").strip().splitlines()
            sys.stderr.write(f"!!   {j}: {first[0][:150] if first else 'no detail'}\n")
        sys.stderr.write("!! Exit 4. The report above is real but INCOMPLETE.\n")
        sys.exit(4)


if __name__ == "__main__":
    main()


---

Your own review was:

1. **The OpenCode write boundary can approve a writable agent.** `agent_can_write()` inspects only the global config and four literal tool names. If the global `panelist` disables those tools but the reviewed repo’s `opencode.json` overrides `agent.panelist.tools.write` to `true`, the guard returns `False` while `opencode run` loads the repo-local override and may edit the tree. Likewise, a custom/MCP tool such as `filesystem_write_file` or `shell` remains enabled but is absent from `MUTATING_TOOLS`.

2. **Claude has the same custom-tool escape.** `--disallowedTools Write,Edit,NotebookEdit,Bash` denies only those names. A configured MCP tool such as `mcp__filesystem__write_file` or a command-running custom tool remains available. A Claude judge can therefore mutate the reviewed repo despite being presented as sandboxed.

3. **`--diff` follows untracked symlinks and can exfiltrate files outside the repo.** `git ls-files --others` returns the symlink’s repository path, then `open(repo / f)` follows it. An untracked `credentials -> ~/.aws/credentials` symlink causes the credential file’s contents to be embedded in the prompt sent to every remote judge.

4. **The run-directory containment check is lexical, not physical.** If `/tmp/cache` is a symlink to `/work/repo/.cache`, then `XDG_CACHE_HOME=/tmp/cache llm-panel --cwd /work/repo ...` passes the prefix check but writes completed answers inside the reviewed tree. A slower judge can read a faster judge’s `<judge>.md`, destroying round-one independence. A relative `XDG_CACHE_HOME` has the same problem when invoked from the repo.

5. **Rebuttal identities are not actually anonymised.** Reviews are copied verbatim without scrubbing. If the round-one prompt says “start by naming your model,” a block will literally begin “I am Claude/GPT…”, and every rebutter sees the identity. Separately, reviewer letters follow the caller’s stable judge order; when that roster/order is stated in the question or inferable from the reviewed source, the missing self-letter reveals the entire mapping.

6. **The vision control both leaks its answer and is never checked.** `vision_check` is inserted verbatim into the textual prompt, so a model can copy it without reading the image. Worse, no post-response validation exists. With a blank image and `--vision-check NEEDLE`, either an answer beginning `NEEDLE` or even `CANNOT_SEE` is returned as `ok`.

7. **Round two requires finding numbers that round one never creates.** The original prompt is sent unchanged, so reviewers may return ordinary prose or bullets. `REBUT_INSTRUCTIONS` then falsely states that every reviewer numbered its findings and demands references such as `B7`. For an unnumbered review, rebutters must invent identifiers or cannot produce matchable positions.

8. **The rebuttal tally counts positions without valid references.** Its regex only requires a label followed within 24 characters by a colon or dash; it never requires `[A-Z]\d+`. A line such as `REJECT — this framing is misleading` increments “reject 1” even though it cites no reviewer finding and should, by the prompt’s own rule, be dropped.

9. **The HTTP transports do not enforce a total wall-clock timeout.** `urlopen(..., timeout=timeout)` sets socket-operation timeouts. An Ollama generation emitting a token every few seconds can run for minutes despite `--timeout 10`; an HTTP peer that dribbles bytes before each socket timeout can keep either HTTP branch alive indefinitely.

10. **Streaming timeouts discard substantive partial answers and their accounting.** If Claude emits 10 KB and is then killed by the watchdog, the handler retains only the last 400 characters inside a `harness` message. `<judge>.md` contains that error rather than the partial review, `run.json` has no partial text or usage, and the answer is not classified `incomplete`, although `<judge>.live.md` contains the review.

11. **Ollama accepts an unfinished stream as a complete answer.** The branch never checks `done`, errors in the final object, or `done_reason`. If the server sends `{"response":"partial","done":false}` and then closes cleanly—or reports `done_reason: "length"`—the accumulated text is returned as `ok`.

12. **Provider outages are blamed on the harness.** A structured OpenCode HTTP 500, 502, or 504 misses both status maps and falls through to text saying the failure is “on our side.” The direct OpenRouter vision branch similarly reports HTTP 429 or 503 as `harness`, bypassing `PROVIDER_UNAVAILABLE`. These are provider-unavailability failures misattributed to local plumbing.

13. **A vision capability/configuration failure is blamed on the model as a refusal.** Any OpenRouter HTTP error body containing `image input` is marked `refused`, including the stated 404 “No endpoints found that support image input.” A stale roster entry or unsupported endpoint therefore becomes evidence that the model declined the question, opposite to the classification rule for bad model IDs and malformed routing.

14. **Codex and Claude cannot report known provider refusals correctly.** Every nonzero Codex exit immediately becomes `harness` without parsing structured JSON errors. Every Claude `result` with `is_error` also becomes `harness`. Thus an exhausted ChatGPT/Claude plan or explicit authentication rejection is printed as the tool’s plumbing failure rather than a provider refusal.

15. **Rebuttal and synthesis spend is completely omitted.** The cost section is assembled from round-one `results` before either extra phase. Rebuttal results returned by `run_rebuttals()` are discarded, and the synthesizer result is not accumulated. A metered `--rebut --synthesize` run can make roughly twice the panel calls while reporting only round-one money and tokens.

16. **Unknown usage is presented as measured zero.** Vision, Claude, and Ollama construct token dictionaries using `... or 0`; an omitted usage field becomes `0 in / 0 out`. Aggregate cost similarly treats absent or null cost as zero and prints `$0.0000 (nothing metered)`. A successful metered OpenRouter response with no reported `usage.cost` therefore produces a false zero-bill claim, despite the per-judge row saying “no cost reported.”

17. **Codex plan usage is dropped entirely.** Successful Codex results have no `billing` metadata. A Codex-only run therefore prints “on subscription plans: none used,” even though the transport is explicitly described as consuming the ChatGPT subscription. A Claude subscription result whose reported notional cost is zero is also labelled `free` and receives no row-level subscription marker.

18. **Claude is not guaranteed to use subscription billing.** The environment removes only `ANTHROPIC_API_KEY`; alternate Claude routing/auth variables remain. With Bedrock/Vertex mode or an alternate auth token configured, the request can incur metered cloud/API charges while `meta["billing"]` is unconditionally recorded as `"subscription"` and excluded from billed spend.

19. **`run.json`’s reviewer mapping disagrees with the actual rebuttal mapping.** Round two assigns letters only to round-one `status == "ok"` judges, while JSON includes both `"ok"` and `"incomplete"`. With `[codex=ok, big-pickle=incomplete, nemotron=ok]`, round two uses `A=codex, B=nemotron`; JSON records `A=codex, B=big-pickle, C=nemotron`, so a renderer attributes every `B<n>` rebuttal to the wrong judge.

20. **`run.json` omits the structured results of optional phases.** It records only that rebuttal/synthesis was requested, not their status, time, cost, tokens, text, or whether rebuttal was skipped. A failed or billed rebuttal is therefore invisible to the separate renderer. Round-one text is also absent from each judge object and only recoverable through an undocumented sibling-filename convention.

21. **The JSON metadata schema remains non-uniform.** A successful Codex judge has neither `meta.cost` nor `meta.tokens`; OpenCode may omit `cost`; vision/Claude may emit `cost: null`; and top-level optional fields plus every normal judge `note` may be null. A renderer formatting these values numerically can still crash or silently treat unknown as zero. `secs` itself is numeric on every path through `result()` in this version.

22. **`consensus_view()` can manufacture consensus between different files.** It discards directories with `f.split("/")[-1]`. If one judge cites `src/config.py:20` and another cites `tests/config.py:20`, they are merged into one `config.py:20` row showing 2/2 agreement.

23. **Bare line references are assigned using cited filenames rather than the reviewed files.** If a diff contains `a.py` and `b.py`, judge A cites `a.py:14`, and judge B writes “line 14” meaning `b.py`, the set of named citations contains only `a.py`. The code assigns B’s bare reference to `a.py:14` and reports false consensus.

24. **Credential-copy failures are knowingly swallowed and can reverse blame.** Suppose the host auth file contains a refreshed key, while the isolated destination contains a revoked key and is unwritable. The guard sees the valid host provider, `copy2` fails and is ignored, OpenCode uses the stale key, and a structured 401 is reported as the provider refusing. The actual cause was the harness failing to propagate credentials.

25. **`--thread` is not implemented for vision judges.** The `orvision` branch never reads or writes `session_file`. Two calls using `--judges vis-gpt --thread design` are unrelated fresh chat completions even though the option promises that every judge resumes its own session.

26. **Ollama can be announced as resuming while actually starting fresh.** The banner considers any nonempty session file resumable, but `ask()` silently ignores malformed JSON, non-list JSON, and empty lists. A session file containing `{broken` yields “1 judge resuming,” then sends no context at all.

27. **CLI prompts beginning with `-` are parsed as transport options.** Codex and OpenCode append the prompt without an option terminator. Supplying `--help` via stdin or `llm-panel ... -- --help` makes the child CLI display help or reject arguments instead of asking the model. Large `--file` or unbounded tracked diffs are also passed as one argv element and can make every CLI transport fail with `E2BIG`.

28. **Repository aliases split history and thread state.** `repo_key()` and `thread_key()` hash the unresolved absolute path. Running against `/work/repo` and later using a symlink `/tmp/repo-link` creates different keys, so `--show`, `--runs`, and `--thread` cannot find the earlier run or conversation even though both paths name the same repository.

29. **`--runs` reports rebuttal files as extra judges.** Its `*.md` scan includes `<judge>.rebuttal.md`, whose stem becomes `<judge>.rebuttal`. A two-judge rebuttal run is listed as four judge names.

A round-one failure is not itself leaked into round two: `run_rebuttals()` correctly filters to `status == "ok"`. The defect there is the contradictory `run.json` letter map, not the prompt selection.

---

You already reviewed this material independently. Below are the findings of the OTHER reviewers. They did not see your review, and their identities are withheld from you on purpose.

Each reviewer NUMBERED their findings. Refer to one as <Letter><number> -- B7 is Reviewer B's finding 7. Take a position on each finding that touches yours:
  UPHOLD:  B7 -- you stand by your own claim despite theirs; say what proves it.
  REJECT:  B7 -- theirs is wrong or overstated; point at the specific code or logic that makes it wrong.
  CONCEDE: B7 -- you were wrong; say exactly what changed your mind.
  MISSED:  B7 -- they caught something real that you did not; confirm it against the code rather than taking their word.

Start each point with one of those four labels verbatim, then the reference, THEN your argument. Cite the reference even when you also describe the finding: a position that only restates a finding in your own words cannot be matched to the finding it answers, so it is dropped from the panel's grouped view and argues with nobody.

Two rules that matter more than agreeing:
1. Do NOT concede merely because someone disagreed with you. Concede only when you can point at what proves you wrong. A correct finding stays correct when it is unpopular.
2. Do NOT invent agreement. If a finding is unverifiable from what you have, say so instead of endorsing it.

Reviews from the other reviewers follow.

### Reviewer B
Two claims in that review rest on recall of external system behaviour rather than on the source you gave me. Flagging them rather than leaving them as assertions:

**Recall-based, not verified this turn:**

- **Finding 7 (`E2BIG`)** — I asserted Linux caps a *single* argv string at `MAX_ARG_STRLEN` = 128 KiB independent of total `ARG_MAX`. Everything source-side is solid (the prompt is one argv element in all three CLI transports; `collect_diff` caps untracked bodies at 200,000 bytes and does not cap the diff at all). The exact ceiling is recall. Falsifier: `python3 -c 'import subprocess; subprocess.run(["true", "x"*200_000])'` — if that succeeds, the finding shrinks to "unbounded prompt growth" and loses its concrete trigger point.
- **Finding 9 (`Task` escape)** — that `--disallowedTools` does not propagate to a subagent spawned via `Task` is recall about the Claude CLI, not something the file shows. What the file *does* show stands on its own: `Task`, `WebFetch` and `mcp__*` are absent from the denylist, which is the same open-set problem as finding 2. Falsifier: run a claude judge with the panel's exact flags and ask it to delegate a write.
- **Finding 2, second half** — already flagged inline; opencode's project-level config precedence is recall.
- **Finding 5** — "OpenRouter omits `usage.cost` unless the request asks for it" is recall. The source-side half is not: the `orvision` payload contains no usage-accounting field, and `meta["cost"]` is read from `usage.cost`, so if that key is ever absent the judge's spend is summed as `0` into a line printed as *billed*.
- **Finding 8** — that `urlopen(timeout=)` is a per-socket-operation timeout rather than a deadline is documented stdlib behaviour, but I did not confirm it this turn.

**On the remediation sentences.** Where I wrote "fix is to pass the prompt on stdin", "a per-judge random permutation closes it", "`STATE.resolve()` before comparing" — treat those as directions, not diagnosed causes. I did not run the three-hypothesis gate on any of them, and a review of a static file cannot: I have no failing run to attribute. What I can stand behind is the observation in each case (the prompt is one argv element; letters come from `enumerate(answered)` with no shuffle; `STATE` is never absolutised while `repo` is). Deciding the cause of any *observed* failure, and what to change, needs the mechanism test against a real run.

The source-only findings — 1, 3, 4, 6, 10, 11, 12, 13, 14 and the first half of 2 — depend on nothing outside the file and are unaffected by the above.

### Reviewer C
I have read the complete source code. I will review it for real defects, focusing on the areas you specified.

## Defects Found

### 1. **Blame misclassification in `_classify_error` - Direction: Provider refusal mislabeled as our fault**

**Concrete failure scenario:** When `opencode` returns a 404 error for an invalid model ID, it's classified as `harness` (our fault) but should be `refused` (provider declining).

**Evidence:** 
- `PROVIDER_DECLINED` dictionary only contains 401, 402, 403
- A 404 "model not found" means the provider declined to serve that model
- Line 240: `_classify_error` defaults unknown codes to `harness`
- Line 192-193: comment says "a bad model id (404)... is OUR mistake" but this contradicts the tool's stated philosophy: provider refusing a specific model IS a refusal by that provider

**Impact:** A judge with stale roster ID appears as "our plumbing broke" instead of "model refused", hiding the fact that the model choice itself was invalid.

### 2. **Anonymity breach in `run_rebuttals()` - Judges can identify their own text**

**Concrete failure scenario:** In round 2, each judge sees: "Your own review was: [full text]". A judge can fingerprint its own writing style, formatting patterns, or specific phrasing to deduce which reviewer wrote which finding.

**Evidence:**
- Line)
- Line 600: `prompts[me] = (f"{prompt}\n\n---\n\nYour own review was:\n\n{results[me]['text']}"`
- Judges are told "They did not see your review" but then shown their exact text
- A clever judge could use stylistic analysis to match other reviews to its own memory

**Impact:** Rebuttal round is contaminated; judges can adjust responses based on perceived authority of anonymous reviewers.

### 3. **Double-counting of tokens/cost in opencode transport**

**Concrete failure scenario:** When opencode judge takes multiple steps, `step_finish` events accumulate tokens/cost, but final answer may be truncated. The partial answer is returned as `incomplete` but the full accumulated cost is reported.

**Evidence:**
- Line 426-434: `meta["tokens"]["input/output"]` are summed across steps
- Line 436: `meta["cost"]` is summed across steps
- Line 447-450: If body exists but `broke` (including `unfinished`), answer marked `incomplete`
- Line 457: The `incomplete` result includes the accumulated `meta`

**Impact:** User pays for all steps even when judge was cut off mid-answer, and cost attribution doesn't match usable output.

### 4. **Missing credential check for claude transport**

**Concrete failure scenario:** Claude judge runs unauthenticated when `ANTHROPIC_API_KEY` is unset, silently falling back to subscription mode without warning.

**Evidence:**
- Line 325: `env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}`
- No check equivalent to opencode's `PROVIDER_ENV` validation
- Comment at line 85-87 says "with ANTHROPIC_API_KEY unset the CLI answers on the claude.ai login" but no runtime verification
- If claude CLI not logged in, judge fails with unclear error

**Impact:** Silent authentication failure misreported as generic `harness` error.

### 5. **`run.json` emission can have null `secs` field causing downstream crash**

**Concrete failure scenario:** `results[j]["secs"]` can be `None` or missing when `ask()` catches an exception early, causing `{j["secs"]:.1f}` format to crash.

**Evidence:**
- Line 693-694: `run.json` includes `"secs": results[j]["secs"]`
- Line 76: `result()` function returns `"secs": round(secs, 1)` but early returns might not call it
- Line 161: `_classify_error` calls `result(..., secs)` - this passes `secs` parameter
- However, exception handlers (lines 462-470) call `result(name, "harness", f"...", time.time() - t0)` which computes secs correctly

**Actually correct:** I checked all exception paths and they all compute `time.time() - t0`. No null `secs` found. Withdrawing this defect.

### 6. **`agent_can_write()` misses `tools` array format in config**

**Concrete failure scenario:** opencode config can specify tools as array: `"tools": ["read", "grep"]` but function only checks dictionary format `"tools": {"read": true, "write": false}`.

**Evidence:**
- Line 545-550: `tools = spec.get("tools") or {}` assumes dictionary
- Line 551: `return any(tools.get(t, True) for t in MUTATING_TOOLS)` - `tools.get()` fails on array
- Array format would be parsed as truthy non-dict, causing `tools.get(t, True)` to raise AttributeError
- Function returns `None` on exception (line Purchaser 553), allowing unsafe agent through

**Impact:** Config using array format for tools bypasses write-safety check.

### 7. **Race condition in session file writing**

**Concrete failure scenario:** Two concurrent `llm-panel` runs with same judge in same repo race to write session file, last writer wins, losing one conversation.

**Evidence:**
- Line 244-245: `session_file.parent.mkdir(parents=True, exist_ok=True); session_file.write_text(...)`
- Line 353-354: Same pattern for claude
- Line 401-402: Same for opencode
- No file locking or atomic write
- Thread safety comment only mentions SQLite contention, not session file races

**Impact:** Persistent conversations corrupted when multiple panels run concurrently.

### 8. **`consensus_view()` miscounts citations when judge cites same line multiple times**

**Concrete failure scenario:** Judge cites `bug.py:14` three times in one answer, counted as one finding, but might be discussing three different issues at that line.

**Evidence:**
- Line 513: `cites.setdefault((f.split("/")[-1], int(ln)), set()).add(j)` deduplicates by (file, line)
- Comment at line 514: "A judge citing the same line five times is one finding, not five"
- This assumes one finding per line, but a judge could identify multiple distinct issues at same line

**Impact:** Consensus table underrepresents agreement when judges cite same line for different reasons.

### 9. **Cost attribution incorrect for subscription judges**

**Concrete failure scenario:** Codex and claude judges report cost in `meta["cost"]` but this is "notional, no invoice". The summary adds them to `plan` total, suggesting they're comparable to metered costs.

**Evidence:**
- Line 671-672: `metered` sum excludes subscription judges
- Line 673-674: `plan` sum includes subscription judges
- Line 694: report says "on subscription plans (notional, no invoice): $X.XX"
- This implies quantifiable cost, but subscription models don't have per-token billing

**Impact:** Misleads user into thinking subscription judges have measurable monetary cost.

### 10. **`--vision-check` bypassed for non-vision judges**

**Concrete failure scenario:** Non-vision judge receives `--vision-check` prompt but cannot read images, returns generic failure instead of specific "CANNOT_SEE" response.

**Evidence:**
- Line 158-162: `vision_check` text prepended to prompt for ALL judges
- Line 164-168: Non-vision judges return `"unavailable"` immediately
- The `vision_check` instruction ("quote verbatim...") remains in the error message

**Impact:** Vision check contaminates error messages for non-vision judges, making failures harder to diagnose.

## Severity Ranking

1. **Anonymity breach** (Critical) - Undermines core property of rebuttal round
2. **Blame misclassification** (High) - Misattributes provider refusals as tool's fault  
3. **Double-counting cost** (High) - Users pay for unusable output
4. **Missing credential check** (Medium) - Silent auth failure
5. **`agent_can_write()` array bypass** (Medium) - Security boundary failure
6. **Session file race** (Medium) - Corrupts persistent conversations
7. **Citation miscounting** (Low) - Underrepresents consensus
8. **Cost attribution** (Low) - Misleads about subscription costs
9. **Vision-check contamination** (Low) - Noisy error messages

The code shows careful attention to failure classification and judge independence, but has concrete defects in anonymity preservation, error attribution, and cost accounting.

### Reviewer D
Looking at this code for real defects, focusing on the areas you specified.

---

## 1. CRITICAL: Anonymity breach via self-attribution in rebuttal prompt

**Location:** `run_rebuttals()`, lines ~520-525

```python
prompts[me] = (f"{prompt}\n\n---\n\nYour own review was:\n\n{results[me]['text']}"
               f"\n\n---\n\n{REBUT_INSTRUCTIONS}{blocks}")
```

**Failure scenario:** Judge A's review contains stylistically distinctive phrases, specific formatting conventions, or domain-specific vocabulary. In the rebuttal round, Judge A receives its own verbatim review with the label "Your own review was:" while simultaneously seeing anonymized reviews labeled "Reviewer B", "Reviewer C", etc. The judge can trivially match its own text to one of the anonymized reviewers by comparing writing style, identifying which "Reviewer" writes exactly as it does. This defeats anonymity—a judge knowing its own letter position can weight its responses to agree with itself or discount challenges to its own findings.

The tool explicitly states "anonymity is a correctness property" but then hands each judge its own review in the rebuttal prompt, making the "which letter am I" inference trivial for any model with self-recognition capability.

---

## 2. CRITICAL: Double-counting cost across multiple opencode steps

**Location:** `ask()` opencode section, lines ~414-419

```python
if isinstance(part.get("tokens"), dict):
    tot = meta.setdefault("tokens", {"input": 0, "output": 0})
    for k in ("input", "output"):
        tot[k] += part["tokens"].get(k) or 0
    meta["steps"] = meta.get("steps", 0) + 1
if part.get("cost") is not None:
    meta["cost"] = meta.get("cost", 0) + part["cost"]
```

**Failure scenario:** An agentic judge takes 8 steps (read, grep, read, etc.). Each `step_finish` event reports cumulative tokens (`858 in / 8741 out` on the last step alone). The code sums these: `input +=` for each step. If step 1 reports 100 in/50 out, step 2 reports 300 in/150 out (cumulative since start), the code adds 100+300=400 in when the actual usage was 300 in. Similarly for cost: if step 1 reports $0.001 and step 2 reports $0.003 cumulative, the code adds them for $0.004 when actual was $0.003.

**Evidence needed:** The comment says "every step is a separate billed call" but also says step_finish reports "858 in / 8741 out for a run that had just read a whole repo" — if that's per-step billing, it's correct. If that's cumulative, it's double-counted. The `tokens` field semantics in opencode's `step_finish` event need verification.

---

## 3. SEVERE: Thread-unsafe dict mutation in rebuttal parallel dispatch

**Location:** `run_rebuttals()`, lines ~527-529

```python
def one(me):
    # ...
    prompts[me] = (...)  # mutation of outer-scope dict
```

Called from:
```python
with cf.ThreadPoolExecutor(max_workers=len(answered)) as ex:
    rebuts = {r["name"]: r for r in [f.result() for f in [ex.submit(one, j) for j in answered]]}
```

**Failure scenario:** Multiple threads write to the `prompts` dict simultaneously. While Python's GIL makes single dict assignments atomic, dict resize operations are not. If two threads trigger resize simultaneously (when dict reaches load factor threshold), one write can be lost. The subsequent emit loop that reads from `prompts` could then miss a judge's prompt file, or write corrupted data.

**Observed behavior:** Rebuttal round completes, but `<judge>.rebuttal.prompt.md` is empty or missing for one judge. The reader has no record of what that judge was actually asked.

---

## 4. SEVERE: Incorrect error classification for malformed opencode error responses

**Location:** `ask()` opencode error parsing, lines ~389-393

```python
elif typ == "error":
    e = ev.get("error") or {}
    d = e.get("data") if isinstance(e.get("data"), dict) else {}
    err = {"name": e.get("name"), "status": d.get("statusCode"),
           "message": d.get("message") or str(e)[:400]}
```

**Failure scenario:** Opencode returns an error event where `e.get("data")` is not a dict (e.g., `null` or a string). The code sets `d = None` or `d = <non-dict>`. Then `d.get("statusCode")` raises `AttributeError: 'NoneType' object has no attribute 'get'`. This exception is caught by the outer `except Exception` handler and reported as a generic `harness` failure, masking the actual provider error that occurred.

**Result:** A legitimate provider refusal (401, 402, 403) whose opencode error envelope has an unexpected shape is reported as "our harness failed" rather than "provider refused" — the opposite of the claimed classification direction.

---

## 5. MODERATE: Timeout watchdog race in claude transport

**Location:** `ask()` claude section, lines ~266-280

```python
killer = threading.Timer(timeout, p.kill)
killer.start()
try:
    for line in p.stdout:
        # ...
    p.wait()
finally:
    killer.cancel()
```

**Failure scenario:** The timer fires while the main thread is blocked on `for line in p.stdout`. `p.kill()` is invoked. The pipe read returns remaining buffered data, then EOF. The loop completes. `p.wait()` returns. But the result dict `d` was never populated because the `result` event was cut off mid-stream. The code then checks:

```python
if not d:
    if p.returncode is not None and p.returncode < 0:
        raise subprocess.TimeoutExpired(cmd, timeout, output="".join(deltas))
```

This correctly raises `TimeoutExpired`, which is caught and reported. However, the `deltas` list may contain a partial response that gets discarded. The user sees "timed out" with no indication of what the judge was saying when killed.

**What's claimed vs reality:** The code claims to attach "the partial answer" to the timeout report, but for claude's streaming protocol, partial deltas ARE preserved in the exception output. This is actually correct, but the comment says the partial is "attached" when it's actually just thrown away and the user gets a generic timeout message.

---

## 6. MODERATE: Null cost semantics differ across transports

**Location:** Cost handling in `summary_table()` vs `cost_note()` vs opencode/orvision sections

**opencode:** `meta["cost"] = meta.get("cost", 0) + part["cost"]` — null `part["cost"]` causes TypeError when added to int.

**orvision:** `meta = {"cost": (d.get("usage") or {}).get("cost")}` — correctly handles null by propagating None.

**summary_table:**
```python
cost = r["meta"].get("cost")
money = ("—" if cost is None else "free" if not cost else f"${cost:.4f}"...)
```

**Failure scenario:** If opencode's JSON has `"cost": null` in a step_finish event, `0 + None` raises `TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'`. The entire judge fails with a `harness` error, and the user sees "TypeError" in the output with no clear indication that this was a cost-parsing bug.

**Verification needed:** Does opencode's `step_finish` ever emit `cost: null`? If so, this crashes. If `cost` is always either a number or absent, the `or 0` fallback should be added for safety.

---

## 7. MODERATE: Security bypass via opencode config tools key

**Location:** `agent_can_write()`, lines ~639-647

```python
spec = (cfg.get("agent") or {}).get(agent)
if spec is None:
    return None
tools = spec.get("tools") or {}
return any(tools.get(t, True) for t in MUTATING_TOOLS)
```

**Claimed guarantee:** "A config granting write via a `tools` key was not caught by a check that only inspected `permission`."

**Actual behavior:** The code checks `tools.get(t, True)` — absent keys default to `True` (enabled). But opencode's actual behavior is unknown here. If opencode treats an absent `tools` key as "use defaults" rather than "enable all," and defaults include write disabled, then this code incorrectly reports "write enabled" when opencode would actually deny write.

**Failure scenario:** Opencode config has:
```json
{"agent": {"panelist": {"tools": {}}}}
```
Empty `tools` dict means no explicit tool grants. Opencode's default may be read-only. But `agent_can_write()` sees empty dict, calls `tools.get("write", True)` which returns `True`, and reports "write enabled." The safety check blocks the panel, but a user passing `--unsafe-agent` to bypass gets a write-capable agent that opencode might actually deny.

**Missing:** This code's assumption about opencode's default tool behavior should be verified, not assumed.

---

## 8. MINOR: run.json field absences that violate downstream contract

**Location:** run.json emission, lines ~744-760

```python
(rundir / "run.json").write_text(json.dumps({
    "stamp": stamp, "when": now(), "repo": repo, "thread": a.thread,
    "effort": a.effort, "rebut": bool(a.rebut), "synthesize": a.synthesize,
    "images": [str(pathlib.Path(i).resolve()) for i in (a.image or [])],
    "letters": {...},
    "prompt": a.prompt,
    "judges": [{
        "name": j,
        "transport": ROSTER[j][0],
        "model": ROSTER[j][1],
        "status": results[j]["status"],
        "secs": results[j]["secs"],
        "meta": results[j]["meta"],
        "note": results[j]["meta"].get("note"),
    } for j in judges],
}, indent=1))
```

**Null-safety check:**
- `secs`: Always present (set in `result()`)
- `meta`: Defaults to `{}` in `result()`
- `note`: Can be None (via `.get("note")`)

**Failure scenario:** Downstream renderer does `{j["secs"]:.1f}` which works. But if it does `{j["note"].upper()}` on a null `note`, it crashes. The schema says `note` can be absent/null, but the claim "A downstream `{j[\"secs\"]:.1f}` already crashed on a null" — actually `secs` is always present, `note` is the nullable one.

---

## 9. ACTUALLY CORRECT: Classification logic

**Claim to verify:** "What real error lands in the wrong bucket, and in which direction does the mistake fall?"

Checking `_classify_error`:
- PROVIDER_DECLINED: 401, 402, 403 → reported as "refused"
- PROVIDER_UNAVAILABLE: 429, 503, 529 → reported as "unavailable"
- Everything else → "harness"

**Analysis:** The order in `ask()` is: (1) sandbox check, (2) completion check, (3) no-answer fault assignment. A 404 (unknown model) goes to "harness" — correct, that's our config error. A 500 goes to "harness" — correct, provider failure. A malformed response (no JSON) goes to "harness" — correct, our parsing issue.

**Verdict:** The classification logic is correct. The comment claims "Ambiguous exits default to `harness`" and that is implemented correctly.

---

## 10. ACTUALLY CORRECT: Session reuse keying

**Claim to verify:** "A judge silently running unauthenticated, or a run landing where nothing can find it."

`thread_key()`:
```python
safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:40]
return f"{safe}-{hashlib.sha256(f'{name}\0{repo}'.encode()).hexdigest()[:12]}"
```

This keys by (name, repo), so `--thread design` in repoA and repoB have different session files. The comment explains the previous bug was keying by name only, and this has been fixed.

`repo_key()`:
```python
base = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(repo.rstrip("/")) or "root")[:40]
return f"{base}-{hashlib.sha256(repo.encode()).hexdigest()[:12]}"
```

Keys by full repo path, so different repos with same basename are distinguished. Correct.

---

## Summary ranking by severity:

1. **Anonymity breach** (self-attribution in rebuttal prompt) — defeats the core correctness property
2. **Cost double-counting** (opencode step_finish token semantics) — money/billing accuracy
3. **Thread-unsafe prompts dict** — data corruption in parallel rebuttal dispatch
4. **Error envelope shape crash** (opencode error parsing) — misclassification of provider refusal
5. **Null cost addition crash** (opencode cost: null) — crash vs graceful handling
6. **Security bypass assumption** (agent_can_write default behavior) — unverified assumption