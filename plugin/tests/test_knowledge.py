"""Facts the person teaches, each with its source."""

T = "2026-10-29"


def run(cli, ws, *args):
    return cli("--workspace", str(ws), "--today", T, "knowledge", *args)


def text(ws):
    return (ws / "assistant/knowledge.md").read_text(encoding="utf-8")


def test_add_appends_with_source_and_date(ws, cli):
    (ws / "assistant/knowledge.md").write_text("# What I have been taught\n\nEach entry: the fact.\n", encoding="utf-8")
    r = run(cli, ws, "add", "--fact", "Launch reviews happen on Tuesdays.", "--source", "per Sam, 2026-10-29")
    assert r.returncode == 0, r.text
    assert "Saved" in r.stdout
    assert text(ws).endswith("- Launch reviews happen on Tuesdays (Source: per Sam, 2026-10-29. Added 2026-10-29.)\n")
    assert text(ws).startswith("# What I have been taught\n")


def test_add_needs_a_source_and_a_fact(ws, cli):
    r = run(cli, ws, "add", "--fact", "Something.", "--source", "  ")
    assert r.returncode == 1 and "Every fact needs a source" in r.stderr
    r = run(cli, ws, "add", "--fact", " ", "--source", "FAQ")
    assert r.returncode == 1 and "Say the fact" in r.stderr


def test_add_keeps_one_line_and_creates_the_file(ws, cli):
    r = run(cli, ws, "add", "--fact", "Two\nlines <!-- x -->", "--source", "FAQ section 3.")
    assert r.returncode == 0
    assert text(ws) == ("# What I have been taught\n\n"
                        "- Two lines x (Source: FAQ section 3. Added 2026-10-29.)\n")


def test_list_and_forget(ws, cli):
    assert run(cli, ws, "list").stdout.strip() == "Nothing taught yet."
    run(cli, ws, "add", "--fact", "Launch reviews happen on Tuesdays", "--source", "per Sam, 2026-10-29")
    run(cli, ws, "add", "--fact", "Pricing reviews happen monthly", "--source", "Pricing guide")
    r = run(cli, ws, "list")
    assert r.stdout.splitlines() == [
        "Launch reviews happen on Tuesdays (Source: per Sam, 2026-10-29. Added 2026-10-29.)",
        "Pricing reviews happen monthly (Source: Pricing guide. Added 2026-10-29.)"]
    r = run(cli, ws, "forget", "reviews")
    assert r.returncode == 1 and "More than one entry matches" in r.stdout
    assert "Pricing reviews happen monthly" in r.stdout
    r = run(cli, ws, "forget", "nothing like this")
    assert r.returncode == 1 and "I could not find anything taught about nothing like this." in r.stderr
    r = run(cli, ws, "forget", "PRICING")
    assert r.returncode == 0 and r.stdout.strip() == "I will no longer use this: Pricing reviews happen monthly."
    assert "Pricing" not in text(ws) and "Launch reviews" in text(ws)
