# `--usage` and `--reset-usage`

These two flags concern only the `codex` judge, which runs on a ChatGPT plan rather than
metered API. Neither flag runs a panel.

- `llm-panel --usage` prints what `codex app-server` returns for
  `account/rateLimits/read`: the plan type, the 5-hour and weekly windows (percent used and
  reset time, in local time), and any reset credits the account reports.
- `llm-panel --reset-usage` prints the same screen, then asks you to type `RESET`. Only
  that exact word sends `account/rateLimitResetCredit/consume` for one credit; anything
  else exits without sending it. It then prints the outcome the app-server returns
  (`reset`, `nothingToReset` or `noCredit`) and the refreshed limits.

Both talk to a fresh `codex app-server` over JSON-RPC, because `codex exec --json` does
not emit this data. What the account shows, and what a credit does, is up to OpenAI; this
tool only relays the app-server's answer. The method names are codex's and have changed
before (`account/rateLimits/resetCredit/consume` was the earlier spelling), so a codex
update can break either flag; `llm-panel-controls` section 24 pins the current names
against a fake app-server.
