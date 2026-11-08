from scamshield.links import extract_links, registrable_domain
from scamshield.notify import compose, defang
from scamshield.redact import redact


def test_extract_links_from_html_and_text_dedupes_and_skips_non_http():
    html = """
    <html><head><style>.x{}</style><title>t</title></head><body>
      <p>Your account is locked.</p>
      <a href="https://login.chase-secure-login.com/verify?id=1">Verify now</a>
      <a href="mailto:help@chase.com">mail</a>
      <a href="https://login.chase-secure-login.com/verify?id=1">again</a>
      <script>var u = "https://tracker.example.net/x";</script>
    </body></html>"""
    text = "Or visit https://chase.com/help."
    body, links = extract_links(text, html, limit=10)
    assert links == ["https://login.chase-secure-login.com/verify?id=1", "https://chase.com/help"]
    assert "Or visit" in body


def test_extract_links_uses_html_text_when_no_plain_part():
    body, links = extract_links("", "<div>Pay at http://pay.example.xyz/now</div>", limit=10)
    assert links == ["http://pay.example.xyz/now"]
    assert "Pay at" in body


def test_extract_links_respects_limit():
    html = "".join(f'<a href="https://site{i}.com/">x</a>' for i in range(20))
    _, links = extract_links("", html, limit=3)
    assert len(links) == 3


def test_registrable_domain():
    assert registrable_domain("https://login.chase-secure.co.uk/a/b") == "chase-secure.co.uk"
    assert registrable_domain("WWW.Example.COM") == "example.com"
    assert registrable_domain("http://192.168.0.1/login") is None
    assert registrable_domain("not a domain") is None


def test_redact_removes_personal_details_but_keeps_amounts():
    text = (
        "Dear Margaret Smith, your card 4111 1111 1111 1111 was charged $1,250.00. "
        "Call (555) 123-4567 or email support@bank-help.com. Account 12345678. "
        "Your grandson Alex says hi. See https://evil.example.com/x"
    )
    out = redact(text, known_names=["Alex"])
    assert "Margaret" not in out and "Smith" not in out
    assert "4111" not in out and "12345678" not in out
    assert "555" not in out and "support@bank-help.com" not in out
    assert "Alex" not in out
    assert "evil.example.com" not in out
    assert "$1,250.00" in out


def test_defang():
    assert defang("Go to https://evil.com/login now") == "Go to hxxps://evil[.]com/login now"
    assert defang("The website chase-secure.xyz was created 3 days ago.") == (
        "The website chase-secure[.]xyz was created 3 days ago."
    )


def test_guardian_copy_never_contains_subject():
    common = dict(
        verdict="scam",
        reasons=["The website was created 3 days ago."],
        protected_label="Margaret",
        sender_domain="chase-secure.xyz",
    )
    user_msg = compose(to="g@example.com", for_guardian=False, original_subject="Account locked", **common)
    guardian_msg = compose(to="a@example.com", for_guardian=True, original_subject=None, **common)
    assert "Account locked" in user_msg.text
    assert "Account locked" not in guardian_msg.text and "Account locked" not in guardian_msg.html
    assert "likely a scam" in user_msg.text
    assert "Margaret" in guardian_msg.subject
    assert "chase-secure[.]xyz" in guardian_msg.text
    assert "delete it" in user_msg.text
