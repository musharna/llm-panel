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