"""In-memory stand-in for imaplib.IMAP4_SSL (no network). Asserts read-only access."""

import imaplib
from datetime import date

from app.seed.demo_emails import demo_email_files

PASSWORD = "app-pass-1234"


class FakeMailbox:
    def __init__(self, folders: dict[str, list[tuple[int, date, bytes]]], uid_validity: int = 7) -> None:
        self.folders = folders
        self.uid_validity = uid_validity
        self.logins: list[str] = []
        self.fetched: list[int] = []

    def factory(self, host, port, timeout=None, ssl_context=None):
        return FakeIMAP(self, host)


class FakeIMAP:
    def __init__(self, box: FakeMailbox, host: str) -> None:
        if host == "unreachable.invalid":
            raise OSError("no route")
        self.box = box
        self.folder: list[tuple[int, date, bytes]] | None = None

    def login(self, user, password):
        if password != PASSWORD:
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")
        self.box.logins.append(user)
        return "OK", [b"logged in"]

    def select(self, mailbox, readonly=False):
        assert readonly is True, "mailbox must be opened read-only"
        name = mailbox.strip('"')
        if name not in self.box.folders:
            return "NO", [b"unknown folder"]
        self.folder = self.box.folders[name]
        return "OK", [str(len(self.folder)).encode()]

    def response(self, code):
        assert code == "UIDVALIDITY"
        return "OK", [str(self.box.uid_validity).encode()]

    def list(self):
        return "OK", [f'(\\HasNoChildren) "/" "{name}"'.encode() for name in self.box.folders]

    def uid(self, command, *args):
        if command == "SEARCH":
            if args[1].startswith("UID "):
                low = int(args[1].split()[1].split(":")[0])
                uids = [u for u, _, _ in self.folder if u >= low] or [self.folder[-1][0]]  # IMAP quirk
            else:
                assert args[1] == "SINCE"
                day, mon, year = args[2].split("-")
                months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                since = date(int(year), months.index(mon) + 1, int(day))
                uids = [u for u, d, _ in self.folder if d >= since]
            return "OK", [" ".join(str(u) for u in uids).encode()]
        assert command == "FETCH" and args[1] == "(BODY.PEEK[])", "must not mark emails as read"
        uid = int(args[0])
        raw = next(r for u, _, r in self.folder if u == uid)
        self.box.fetched.append(uid)
        return "OK", [(f"1 (UID {uid} BODY[] {{{len(raw)}}}".encode(), raw), b")"]

    def logout(self):
        return "BYE", []

    def shutdown(self):
        pass


def demo_folder(today: date) -> list[tuple[int, date, bytes]]:
    """The three demo .eml files as UIDs 101-103, all dated today (inside any window)."""
    return [(101 + i, today, path.read_bytes()) for i, path in enumerate(demo_email_files())]
