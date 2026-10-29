# Recipe: Keep an inherited tool running

## When it fits

The person looks after something someone else built (a scheduled data pull, a spreadsheet with formulas, a small web app) and needs it to keep working, with a clear path when it breaks.

## What to ask

- Where does it live, and how is it run?
- What goes in and what should come out?
- When did it last work, and who built it?

## Inputs and checks

- Its latest output, so a health check has something to compare with.
- The input files it uses, with their required columns.

## Facts step

Useful for a health check: read its latest output and check the counts, dates, and blanks that show it worked (for example "the newest row is from this month", "no column is empty").

## The result

- A health check: what was checked, what passed, and what looks wrong.
- The runbook: where it lives, how to run it, inputs, outputs, and who to ask.
- The "this broke" path: what to check first and the plain steps to get it running again.
- Never change where the tool lives. Prepare the change and the steps instead.
- End with "Sources:" naming the output checked.

## Checklist items to include

- States when it last worked and how that was checked.
- Lists the steps to run it in plain words.
- Says what to check first when it breaks.

## Numbers

When its output feeds numbers for leaders, set `exec_numbers: true` and treat those numbers through number sign-off.

## Watch out for

- Changes to the tool itself (its code or formulas) are prepared as drafts and never pushed, deployed, or published.
- Old output that looks fine: check its date.

## Example requests

- "Check that the metrics pull still works."
- "Write down how to run the roadmap app for my backup."
