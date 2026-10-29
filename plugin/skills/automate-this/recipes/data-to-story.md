# Recipe: Data to story

## When it fits

The person turns numbers (an export, a metrics file, a spreadsheet) into a written update for a reader: a status note, a review section, an executive summary, or a slide outline.

## What to ask

- Which file holds the numbers, and where does it come from?
- Who reads the update, and what decision or question does it serve?
- Is there a past update you liked? Ask them to drop one in as the model for tone and length.

## Inputs and checks

- The data file: `csv`, `xlsx`, or `json`. List the required columns or keys in the input checks, and a minimum row count when an empty export is a sign of a bad pull.
- The model update, when given, is read for format only.

## Facts step

Required. Every number in the story comes from a fact with an id: totals, counts, medians, changes from the last period, and how many rows were left out and why. When the file holds two periods, compute the change from the earlier one as its own fact.

## The result

- A short document: a two or three line summary, then sections in the order the reader needs.
- Every number in the text names its fact in brackets, such as "[ttm-median]", and the fact list sits at the end under "Facts used".
- When asked, add a slide outline: one line per slide with its title and the facts it uses. Building the deck itself is a separate part they can add later.
- Compare with the last period when the data has it, and say what changed in plain words.
- End with "Sources:".

## Checklist items to include

- Every number in the text matches a fact from the facts step and names its id.
- Rows left out are counted and the reason is stated.
- The change from the last period is stated when the data includes it.

## Numbers

Numbers in these updates often go to leaders. Set `exec_numbers: true` when they do. Every such number is labeled "Draft, not checked" until the person approves it through number sign-off.

## Watch out for

- Blank cells and rows that do not match: count them in the facts step and say how they were handled.
- Percent changes on small counts: give the counts too.
- Never smooth over a surprising number. Point it out and ask.

## Example requests

- "Turn this metrics file into the monthly update."
- "Write the summary for the quarterly review from this export."
