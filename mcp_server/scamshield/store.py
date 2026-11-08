"""Verdict and user/guardian storage. Stores verdicts and evidence, never email bodies.

LocalStore (a JSON file) is for Phase 1 on a laptop. DynamoStore uses one table:
    pk = "USER#<user_id>", sk = "PROFILE"            -> UserProfile
    pk = "USER#<user_id>", sk = "EMAIL#<email_id>"   -> EmailRecord
    pk = "INVITE#<token>",  sk = "INVITE"            -> Invite (guardian sign-up waiting for the user to connect)
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .config import Settings


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class UserProfile:
    user_id: str
    email: str
    guardian_email: str | None = None
    display_name: str | None = None
    guardian_name: str | None = None

    def allowed_recipients(self) -> set[str]:
        return {e.lower() for e in (self.email, self.guardian_email) if e}

    def known_names(self) -> list[str]:
        return [n for n in (self.display_name, self.guardian_name) if n]


@dataclass
class EmailRecord:
    user_id: str
    email_id: str
    verdict: str  # scam | suspicious | fine | no_links
    checked_at: str = field(default_factory=now_iso)
    labeled: bool = False
    reasons: list[str] = field(default_factory=list)
    warned_at: str | None = None
    warned_recipients: list[str] = field(default_factory=list)


@dataclass
class Invite:
    """A guardian's sign-up, waiting for the protected person to connect their Gmail."""

    token: str
    user_id: str
    protected_name: str
    guardian_name: str
    guardian_email: str
    created_at: str = field(default_factory=now_iso)
    connected_at: str | None = None
    connected_email: str | None = None


class Store(Protocol):
    def get_user(self, user_id: str) -> UserProfile | None: ...
    def put_user(self, profile: UserProfile) -> None: ...
    def list_users(self) -> list[UserProfile]: ...
    def checked_ids(self, user_id: str, email_ids: list[str]) -> set[str]: ...
    def get_email(self, user_id: str, email_id: str) -> EmailRecord | None: ...
    def put_email(self, record: EmailRecord) -> None: ...
    def put_invite(self, invite: Invite) -> None: ...
    def get_invite(self, token: str) -> Invite | None: ...
    def list_invites(self) -> list[Invite]: ...


class LocalStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"users": {}, "emails": {}}
        return json.loads(self.path.read_text())

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.path)

    def get_user(self, user_id: str) -> UserProfile | None:
        with self._lock:
            raw = self._load()["users"].get(user_id)
        return UserProfile(**raw) if raw else None

    def put_user(self, profile: UserProfile) -> None:
        with self._lock:
            data = self._load()
            data["users"][profile.user_id] = asdict(profile)
            self._save(data)

    def list_users(self) -> list[UserProfile]:
        with self._lock:
            users = self._load()["users"]
        return [UserProfile(**raw) for _, raw in sorted(users.items())]

    def checked_ids(self, user_id: str, email_ids: list[str]) -> set[str]:
        with self._lock:
            mine = self._load()["emails"].get(user_id, {})
        return {i for i in email_ids if i in mine}

    def get_email(self, user_id: str, email_id: str) -> EmailRecord | None:
        with self._lock:
            raw = self._load()["emails"].get(user_id, {}).get(email_id)
        return EmailRecord(**raw) if raw else None

    def put_email(self, record: EmailRecord) -> None:
        with self._lock:
            data = self._load()
            data["emails"].setdefault(record.user_id, {})[record.email_id] = asdict(record)
            self._save(data)

    def put_invite(self, invite: Invite) -> None:
        with self._lock:
            data = self._load()
            data.setdefault("invites", {})[invite.token] = asdict(invite)
            self._save(data)

    def get_invite(self, token: str) -> Invite | None:
        with self._lock:
            raw = self._load().get("invites", {}).get(token)
        return Invite(**raw) if raw else None

    def list_invites(self) -> list[Invite]:
        with self._lock:
            invites = self._load().get("invites", {})
        return sorted((Invite(**raw) for raw in invites.values()), key=lambda i: i.created_at)


class DynamoStore:
    def __init__(self, table_name: str, region: str, resource=None) -> None:
        import boto3

        self._resource = resource or boto3.resource("dynamodb", region_name=region)
        self._table = self._resource.Table(table_name)
        self._table_name = table_name

    @staticmethod
    def _pk(user_id: str) -> str:
        return f"USER#{user_id}"

    def get_user(self, user_id: str) -> UserProfile | None:
        item = self._table.get_item(Key={"pk": self._pk(user_id), "sk": "PROFILE"}).get("Item")
        if not item:
            return None
        return UserProfile(**{k: item.get(k) for k in UserProfile.__dataclass_fields__})

    def put_user(self, profile: UserProfile) -> None:
        item = {k: v for k, v in asdict(profile).items() if v is not None}
        self._table.put_item(Item={"pk": self._pk(profile.user_id), "sk": "PROFILE", **item})

    def list_users(self) -> list[UserProfile]:
        """Full scan: fine for a handful of users (only used when regenerating policies)."""
        from boto3.dynamodb.conditions import Attr

        users: list[UserProfile] = []
        kwargs: dict = {"FilterExpression": Attr("sk").eq("PROFILE")}
        while True:
            resp = self._table.scan(**kwargs)
            users += [UserProfile(**{k: i.get(k) for k in UserProfile.__dataclass_fields__}) for i in resp["Items"]]
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return sorted(users, key=lambda u: u.user_id)

    def checked_ids(self, user_id: str, email_ids: list[str]) -> set[str]:
        found: set[str] = set()
        for start in range(0, len(email_ids), 100):  # BatchGetItem limit
            keys = [{"pk": self._pk(user_id), "sk": f"EMAIL#{i}"} for i in email_ids[start : start + 100]]
            request = {self._table_name: {"Keys": keys, "ProjectionExpression": "email_id"}}
            while request:
                resp = self._resource.batch_get_item(RequestItems=request)
                found |= {item["email_id"] for item in resp["Responses"].get(self._table_name, [])}
                request = resp.get("UnprocessedKeys") or None
        return found

    def get_email(self, user_id: str, email_id: str) -> EmailRecord | None:
        item = self._table.get_item(Key={"pk": self._pk(user_id), "sk": f"EMAIL#{email_id}"}).get("Item")
        if not item:
            return None
        fields = {k: item[k] for k in EmailRecord.__dataclass_fields__ if k in item}
        fields["reasons"] = list(fields.get("reasons", []))
        fields["warned_recipients"] = list(fields.get("warned_recipients", []))
        return EmailRecord(**fields)

    def put_email(self, record: EmailRecord) -> None:
        item = {k: v for k, v in asdict(record).items() if v is not None}
        self._table.put_item(Item={"pk": self._pk(record.user_id), "sk": f"EMAIL#{record.email_id}", **item})

    def put_invite(self, invite: Invite) -> None:
        item = {k: v for k, v in asdict(invite).items() if v is not None}
        self._table.put_item(Item={"pk": f"INVITE#{invite.token}", "sk": "INVITE", **item})

    def get_invite(self, token: str) -> Invite | None:
        item = self._table.get_item(Key={"pk": f"INVITE#{token}", "sk": "INVITE"}).get("Item")
        return Invite(**{k: item.get(k) for k in Invite.__dataclass_fields__}) if item else None

    def list_invites(self) -> list[Invite]:
        """Full scan: fine for a handful of invites."""
        from boto3.dynamodb.conditions import Attr

        invites: list[Invite] = []
        kwargs: dict = {"FilterExpression": Attr("sk").eq("INVITE")}
        while True:
            resp = self._table.scan(**kwargs)
            invites += [Invite(**{k: i.get(k) for k in Invite.__dataclass_fields__}) for i in resp["Items"]]
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return sorted(invites, key=lambda i: i.created_at)


def make_store(settings: Settings) -> Store:
    if settings.store_backend == "dynamodb":
        return DynamoStore(settings.dynamodb_table, settings.aws_region)
    if settings.store_backend == "local":
        return LocalStore(settings.local_store_path)
    raise ValueError(f"Unknown SCAMSHIELD_STORE: {settings.store_backend!r}")
