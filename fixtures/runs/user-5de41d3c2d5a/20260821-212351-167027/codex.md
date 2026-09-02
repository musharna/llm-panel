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