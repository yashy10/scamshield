"""Turn an email body into plain text plus the list of links it contains, and normalize domains."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

import tldextract

# Offline: use tldextract's bundled Public Suffix List snapshot, never fetch or cache to disk.
_TLD = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

_URL_RE = re.compile(r"""\bhttps?://[^\s<>"'`{}|\\^\[\]]+""", re.IGNORECASE)
_TRAILING_PUNCT = ".,;:!?)]}'\""
_MAX_URL_LEN = 2048
_SKIP_TAGS = {"script", "style", "head", "title"}
_BLOCK_TAGS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section"}


class _HTMLExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self._text: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag in ("a", "area"):
            for name, value in attrs:
                if name == "href" and value:
                    self.hrefs.append(value.strip())
        if tag in _BLOCK_TAGS:
            self._text.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag in _BLOCK_TAGS:
            self._text.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._text.append(data)

    @property
    def text(self) -> str:
        return "".join(self._text)


def html_to_text_and_links(html: str) -> tuple[str, list[str]]:
    parser = _HTMLExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # Malformed HTML: keep whatever was parsed.
        pass
    return parser.text, parser.hrefs


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_url(url: str) -> str | None:
    url = url.strip().rstrip(_TRAILING_PUNCT)
    if len(url) > _MAX_URL_LEN:
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return None
    return url


def extract_links(text: str, html: str, limit: int) -> tuple[str, list[str]]:
    """Return (readable body text, unique http(s) links in order of appearance)."""
    html_text, hrefs = html_to_text_and_links(html) if html else ("", [])
    body_text = text or html_text

    candidates = list(hrefs)
    candidates += _URL_RE.findall(text or "")
    candidates += _URL_RE.findall(html_text)

    links: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        url = clean_url(raw)
        if url and url not in seen:
            seen.add(url)
            links.append(url)
        if len(links) >= limit:
            break
    return body_text, links


def host_of(url_or_domain: str) -> str | None:
    """Lowercased, IDNA-encoded hostname from a URL or bare domain."""
    value = url_or_domain.strip()
    if "://" not in value:
        value = "http://" + value
    try:
        host = urlsplit(value).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    return host


def registrable_domain(url_or_domain: str) -> str | None:
    """e.g. 'https://login.chase-secure.co.uk/x' -> 'chase-secure.co.uk'. None for IPs or unknown suffixes."""
    host = host_of(url_or_domain)
    if not host:
        return None
    parts = _TLD(host)
    if not parts.domain or not parts.suffix:
        return None
    return f"{parts.domain}.{parts.suffix}"
