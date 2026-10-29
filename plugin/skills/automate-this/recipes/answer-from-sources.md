# Recipe: Answer from sources

## When it fits

The person gets the same kinds of questions again and again (in chat, email, or meetings) and the answers live in approved documents such as an FAQ, a policy, or a process guide.

## What to ask

- Which documents hold the approved answers? Add each to the sources list if it is not there.
- Where do the questions come from, and who asks them?
- Should the answer be short enough to paste into a chat, or a longer email?

## Inputs and checks

- The questions: pasted text, a text file, or a screenshot of a thread. Expect `txt` or `md`.
- The source documents: read live through a connected service when possible, otherwise a copy in the inbox with its export date recorded. Expect `md`, `txt`, or `pdf`.
- A living document copy older than its freshness limit makes the tool show "Needs update". Say so before answering.

## Facts step

Usually none. Add one only when answers need counts or dates computed from a data file.

## The result

- One answer per question, in the order asked.
- Each answer quotes or closely follows the source and cites the exact section: document name, section heading, and a link when there is one.
- A question the sources do not cover gets the reply "Not covered by the approved sources." Add it to `assistant/gaps.md` as one line: the date, the question, and who asked if known. Create the file with the heading "Questions the sources do not answer" if it does not exist.
- Never answer from general knowledge without saying plainly that the answer is not from their sources.
- End with "Sources:" listing each document and section used.

## Checklist items to include

- Every answer cites a document and section heading from the sources list.
- Every question the sources do not cover says so and is added to the gaps list.
- No answer adds facts that are not in the cited section.

## Numbers

Quote numbers exactly as the source states them, with the source. Do not round or update them.

## Watch out for

- Two sources that disagree: show both, with their sections, and say they disagree.
- Old copies of living documents: check the export date first.
- Questions that ask for an opinion or a decision: draft a reply that points to the owner instead.

## Example requests

- "Answer these questions from the FAQ."
- "Draft replies to the questions in this thread using our process guide."
