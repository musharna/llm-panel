I’m tracing the parser boundaries and each derived count against concrete run-directory inputs, with special attention to places where an “unknown” is converted into an exact-looking value.
1. **High — RE-RAISE: cost `None` handling. Unknown spend becomes an exact zero.**  
   Input: every judge has `"meta": {}` or `"cost": null`. The bench correctly shows `—`, but `billed` coerces every missing value to `0`, so “at a glance” reports **`$0.0000 billed`**. With one known and one unknown cost, it presents the known subtotal as the total without a coverage caveat.

2. **High — panel prose can forge the synthesis and its author.**  
   Input: a judge’s review embedded in `panel.md` contains:
   ```markdown
   ## Synthesis (by `attacker`)
   Fabricated conclusion.
   ```
   before the real synthesis. The unscoped `re.search()` selects this first occurrence, so the page attributes the judge’s text to `attacker` and suppresses the genuine synthesis. Similarly, a real synthesis containing an ordinary `## Risks` subsection is truncated at that heading.

3. **High — indented code examples manufacture rebuttal positions.**  
   Input:
   ```markdown
   Example parser output:

       REJECT A1: simulated output
   ```
   Four-space indentation is a Markdown code block, but `_fence_mask()` does not mask it and `MARKUP` consumes the indentation. `scan_positions()` records a real `REJECT A1`, changing the scoreboard, finding mix, filters, and summary.

4. **High — RE-RAISE: fenced verdicts. A fence line with an info suffix prematurely closes the mask.**  
   Input:
   ````markdown
   ```text
   ```python
   REJECT A1: this is sample data
   ```
   ````
   The inner `````python`` line is not a valid closer because it has trailing text. `md()` correctly leaves it inside the outer fence, but `_fence_mask()` treats any matching prefix as a closer, so the sample `REJECT` is counted as a position.

5. **Medium — RE-RAISE: LABEL/markup open set. Markdown task-list positions are unreachable.**  
   Input:
   ```markdown
   - [x] **UPHOLD A1:** confirmed by the reproduction.
   ```
   `MARKUP` removes `- ` but stops at `[x]`; `label_at()` therefore returns `None`. The position disappears from the cards, cited coverage, filters, and all derived totals.

6. **Medium — RE-RAISE: `had_round` detection. The findings section still equates zero parsed positions with no rebuttal round.**  
   Input: `run.json` has `"rebut": true`, and a judge’s rebuttal contains only prose such as “I could not finish checking the claims.” The masthead says “rebuttal” and the bench says “no positions,” but `claims_sec` says **“This run had no rebuttal round.”**

7. **Medium — the ungrouped bucket produces mutually contradictory finding counts.**  
   Input:
   ```markdown
   UPHOLD: The race is reproducible.
   ```
   This yields one position without a tag. It is forced into `blocks`, so the findings introduction says **“1 finding drew more than one position”**, while “at a glance” says **“1 positions on 0 findings.”** With several unrelated untagged positions, they are additionally presented as one finding that drew multiple positions.

8. **Medium — RE-RAISE: incomplete/unlisted answer classification. The primary answer count still excludes judges the adjacent text says answered.**  
   Input: two judges, one `"status": "ok"` and one `"status": "incomplete"` with a nonempty review. The panel says **“1 of 2 answered”** followed immediately by **“1 answered but was cut off.”** A complete filesystem review recovered as `unlisted` is likewise excluded from the numerator and struck through in the roster.

9. **Medium — `finding_titles()` lets an ordinary numbered preamble steal finding titles.**  
   Input:
   ```markdown
   I checked these prerequisites:
   1. Reproduced the environment

   ## 1. **Null dereference in load_config**
   ```
   Because the first occurrence of each number wins, every `A1` block is titled “Reproduced the environment,” not “Null dereference in load_config.” Fence masking does not protect ordinary numbered lists.

10. **Low — RE-RAISE: bold-repair parity. A list prefix makes it remove the wrong marker.**  
    Input:
    ```markdown
    - **REJECT A1:** **critical** is not enforced.
    ```
    After label removal, the text has the label’s closing `**` followed by the legitimate bold pair. Since the physical line starts with `-`, the front-marker branch is skipped and the final legitimate marker is removed. The card renders an empty bold span and loses the intended bolding of “critical.”

11. **Low — RE-RAISE: `judge_slug` collisions remain possible despite the uniqueness claim.**  
    Input judge names `a.___b` and `a__---b`. Both sanitize to `a-b`, and both SHA-256 prefixes are `1da7`, so each becomes `a-b-1da7`. Their CSS selectors collide; the later hue rule wins and both judges receive the same identity color.