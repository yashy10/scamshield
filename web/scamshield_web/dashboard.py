"""What the dashboard shows: who the signed-in account can see, and one inbox's results over a period.

A protected person sees their own inbox. A guardian sees the inboxes they were linked to, but not
email subjects, matching the warnings they get by email ("you see warnings only").
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, tzinfo

from scamshield.store import EmailRecord, Invite, Store, UserProfile

PERIODS = {"7": ("Last 7 days", 7), "30": ("Last 30 days", 30), "all": ("All time", None)}
DEFAULT_PERIOD = "30"

# Status colors carry meaning, so they're fixed and always shown with an icon and words.
COLORS = {"scam": "#d03b3b", "suspicious": "#fab219", "safe": "#0ca30c", "empty": "#d5dbe5"}

RING_RADIUS = 100
RING_GAP = 3.0  # surface gap between segments, in viewBox units
RING_MIN_SHARE = 0.025  # a nonzero count always gets a visible arc; exact numbers are in the legend


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def moment(record: EmailRecord) -> datetime | None:
    """When the email arrived, else when it was checked; None for records with neither."""
    return parse_time(record.received_at) or parse_time(record.checked_at)


def when(record: EmailRecord) -> datetime:
    return moment(record) or datetime.min.replace(tzinfo=UTC)


def verdict_of(record: EmailRecord) -> str:
    """scam | suspicious | safe. An email someone marked as safe counts as safe everywhere."""
    if record.marked_safe_at or record.verdict not in ("scam", "suspicious"):
        return "safe"
    return record.verdict


def status_of(has_any: bool, records: list[EmailRecord]) -> str:
    """waiting until the inbox has been checked at all; then the worst result in `records`."""
    if not has_any:
        return "waiting"
    kinds = {verdict_of(r) for r in records}
    return "scam" if "scam" in kinds else "careful" if "suspicious" in kinds else "safe"


def tally(records: list[EmailRecord]) -> dict[str, int]:
    kinds = [verdict_of(r) for r in records]
    return {"checked": len(kinds), "scam": kinds.count("scam"), "suspicious": kinds.count("suspicious"),
            "safe": kinds.count("safe")}


def local_window(period: str, now: datetime, tz: tzinfo) -> tuple[datetime | None, datetime | None]:
    """(start, previous start) of a 7- or 30-day period that ends now, starting at local midnight in tz,
    so a "day" is the person's day. (None, None) for all time."""
    days = PERIODS.get(period, PERIODS[DEFAULT_PERIOD])[1]
    if not days:
        return None, None
    today = now.astimezone(tz).date()
    start = datetime.combine(today - timedelta(days=days - 1), time.min, tzinfo=tz)
    return start, datetime.combine(today - timedelta(days=2 * days - 1), time.min, tzinfo=tz)


def within(records: list[EmailRecord], start: datetime | None, end: datetime | None = None) -> list[EmailRecord]:
    if start is None and end is None:
        return list(records)
    picked = []
    for record in records:
        at = moment(record)
        if at is not None and (start is None or at >= start) and (end is None or at < end):
            picked.append(record)
    return picked


def series(records: list[EmailRecord], period: str, now: datetime, tz: tzinfo, max_weeks: int = 52) -> dict:
    """Daily points for 7/30 days, weekly (Monday) points for all time, bucketed in the person's time zone."""
    days = PERIODS.get(period, PERIODS[DEFAULT_PERIOD])[1]
    today = now.astimezone(tz).date()
    def key(d: date) -> date:  # the bucket a local date falls in
        return d if days else d - timedelta(days=d.weekday())

    if days:
        unit, starts = "day", [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    else:
        this_monday = today - timedelta(days=today.weekday())
        dated = [m for r in records if (m := moment(r))]
        first = min((m.astimezone(tz).date() for m in dated), default=today)
        first_monday = max(first - timedelta(days=first.weekday()), this_monday - timedelta(weeks=max_weeks - 1))
        unit = "week"
        starts = [first_monday + timedelta(weeks=i) for i in range((this_monday - first_monday).days // 7 + 1)]
    points = {d: {"start": d.isoformat(), "safe": 0, "suspicious": 0, "scam": 0} for d in starts}
    for record in records:
        at = moment(record)
        if at is None:
            continue
        bucket = points.get(key(at.astimezone(tz).date()))
        if bucket is not None:
            bucket[verdict_of(record)] += 1
    return {"unit": unit, "points": list(points.values())}


@dataclass
class Person:
    profile: UserProfile
    role: str  # "self" or "guardian"

    @property
    def name(self) -> str:
        return self.profile.display_name or self.profile.email.split("@")[0]


@dataclass
class Visible:
    people: list[Person]
    waiting: list[Invite]  # guardian invites the other person hasn't accepted yet


def visible_to(store: Store, email: str) -> Visible:
    email = email.lower()
    people = []
    for profile in store.list_users():
        if profile.email.lower() == email:
            people.append(Person(profile, "self"))
        elif (profile.guardian_email or "").lower() == email:
            people.append(Person(profile, "guardian"))
    people.sort(key=lambda p: (p.role != "self", p.name.lower()))
    waiting = [i for i in store.list_invites() if i.guardian_email.lower() == email and not i.connected_at]
    return Visible(people, waiting)


@dataclass
class Segment:
    key: str
    label: str
    count: int
    color: str
    dash: float = 0.0
    offset: float = 0.0


@dataclass
class Week:
    start: datetime
    safe: int = 0
    suspicious: int = 0
    scam: int = 0

    @property
    def total(self) -> int:
        return self.safe + self.suspicious + self.scam


@dataclass
class InboxView:
    person: Person
    period: str
    period_label: str
    checked: int
    scams: list[EmailRecord]
    suspicious: list[EmailRecord]
    safe: int
    warnings_sent: int
    last_checked: datetime | None
    status: str  # scam | careful | safe | waiting
    segments: list[Segment] = field(default_factory=list)
    weeks: list[Week] = field(default_factory=list)
    circumference: float = 2 * math.pi * RING_RADIUS

    @property
    def flagged(self) -> int:
        return len(self.scams) + len(self.suspicious)

    @property
    def week_max(self) -> int:
        return max((w.total for w in self.weeks), default=0)


def ring(counts: list[tuple[str, str, int]]) -> list[Segment]:
    """Arc lengths for an SVG donut drawn with stroke-dasharray, clockwise from 12 o'clock."""
    circumference = 2 * math.pi * RING_RADIUS
    total = sum(c for _, _, c in counts)
    if not total:
        return [Segment("empty", "No emails checked yet", 0, COLORS["empty"], circumference, 0.0)]
    shown = [(k, label, c) for k, label, c in counts if c]
    shares = [max(c / total, RING_MIN_SHARE) for _, _, c in shown]
    excess = sum(shares) - 1
    biggest = shares.index(max(shares))
    shares[biggest] -= excess
    gap = RING_GAP if len(shown) > 1 else 0.0
    segments, start = [], 0.0
    for (key, label, count), share in zip(shown, shares, strict=True):
        length = share * circumference
        segments.append(Segment(key, label, count, COLORS[key], max(length - gap, 0.5), -start))
        start += length
    return segments


def weekly(records: list[EmailRecord], now: datetime, weeks: int = 8) -> list[Week]:
    this_monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    buckets = [Week(this_monday - timedelta(weeks=weeks - 1 - i)) for i in range(weeks)]
    for record in records:
        at = when(record)
        for week in reversed(buckets):
            if at >= week.start:
                setattr(week, verdict_of(record), getattr(week, verdict_of(record)) + 1)
                break
    return buckets


def inbox_view(store: Store, person: Person, period: str = DEFAULT_PERIOD, now: datetime | None = None) -> InboxView:
    now = now or datetime.now(UTC)
    if period not in PERIODS:
        period = DEFAULT_PERIOD
    label, days = PERIODS[period]
    everything = store.list_emails(person.profile.user_id)
    since = now - timedelta(days=days) if days else None
    records = [r for r in everything if since is None or when(r) >= since]

    newest_first = sorted(records, key=when, reverse=True)
    scams = [r for r in newest_first if verdict_of(r) == "scam"]
    suspicious = [r for r in newest_first if verdict_of(r) == "suspicious"]
    safe = len(records) - len(scams) - len(suspicious)
    checked_times = [t for r in everything if (t := parse_time(r.checked_at))]
    status = status_of(bool(everything), records)

    return InboxView(
        person=person,
        period=period,
        period_label=label,
        checked=len(records),
        scams=scams,
        suspicious=suspicious,
        safe=safe,
        warnings_sent=sum(1 for r in records if r.warned_at),
        last_checked=max(checked_times) if checked_times else None,
        status=status,
        segments=ring([("scam", "Scams caught", len(scams)),
                       ("suspicious", "Needed a careful look", len(suspicious)),
                       ("safe", "Looked safe", safe)]),
        weeks=weekly(everything, now),
    )


def ago(moment: datetime | None, now: datetime | None = None) -> str:
    if not moment:
        return "not yet"
    seconds = ((now or datetime.now(UTC)) - moment).total_seconds()
    if seconds < 90:
        return "just now"
    if seconds < 3600:
        return f"{round(seconds / 60)} minutes ago"
    if seconds < 36 * 3600:
        hours = round(seconds / 3600)
        return "1 hour ago" if hours == 1 else f"{hours} hours ago"
    days = round(seconds / 86400)
    return "yesterday" if days == 1 else f"{days} days ago"


def day(moment: datetime | None) -> str:
    return f"{moment:%a %b} {moment.day}" if moment else ""


def period_phrase(period: str) -> str:
    return {"7": "in the last 7 days", "30": "in the last 30 days"}.get(period, "so far")


def warned_to(record: EmailRecord, person: Person) -> str:
    """Who got the warning, in the viewer's words: "you and Alex", "Margaret and you"."""
    profile, names = person.profile, []
    for address in record.warned_recipients:
        if address == profile.email.lower():
            names.append("you" if person.role == "self" else person.name)
        elif address == (profile.guardian_email or "").lower():
            names.append("you" if person.role == "guardian" else (profile.guardian_name or "your family member"))
    if "you" in names:  # "you" reads best first when it's the protected person, last for a guardian
        names.remove("you")
        names = ["you", *names] if person.role == "self" else [*names, "you"]
    return " and ".join(names)
