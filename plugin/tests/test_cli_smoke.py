import subprocess, sys, pathlib
JA = pathlib.Path(__file__).parents[1] / "scripts" / "ja.py"

def run(*a, cwd=None):
    return subprocess.run([sys.executable, str(JA), *a], capture_output=True, text=True, cwd=cwd)

def test_help_lists_commands():
    r = run("--help")
    assert r.returncode == 0
    for cmd in ["init", "tools", "index", "dashboard", "record", "ledger", "check"]:
        assert cmd in r.stdout
