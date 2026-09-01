Reviewing as one judge. Findings below, most severe first. References are by function + quoted code (the file was given inline, so no line numbers).

---

## 1. `run.json`'s `letters` map is built from a different set than the rebuttal round used — round-2 cross-references resolve to the wrong judge

`run_rebuttals()`:
```python
answered = [j for j in judges if results[j]["status"] == "ok"]
letters   = {j: chr(ord("A") + i) for i, j in enumerate(answered)}
```
`emit`/run.json:
```python
"letters": {chr(ord("A") + i): j
            for i, j in enumerate(j for j in judges
                                  if results[j]["status"] in ("ok", "incomplete"))},
```

`incomplete` judges are excluded from round 2 but **included** in the persisted legend.

Failure: `--judges codex,big-pickle,nemotron,deepseek --rebut`, `big-pickle` returns `incomplete` (cut off at `finish_reason: "length"`). The prompts actually sent say A=codex, B=nemotron, C=deepseek. `run.json` says A=codex, B=big-pickle, C=nemotron, D=deepseek. A rebuttal that writes `REJECT: B3` means *nemotron's* finding 3; the renderer attributes it to *big-pickle* — a judge that never argued and whose review was truncated. `panel.md`'s inline legend is correct, so the two artifacts of the same run contradict each other and neither says so. This is the exact answer to "what happens to a judge that fails in round 1 but is still cited in round 2": it gets cited, under someone else's findings.

## 2. `agent_can_write()` checks four hard-coded tool names against an open set — write arrives through the tools it doesn't enumerate

```python
MUTATING_TOOLS = ("write", "edit", "patch", "bash")
...
tools = spec.get("tools") or {}
return any(tools.get(t, True) for t in MUTATING_TOOLS)
```

The docstring's own rule — "a tool key that is ABSENT means opencode enables it, so absence counts as writable" — is applied *only to those four names*. Every other tool is absent from the map and therefore enabled, and invisible to the check.

Failure: `panelist` declares `tools: {write:false, edit:false, patch:false, bash:false}`. `agent_can_write` returns `False`, the guard passes, the panel runs. The agent still has `task` (spawn a subagent — opencode's default subagent is `build`, which has the write tools) and every `mcp__*` tool from any MCP server configured for opencode, including filesystem servers. A judge asked to "check whether the fix is applied" can delegate to `build` and get the edit done. Same shape as the incident the docstring records (`permission`-only check missed `tools`) — the fix moved the blind spot rather than closing it. A correct check needs the complement: *deny-by-default*, i.e. assert the config restricts the tool set to a known-read-only allowlist, not that four specific names are false.

Secondary, same function: `CONFIG_DIR` is `$XDG_CONFIG_HOME/opencode` only. `ask()` runs `opencode run` with `cwd=repo`, and opencode merges a project-level `opencode.json`/`opencode.jsonc` found from the working directory over the global one. If that's right for your opencode version, then a repo under review that ships its own `agent.panelist` with write tools defeats the guard entirely — the file the guard reads is not the file opencode obeys, and the file opencode obeys is controlled by the thing being judged. Worth verifying against your opencode's config resolution before dismissing.

## 3. `--vision-check` never checks anything

```python
ap.add_argument("--vision-check", ... "Any judge whose answer does not contain TEXT is
                reported as unverified rather than believed.")
```
The only use of the value:
```python
if images and vision_check:
    prompt = (f"BEFORE ANYTHING ELSE, quote verbatim ... {vision_check} ...")
```
After that, `vision_check` is never referenced again. There is no comparison against `res["text"]`, and no `unverified` status exists anywhere in the status vocabulary (`ok`/`refused`/`unavailable`/`incomplete`/`harness`).

Failure: `llm-panel --image chart.png --vision-check "Q3 revenue" --judges vis-gemini "read this chart"`. Gemini confabulates, never quotes "Q3 revenue" (or writes `CANNOT_SEE` and then keeps going anyway). It is reported as `ok`, printed in full, counted in "1 of 1 judges answered", and included in `consensus_view`. The help text's own closing sentence — "A judge asserting 'I can see it' is not evidence" — describes precisely what the tool now accepts. This is a control presented as measured that does not run.

`vision_check` is also not forwarded by `run_rebuttals()` or the `--synthesize` call, so even the prompt-side instruction is dropped in round 2 while `images` is still passed.

## 4. `401`/`402` are classified `refused`, blaming the model for our credential problem — and the run then exits 0

```python
PROVIDER_DECLINED = {401: "auth rejected", 402: "out of credits", 403: "forbidden..."}
```

The tool's own pre-flight treats a *missing* key as ours:
```python
return result(name, "harness", f"no credential for {...}: ... This is a missing key on our
              side, not a refusal by the model.", ...)
```
A key that is present but expired, revoked, typo'd, or scoped wrong is the identical fact about us, and it lands in the opposite bucket. Same for 402: "out of credits" is our account balance.

Failure: `OPENROUTER_API_KEY` was rotated last week. `llm-panel --judges or-grok,or-kimi,or-qwen,or-deepseek "review this"` → four × `401` → report says **"Refused: or-grok, or-kimi, or-qwen, or-deepseek — their view is missing from this panel."** Per the module docstring that is "a fact about the judge". It is a fact about our shell environment. The docstring names this direction as the corrupting one ("crediting a model with a refusal it never made corrupts the panel's finding") and the code walks straight into it.

Compounding: `broken = [j for j in judges if results[j]["status"] == "harness"]` — only `harness` triggers the DEGRADED-PANEL banner and `sys.exit(4)`. A panel where every judge 401'd exits **0**. `run_check` has the same hole (`bad = [r for r in rows if r["status"] == "harness"]`, returns 0 otherwise), so `--check` reports success on a fully unauthenticated bench.

Related swallow that feeds this: the auth propagation
```python
try:
    if not dest.is_file() or dest.stat().st_mtime < HOST_AUTH.stat().st_mtime:
        shutil.copy2(HOST_AUTH, dest)
except OSError:
    pass  # fall through; the provider will report the failure honestly
```
The provider reports it as `refused`. That is not honest, it is the inversion above.

## 5. Rebuttal-round and synthesis spend is never counted anywhere

The Cost section, `summary_table()` and `run.json` are all computed from `results`, which contains **round 1 only**. `run_rebuttals()` returns `rebuts` and `main()` discards it (`rlines, _ = run_rebuttals(...)`). The `--synthesize` call's `s["meta"]` is likewise dropped.

Failure: `--judges or-glm,or-grok,or-kimi,or-deepseek --rebut --synthesize or-grok --diff`. That is 9 billed calls (4 + 4 + 1), with round-2 prompts *larger* than round 1 (they carry every other judge's full review). The report prints `- billed: **$X**` where X covers 4 of the 9. The renderer reading `run.json` sees the same 4. There is no field in `run.json` from which the missing spend could be recovered — round 2 has no status, no `secs`, no `meta`, only the `<judge>.rebuttal.md` text.

Two further ways the money number is wrong in the same block:

```python
metered = sum(results[j]["meta"].get("cost") or 0 for j in judges if ...)
```
`.get("cost") or 0` folds *unknown* into *zero*. The opencode branch only sets `meta["cost"]` if a `step_finish` carried one; the `orvision` branch reads `usage.cost`, which OpenRouter omits unless the request asks for it — and the request here doesn't (`payload` has no `usage: {include: true}`). So `vis-gpt` and `vis-grok`, which are metered OpenRouter calls costing real money, contribute `0` to a line printed as **"billed: $0.0000 (nothing metered)"**. The per-judge list is honest ("no cost reported"); the total that the reader will actually quote is not.

And `plan`: a `claude` judge whose `total_cost_usd` is `0.0` or `null` makes `plan == 0`, so the report prints "- on subscription plans: none used" for a run in which a subscription judge did run. The `codex` judge is on the ChatGPT plan per the roster comment but its branch never builds a `meta` at all, so it contributes neither tokens nor a `billing` marker — yet the tokens line still reads "across {len(judges)} judges".

## 6. Reviewer letters are deterministic and derivable, so the anonymisation is reversible

```python
letters = {j: chr(ord("A") + i) for i, j in enumerate(answered)}
others  = [o for o in answered if o != me]
```
No shuffle, no per-judge relabelling. Letters are assigned in `judges` order, which is either the literal `--judges` string or `DEFAULT`. Each judge sees exactly one letter missing from the sequence it receives, which tells it its own index; and the ordering is the roster ordering.

Failure, and it is the tool's own primary use case: `llm-panel --rebut --diff` inside the llm-panel repo. The round-2 prompt begins with `prompt`, which for `--diff` contains the working-tree diff of this file — including `ROSTER` and `DEFAULT = ["codex", "big-pickle", "nemotron", "deepseek"]` — plus `letters = {j: chr(ord("A") + i) for i, j in enumerate(answered)}` itself. A judge holding that source can map A→codex, B→big-pickle, C→nemotron, D→deepseek directly, and confirm its own slot from the gap. Round two is then de-anonymised for every judge simultaneously, and the tool reports it as anonymous. A per-judge random permutation of letters (recorded in `run.json` per judge) closes it; a global stable ordering cannot.

## 7. `--diff` builds a prompt that can exceed Linux's single-argument limit, killing every subprocess judge at once

All three subprocess transports pass the prompt as one argv element (`cmd + [prompt]` for opencode, `[..., prompt]` for codex, `["-p", prompt]` for claude). Linux caps a *single* argument string at `MAX_ARG_STRLEN` = 128 KiB, independent of the total `ARG_MAX`.

`collect_diff()` puts no cap on the diff itself (`diff = git("diff", "HEAD")`) and budgets untracked file bodies at `budget = 200_000` — 1.5× the per-argument ceiling on its own.

Failure: a branch with a 300 KB diff (a lockfile regeneration, a vendored dir, a generated schema). `execve` returns `E2BIG`; `subprocess.run` raises `OSError: [Errno 7] Argument list too long`, which is caught by `except Exception as e:` and reported as `harness: OSError: [Errno 7] Argument list too long` for **codex, every opencode judge, and every claude judge** — while `ollama` and `orvision` judges (HTTP bodies, no argv) answer normally. The panel prints DEGRADED and exits 4 with an error message that names neither the prompt size nor `--diff`. Fix is to pass the prompt on stdin or via a temp file for the CLI transports, and to bound the diff the way untracked files are bounded.

## 8. `urlopen(timeout=)` is a per-read socket timeout, not a deadline — an ollama judge can hang past `--timeout` indefinitely

```python
with urllib.request.urlopen(req, timeout=timeout) as resp:
    for raw_line in resp:
        d = json.loads(raw_line.decode())
```
The timeout applies to each socket operation. A model that keeps emitting tokens never idles that long.

Failure: `local-qwen` enters a degenerate repetition loop and streams one token every few hundred ms. With `--timeout 900` the panel waits forever; the heartbeat prints `… 4200s — still working: local-qwen` and the run never completes. Meanwhile the model holds 21 GB of a shared 24 GB card for the whole time (`keep_alive` only governs residency *after* the answer). Same structure in the `orvision` branch. Both need an explicit wall-clock deadline checked inside the read loop.

Secondary in the same branch: if the socket *does* time out mid-stream, the resulting `TimeoutError` is caught by the generic `except Exception` and returns `harness: TimeoutError: ...` with `chunks` discarded — so unlike the claude path, an ollama judge's partial answer is thrown away rather than attached.

## 9. The claude judge's tool denylist omits the tool that grants every other tool

```python
"--disallowedTools", "Write,Edit,NotebookEdit,Bash"
```
`Task` is not denied. Neither are MCP tools (`mcp__*`), `WebFetch`, or `KillShell`/`BashOutput`. A denylist here has the same open-set problem as finding 2, but with a sharper instance: a subagent spawned via `Task` does not inherit `--disallowedTools`, and gets the default tool set including `Write`, `Edit` and `Bash` in the same `cwd=repo`.

Failure: `--judges claude-opus --diff "review these changes"` in a live working tree. The judge decides to test its hypothesis, spawns a subagent to "run the test suite and report", and the subagent writes a scratch file and runs `pytest` in the tree the panel is reviewing. The panel reports `ok` and prints the review. The comment above this line documents that `--allowedTools` was already found insufficient; the same reasoning applies to an enumerated denylist.

## 10. Round 2 instructs judges to reference numbers that round 1 never asked them to produce

```python
REBUT_INSTRUCTIONS = ("... Each reviewer NUMBERED their findings. Refer to one as
                       <Letter><number> -- B7 is Reviewer B's finding 7. ...")
```
Round 1's prompt is whatever the user typed. Nothing in `main()` or `emit()` appends a numbering instruction, and `run_rebuttals` pastes `results[o]['text']` verbatim without adding numbers.

Failure: `llm-panel --rebut --diff "review my changes"`. Round-1 answers come back as prose with `##` headings and bullets, no numbering. Round 2 is told the findings are numbered, so judges either invent numbers that map to nothing, or describe findings in their own words — which the instructions themselves say gets the position "dropped from the panel's grouped view and argues with nobody". Either the round-1 prompt must carry the numbering requirement, or `run_rebuttals` must number the blocks mechanically before pasting them (which it can do reliably and the model cannot).

## 11. `CITE` matches non-citations, inventing consensus rows and disabling the bare-line path as collateral

```python
CITE = re.compile(r"([A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,6}):(\d+)")
```
The character class includes `/` and `.` and excludes only `:`, so any `host:port` or dotted token followed by `:digits` matches.

Failure, live, on this very review: this file contains `http://127.0.0.1:11434` and `openrouter.ai/api/v1/chat/completions`. Any two judges that quote the ollama host produce a `cites` entry `("127.0.0.1", 11434)` with two judges in it — printed as a row in **"Where the judges pointed at the same code"** with `2/4`, a location that is not code and not a line number. `example.com:8080`, `v1.2:3`, and `12.30:45` behave the same way.

The knock-on is worse than the phantom row. `files = {f for f, _ in cites}` — one bogus host adds a second "file", so `len(files) == 1` goes false and **every** bare `line N` reference from every judge is dropped into `unresolved` and reported as "ambiguous and was not guessed at". A four-judge panel on a single-file diff where one judge quotes a URL loses the entire bare-line resolution path, producing exactly the undercount the `BARE_LINE` comment says it was added to prevent.

Separately, the bare-line guard is weaker than its docstring claims: `files` counts only files cited *in `file:line` form*. Two files in the diff, but only one judge used colon-line syntax → `len(files) == 1` → another judge's "line 14", which was about the *other* file, is attributed to the cited one. The check should key off the number of files in the material under review, not the number that happened to be cited in the strict form.

## 12. The vision transport can never report `unavailable`, so a rate limit there triggers the degraded-bench alarm

```python
if "image input" in body or e.code in PROVIDER_DECLINED:
    return result(name, "refused", ...)
return result(name, "harness", f"OpenRouter {e.code}: {body}", ...)
```
`PROVIDER_UNAVAILABLE` is never consulted in this branch. A `429` from OpenRouter reaches `harness`.

Failure: `--judges or-grok,vis-grok "..."`, both hit OpenRouter's per-account rate limit at the same instant. `or-grok` (opencode path, `_classify_error`) reports `unavailable` — "retryable, says nothing about the question". `vis-grok` reports `harness` — "OUR plumbing", triggers `!! DEGRADED PANEL`, and exits 4. Identical upstream response, opposite blame, and a non-zero exit that will fail any script wrapping this.

## 13. The "cache dir is inside the repo" guard misses a relative `XDG_CACHE_HOME`

```python
if str(STATE) == repo or str(STATE).startswith(repo.rstrip("/") + os.sep):
```
`repo` is absolutised (`os.path.abspath(a.cwd)`); `STATE` is not, and no symlink resolution happens on either side.

Failure: `XDG_CACHE_HOME=.cache llm-panel --diff --rebut "review this"`. `STATE` is the relative path `.cache/llm-panel`, `startswith("/home/...")` is false, the guard stays silent — and every relative path then resolves against the process's cwd, which is the repo. Each judge's answer is written by `emit()` into `<repo>/.cache/llm-panel/runs/.../<judge>.md` *the moment it finishes*, while the slower judges are still running with read access to that tree, and the whole set is sitting there for round 2. The property the guard exists to protect is defeated by the case the guard cannot see. Same for `~/.cache` symlinked into the repo. `STATE = pathlib.Path(...).resolve()` before comparing, against `os.path.realpath(repo)`, closes both.

## 14. A corrupt ollama session file makes the header claim memory the judge does not have

The banner and the `panel.md` header both use `read_session()` for non-codex transports:
```python
alive = [j for j in judges if (codex_session_id(sessions[j], repo)
                               if ROSTER[j][0] == "codex" else read_session(sessions[j]))]
hdr += "**Thread `...`** — judges carrying memory of earlier turns: " + ", ".join(alive)
```
But `ask()` loads it defensively:
```python
try:
    ctx = json.loads(session_file.read_text())
    if isinstance(ctx, list) and ctx:
        payload["context"] = ctx
except (OSError, ValueError):
    pass
```
Failure: `local-llama.session` is truncated by an interrupted write (the file is rewritten in full on every turn, non-atomically). `read_session` returns the non-empty garbage → the judge is listed as "resuming" and as "carrying memory of earlier turns"; `json.loads` throws inside `ask` → the judge answers with no context at all, silently, forever after. This is the same defect `codex_session_id()`'s docstring says was fixed for codex ("a status line reporting the opposite of what happened") — the fix was never extended to the ollama or claude paths.

---

## Smaller, but real

- **`run.json` nullability, since you asked which fields a renderer can't trust.** `secs` is *not* one of them — `result()` always writes `round(secs, 1)`, so a downstream crash on a null `secs` came from a rebuttal/synthesis entry the renderer synthesised itself, or from a `run.json` written by an older version, not from this writer. What *is* absent or null: `thread`, `effort`, `synthesize` (null when unflagged); `judges[].note` (null for every judge except `incomplete` ones); `judges[].meta` is `{}` for **every codex judge, success or failure** (that branch never builds a meta) and for all early-failure paths in the other transports, so `meta.tokens` and `meta.cost` are *absent keys*, not nulls; `meta.cost` is additionally `null` from the claude and orvision branches; `letters` can be `{}`. And `run.json` is written only at the very end, so a killed or crashed run leaves `<judge>.md` files with no `run.json` at all — contradicting the docstring's "a panel killed halfway still leaves the answers it did collect".
- **`emit()` is not defensive but `write_live()` is.** An `OSError` from `(rundir / f"{judge}{tag}.md").write_text(...)` inside `run_rebuttals.one()` propagates through `f.result()` and kills `main()` *after* both rounds have been paid for and before `panel.md` is written. Given the design intent above, this should be wrapped like `write_live`.
- **`writable is None` is reported as one cause when it has three.** `agent_can_write` returns `None` for "agent not in config", for `json.loads` failure, and for `OSError`. The die message says "it is not defined in your opencode config". A `opencode.jsonc` with a `/* block comment */` or a trailing comma — both legal jsonc, and the file is named `.jsonc` — survives the `^\s*//.*$` strip, fails `json.loads`, and tells the user their agent doesn't exist when it does.
- **`--keep-alive` is ignored in round 2 and in synthesis.** Both call sites hardcode `"60s"`. An ollama judge mid-thread with `--keep-alive 30m` gets evicted from VRAM between rounds and reloads.
- **The position tally over-counts.** `rf"^\s*\**{k}\**[^:\u2014\u2013]{{0,24}}?\s*[:\u2014\u2013]\s"` with `re.I` matches a line beginning "Rejecting the premise: …" as a `REJECT` position (the lazy `{0,24}` swallows " ing the premise"). The block is captioned "labels the judges used", which is then not what it counted.
- **`--runs` lists rebuttals as judges.** `judges_ran` excludes `.prompt.md` and `.live.md` but not `.rebuttal.md`, so `f.stem` yields `codex.rebuttal` alongside `codex` and a 4-judge run prints 8 judges.
- **`stored_providers()` returning `set()` "on any read failure"** turns a transient `EACCES`/`EINTR` on `auth.json` into a pre-flight `harness` abort for every OpenRouter and HuggingFace judge, before a request is ever attempted. The message asserts there is "neither `$VAR` in the environment nor an entry in `<path>`" — an assertion about file contents that was never read.

## Looks wrong, is correct

- **`--check` re-expanding the roster after the write-safety guard.** The argparse comment implies this is still a live hazard. It isn't: `agent_can_write(a.agent)` is scoped to the *agent*, not to the judge list, so widening the judge set afterwards cannot change the verdict. The guard does still fire, because `DEFAULT` contains opencode judges.
- **`shutil.copy2` + `dest.stat().st_mtime < HOST_AUTH.stat().st_mtime`.** `copy2` preserves mtime, so the two are equal after a copy and the strict `<` correctly never re-copies. The only miss is a source file with a *backdated* mtime (restore from backup, `cp -p` from another host) — worth a comment, not a code change.
- **Filtering `chrome` to lines not starting with `{`.** Correct for JSONL: opencode's own warnings are bare lines and the model's answer is inside a JSON string with newlines escaped, so the answer can't reach the guard even when it quotes the guard's own text.
- **Last-write-wins on `meta["finish"]` in the opencode branch.** Reads like the bug the token-summing comment describes, but is right — an agentic run's final `step_finish` is the one whose reason describes the answer.Two claims in that review rest on recall of external system behaviour rather than on the source you gave me. Flagging them rather than leaving them as assertions:

**Recall-based, not verified this turn:**

- **Finding 7 (`E2BIG`)** — I asserted Linux caps a *single* argv string at `MAX_ARG_STRLEN` = 128 KiB independent of total `ARG_MAX`. Everything source-side is solid (the prompt is one argv element in all three CLI transports; `collect_diff` caps untracked bodies at 200,000 bytes and does not cap the diff at all). The exact ceiling is recall. Falsifier: `python3 -c 'import subprocess; subprocess.run(["true", "x"*200_000])'` — if that succeeds, the finding shrinks to "unbounded prompt growth" and loses its concrete trigger point.
- **Finding 9 (`Task` escape)** — that `--disallowedTools` does not propagate to a subagent spawned via `Task` is recall about the Claude CLI, not something the file shows. What the file *does* show stands on its own: `Task`, `WebFetch` and `mcp__*` are absent from the denylist, which is the same open-set problem as finding 2. Falsifier: run a claude judge with the panel's exact flags and ask it to delegate a write.
- **Finding 2, second half** — already flagged inline; opencode's project-level config precedence is recall.
- **Finding 5** — "OpenRouter omits `usage.cost` unless the request asks for it" is recall. The source-side half is not: the `orvision` payload contains no usage-accounting field, and `meta["cost"]` is read from `usage.cost`, so if that key is ever absent the judge's spend is summed as `0` into a line printed as *billed*.
- **Finding 8** — that `urlopen(timeout=)` is a per-socket-operation timeout rather than a deadline is documented stdlib behaviour, but I did not confirm it this turn.

**On the remediation sentences.** Where I wrote "fix is to pass the prompt on stdin", "a per-judge random permutation closes it", "`STATE.resolve()` before comparing" — treat those as directions, not diagnosed causes. I did not run the three-hypothesis gate on any of them, and a review of a static file cannot: I have no failing run to attribute. What I can stand behind is the observation in each case (the prompt is one argv element; letters come from `enumerate(answered)` with no shuffle; `STATE` is never absolutised while `repo` is). Deciding the cause of any *observed* failure, and what to change, needs the mechanism test against a real run.

The source-only findings — 1, 3, 4, 6, 10, 11, 12, 13, 14 and the first half of 2 — depend on nothing outside the file and are unaffected by the above.