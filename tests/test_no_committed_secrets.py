"""No credentials in the source tree.

Three passwords were committed to this repository once — a Supabase connection
string in two places and a JAXA FTP password. They are gone from the working
tree, but nothing except this test stops the next one, and a secret is only
noticed after it is public.

This is deliberately narrow: it looks for the shapes of a credential, not for
anything that resembles a password. A test that cries wolf gets deleted.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEARCHED = ("*.py", "*.js", "*.html", "*.ps1", "*.sh", "*.yml", "*.yaml")
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "vendor", "data"}

# A connection string carrying a password: scheme://user:something@host
CONNECTION_STRING = re.compile(
    r"(postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://(?P<user>[^\s:'\"]+):(?P<secret>[^\s@'\"]+)@"
)

# Documentation has to be able to show the shape of a connection string. These
# are the stand-ins that count as documentation rather than as a leak.
PLACEHOLDERS = {
    "user", "username", "password", "pass", "user:password",
    "your-password", "your_password", "xxx", "xxxx", "postgres",
}


def _is_placeholder(match) -> bool:
    user = match.group("user").strip("<>{}[]").lower()
    secret = match.group("secret").strip("<>{}[]").lower()
    return user in PLACEHOLDERS and secret in PLACEHOLDERS

# The specific secrets that were committed. Even once rotated, they must not
# come back — and history means they stay findable.
KNOWN_LEAKS = ("pWkejwZmBik1tMYr", "Niskur+1404", "uniqqsjwsqnboeuzhdyf")


def source_files():
    for pattern in SEARCHED:
        for path in ROOT.rglob(pattern):
            if SKIP_DIRS & set(path.parts):
                continue
            if path.name == pathlib.Path(__file__).name:
                continue    # this file names the leaked values on purpose
            yield path


def test_no_connection_string_with_a_password():
    offenders = []
    for path in source_files():
        for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            match = CONNECTION_STRING.search(line)
            if match and not _is_placeholder(match):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert not offenders, (
        "connection strings with embedded passwords found: "
        f"{offenders}. Read it from the environment instead — see .env.example."
    )


def test_the_previously_leaked_secrets_have_not_returned():
    offenders = []
    for path in source_files():
        text = path.read_text(errors="ignore")
        for leak in KNOWN_LEAKS:
            if leak in text:
                offenders.append(f"{path.relative_to(ROOT)} contains a known leaked value")
    assert not offenders, offenders


def test_env_example_documents_the_settings_without_values():
    example = (ROOT / ".env.example").read_text()
    for name in ("DATABASE_URL", "JAXA_USER", "JAXA_PASS", "USE_LOCAL_DATA"):
        assert name in example, f"{name} is not documented in .env.example"

    # Every line is a comment or a bare NAME= — never NAME=secret.
    for line in example.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert line.endswith("="), f".env.example holds a value: {line!r}"
