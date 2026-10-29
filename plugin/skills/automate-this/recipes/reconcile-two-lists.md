# Recipe: Reconcile two lists

## When it fits

The person compares two lists that should agree (an export against an inventory, a tracker against a system of record) and needs to see what matches, what is missing on each side, and what is incomplete.

## What to ask

- Which column links the two lists (for example the offering name or an ID)?
- Which list is the reference when they disagree?
- Which blank fields matter (for example a missing completion date)?

## Inputs and checks

- Two files, usually `csv` or `xlsx`. In the input checks, list the key column and every column the result uses as required columns for each file, so the files can be given in any order.
- Add a minimum row count for each when an empty export means a bad pull.

## Facts step

Required. It must:

- Build the matching key the same way for both lists: trim spaces at both ends, collapse inner spaces, and ignore upper and lower case. Report how many names matched only after this cleanup.
- Count rows in each list, matched keys, keys only in the first list, and keys only in the second list. Put the unmatched names in the fact notes.
- Count blank values in each column that matters.
- Count keys that appear more than once in either list.
- Never drop a row silently. Every row ends up matched, unmatched, or counted as a problem.

## The result

- A short summary: how many matched, how many did not on each side, how many blanks.
- How the names were matched, in one sentence (for example "Names were matched ignoring case and extra spaces; 3 matched only after that").
- A table of rows only in the first list, then a table of rows only in the second list.
- The blank counts per column, and which rows they are when there are few.
- End with "Sources:" naming both files and their export dates.

## Checklist items to include

- States the matching key and how names were cleaned before matching.
- Lists every unmatched row from each list by name.
- Counts the blank values in each column that matters.
- Every count in the text matches the facts step.

## Numbers

Counts here are usually for the person's own work. Set `exec_numbers: true` only when the counts go to leaders.

## Watch out for

- Names that differ only by case or a trailing space: they match after cleanup, and the result says how many.
- Names that are truly different spellings: list them as unmatched; never guess a match.
- Duplicate keys: count and list them instead of keeping one at random.

## Example requests

- "Match the offering export against the inventory."
- "Which offerings are missing from the tracker?"
