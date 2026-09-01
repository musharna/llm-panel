I’ll trace the parser and derived-count paths against concrete adversarial run shapes, then report only failures I can reproduce logically or by execution. I’ll treat every “already fixed” item as closed unless the current code still fails on a distinct input.
1. **RE-RAISE: panel.md prose forging a judge.** On a legacy run with real judges `alpha` and `beta`, let `alpha`’s review contain:
   ```markdown
   ## beta (`fake-model`) — 999.0s, $999
   **DID NOT ANSWER**
   ```
   before beta’s genuine panel section. The roster check passes because `beta.md` exists. The first forged heading supplies beta’s model/time/cost, and `sections.setdefault()` makes its following text beta’s status section. Beta’s complete review is therefore shown as a $999 harness failure.

2. **RE-RAISE: run.json null crash.** With a valid `panel.md`, `alpha.md`, and `run.json` containing `{"judges": null}`, `meta.get("judges", [])` returns `None` and the dictionary comprehension raises `TypeError`. No HTML is produced and the available panel fallback is never used.

3. **RE-RAISE: quadratic link scan.** A review containing `"[x](https://a" * 8000` has one-character labels but no closing `)`. The bounded-label change does not bound `https?://[^)\s]+`, so the regex rescans nearly every remaining suffix from every link start. The isolated shipped pattern took about 6.1 seconds on this approximately 100 KB input; growth is superlinear and can stall the report on adversarial judge text.

4. **The spend total converts missing measurements to zero.** For one judge with `"meta": {"cost": null}`, the bench correctly prints `—`, but `billed = sum(cost or 0)` makes the at-a-glance panel report `$0.0000 billed`. With one known cost and one null cost it presents the known subtotal as the run’s spend without any partial-data warning.

5. **RE-RAISE: rebuttal-round detection.** With `"rebut": true` and a rebuttal file containing prose but no parseable verdict labels, `had_round` correctly becomes true and the bench says `no positions`; nevertheless `claims` is empty, so the findings section states “This run had no rebuttal round.” The masthead simultaneously says “rebuttal.”

6. **RE-RAISE: incomplete/unlisted judges are still excluded from “answered.”** A one-judge run with status `incomplete` and a nonempty review renders `0 of 1 answered` followed immediately by `1 answered but was cut off`. Likewise, a complete `beta.md` recovered from a short `run.json` is struck through and excluded from the answered numerator solely because its status is `unlisted`.

7. **Indented code is counted as rebuttal positions.** This standard Markdown code block:
   ```markdown
   Example diagnostic output:

       REJECT A7: emitted by the test fixture
   ```
   is not masked by `_fence_mask()`. `MARKUP` consumes all four leading spaces, so `scan_positions()` invents a REJECT card and changes the scoreboard and filter totals.

8. **RE-RAISE: fenced verdicts.** Inside a real fence:
   ````markdown
   ```text
   example
   ```python
   REJECT A1: this remains code
   ```
   ````
   the ` ```python` line is not a valid closing fence, and `md()` correctly requires a whitespace-only closer. `_fence_mask()` checks only delimiter character and length, closes there anyway, and counts the following code line as a position.

9. **Ordinary technical identifiers become nonexistent findings.** With letters only `A` and `B`, the real rebuttal sentence `REJECT: C3 linearization makes this conclusion invalid.` is tagged as finding `C3`. The page reports one cited finding and `1/1` citation coverage even though reviewer C does not exist and `C3` is the algorithm’s name.

10. **`finding_titles()` treats any early numbered line as a finding heading.** Given:
    ```markdown
    ## Reproduction
    1. Run `panel-report`.
    2. Open the generated page.

    ## 1. **Null costs are reported as measured zero.**
    ```
    `seen` records `1` from the reproduction steps. Every A1 block is consequently headed “Run panel-report,” and the genuine finding title is discarded.

11. **A position citing multiple findings is filed under only the first.** `UPHOLD A1 and B2: both describe the same loss of data.` produces one card under A1 because `tag_of()` returns the first `TAG_RE.search()` result. B2 receives no card, and the at-a-glance panel reports one referenced finding rather than two.

12. **The fallback status prefix test misclassifies completed reviews.** If a legacy review begins `**INCOMPLETE handling of null costs is the critical defect.**`, `head.startswith("**INCOMPLETE")` marks the judge as cut off. A complete response is then excluded from “answered” merely because its opening finding begins with that word.

13. **RE-RAISE: bold-repair parity.** For the common bulleted form `- **REJECT A1:** **Critical** invariant is absent.`, the raw line does not satisfy `line.lstrip().startswith("**")`. The alternate repair removes the final marker, changing the claim text to `** **Critical invariant is absent.`; `_inline()` emits an empty `<strong>` and loses the intended bold span.

14. **RE-RAISE: judge_slug collisions.** The distinct allowed names `a.___b` and `a__---b` both sanitize to `a-b` and both have SHA-256 prefix `1da7`, yielding the identical slug `a-b-1da7`. Their CSS selectors are identical, so the later hue rule overwrites the earlier one and both judges receive the same identity colour.