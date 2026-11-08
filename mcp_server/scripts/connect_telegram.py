"""Connect a Telegram chat for "Scam blocked successfully" alerts.

1. In Telegram, message @BotFather, send /newbot, and copy the bot token it gives you.
2. Open your new bot and press Start (or add it to a group and send any message there).
3. Run:  uv run scripts/connect_telegram.py

The script checks the token, finds the chat that just messaged the bot, sends a test alert there,
and saves TELEGRAM_BOT_TOKEN and SCAMSHIELD_TELEGRAM_CHAT_ID to the repo-root .env (git-ignored).
The token is read from TELEGRAM_BOT_TOKEN or a hidden prompt, never from the command line.

For the deployed MCP server, keep the token in AgentCore Identity instead of an env var:
    uv run scripts/connect_telegram.py --identity-provider scamshield-telegram
then set SCAMSHIELD_TELEGRAM_PROVIDER=scamshield-telegram and SCAMSHIELD_TELEGRAM_CHAT_ID on the runtime.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys

from scamshield.config import REPO_ROOT, get_settings
from scamshield.credentials import write_secret
from scamshield.telegram import TelegramAlerts, TelegramClient, TelegramError

ENV_FILE = REPO_ROOT / ".env"


def find_chats(client: TelegramClient) -> list[tuple[str, str]]:
    """Chats that recently messaged the bot or added it, newest first, as (chat_id, description)."""
    chats: dict[str, str] = {}
    for update in reversed(client.call("getUpdates", {"limit": 100, "timeout": 0})):
        for key in ("message", "channel_post", "my_chat_member", "edited_message"):
            chat = (update.get(key) or {}).get("chat")
            if not chat:
                continue
            name = chat.get("title") or " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
            if chat.get("username"):
                name = f"{name} (@{chat['username']})".strip()
            chats.setdefault(str(chat["id"]), f"{chat.get('type', 'chat')}: {name or 'unnamed'}")
    return list(chats.items())


def save_env(values: dict[str, str]) -> None:
    """Set these keys in the repo-root .env, keeping every other line."""
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    for key, value in values.items():
        pattern = re.compile(rf"^\s*#?\s*{re.escape(key)}=")
        for i, line in enumerate(lines):
            if pattern.match(line):
                lines[i] = f"{key}={value}"
                break
        else:
            lines.append(f"{key}={value}")
    write_secret(ENV_FILE, "\n".join(lines) + "\n")


def store_in_identity(provider: str, token: str) -> None:
    """Create or update an AgentCore Identity API-key credential provider holding the bot token."""
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=get_settings().aws_region)
    try:
        control.update_api_key_credential_provider(name=provider, apiKey=token)
        print(f"Updated the bot token in AgentCore Identity provider '{provider}'.")
    except control.exceptions.ResourceNotFoundException:
        control.create_api_key_credential_provider(name=provider, apiKey=token)
        print(f"Stored the bot token in a new AgentCore Identity provider '{provider}'.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chat-id", help="Use this chat instead of finding it (a number, or @channelname).")
    parser.add_argument("--name", default="Margaret", help="Protected person's name shown in the test alert.")
    parser.add_argument("--no-test", action="store_true", help="Don't send the test alert.")
    parser.add_argument("--no-save", action="store_true", help="Don't write anything to .env.")
    parser.add_argument(
        "--identity-provider",
        metavar="NAME",
        help="Store the token in this AgentCore Identity API-key provider instead of .env.",
    )
    args = parser.parse_args()

    settings = get_settings()  # also loads the repo-root .env
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or getpass.getpass("Telegram bot token (from @BotFather): ").strip()
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{30,}", token):
        print("That doesn't look like a bot token (it should look like 123456789:AA...).")
        return 1

    client = TelegramClient(token)
    try:
        bot = client.call("getMe")
        print(f"Bot: @{bot.get('username')}")

        chat_id = args.chat_id or settings.telegram_chat_id
        if not chat_id:
            chats = find_chats(client)
            if not chats:
                print(
                    f"No chats yet. Open https://t.me/{bot.get('username')} and press Start (or add the bot "
                    "to a group and send a message there), then run this again."
                )
                return 1
            for cid, desc in chats:
                print(f"  {cid}  {desc}")
            chat_id = chats[0][0]
            if len(chats) > 1:
                print("Using the most recent chat. Pass --chat-id to pick another.")
        print(f"Chat id: {chat_id}")

        if not args.no_test:
            alerts = TelegramAlerts(lambda: token, chat_id, settings.telegram_link)
            if not alerts.scam_blocked(protected_name=args.name, sender_domain="chase-secure-login.com"):
                print("The test alert failed (see the warning above). Is the bot a member of that chat?")
                return 1
            print("Test alert sent. Check Telegram.")
    except TelegramError as exc:
        print(exc)
        return 1

    if args.identity_provider:
        store_in_identity(args.identity_provider, token)
        if not args.no_save:
            save_env({"SCAMSHIELD_TELEGRAM_CHAT_ID": chat_id})
        print(
            f"On the MCP runtime, set SCAMSHIELD_TELEGRAM_PROVIDER={args.identity_provider} and "
            f"SCAMSHIELD_TELEGRAM_CHAT_ID={chat_id}."
        )
    elif not args.no_save:
        save_env({"TELEGRAM_BOT_TOKEN": token, "SCAMSHIELD_TELEGRAM_CHAT_ID": chat_id})
        print(f"Saved TELEGRAM_BOT_TOKEN and SCAMSHIELD_TELEGRAM_CHAT_ID to {ENV_FILE}.")
    else:
        print(f"Set SCAMSHIELD_TELEGRAM_CHAT_ID={chat_id} and TELEGRAM_BOT_TOKEN for the MCP server.")
    print("Restart the MCP server; every email it labels as a scam now sends an alert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
