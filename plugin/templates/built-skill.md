---
name: {{skill_name}}
description: {{description}}
allowed-tools:
  - {{allow_quoted}}
  - {{allow_plain}}
---

# {{name}}

{{does}}

Follow these steps each time the person asks for this. Talk in plain business English and show them nothing technical.

## The helper

Below, `ja <action>` means this line, run from the assistant folder:

```
uv run --script "{{ja_path}}" <action> [details]
```

If that line says the file does not exist, the kit was updated. Use the path on the `ja_path:` line of `assistant/.job-assistant` instead.

## What to ask for

<!-- fill: what to ask for. List only what this tool needs and the person may not have given yet, at most three questions, one at a time. -->

## Check the input

Run `ja input check {{id}} <files>` with the files they gave, in the order this tool expects. If it reports a problem, tell them plainly what is wrong and show the numbered steps it prints. Do not go on until the right file is in.

## Facts

Run `ja facts run {{id}} <files>`. Use the facts exactly as it prints them, with their sources. Never count, add up, compare dates, or match names yourself. If it says this tool has no facts step, skip this section.

It also prints when each file was received. In the result, give each file's export date if the person told you. Otherwise write "Export date: unknown" and the date it was received.

## Learned rules

Run `ja rules for {{id}}` before you write the result. Follow every rule it prints. They come from the person's own corrections.

## Write the result

<!-- fill: how to write the result. Say what goes in it, in what order, for which reader, and where each fact goes. -->
{{number_signoff}}
## Finish

1. Check the result against every item in `checklist.yaml` in this folder before showing it.
2. End with "Sources:" naming each source used. When `ja rules for {{id}}` printed rules, add "Rules used:" with the short name of each one you followed.
3. Ask: "Does this look right?" On corrections, fix the result and show it again.
4. When they say it looks right, run `ja record accepted {{id}}`. Offer to keep it as an example for future checks. On yes, save the result as `inbox/{{id}}-result.md` and run `ja proof save {{id}} --input <files> --output inbox/{{id}}-result.md`.
