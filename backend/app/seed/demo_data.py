"""Synthetic demo conversations. Every name, ID, device and URL here is fictional.

Stored as raw messages only. Knowledge is deliberately NOT pre-extracted:
Phase 3 must discover it automatically.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.enums import SourceType

DEMO_SOURCE_NAME = "Synthetic NOC chat (demo)"
DEMO_SOURCE_TYPE = SourceType.SIMULATED
DEMO_SOURCE_EXTERNAL_ID = "elisa-echo-synthetic-demo"

# Reserved TLD: these links can never resolve to a real system.
_URL = "https://chat.example.invalid/demo"


@dataclass(frozen=True)
class DemoMessage:
    external_id: str
    author_id: str
    author_name: str
    sent_at: datetime
    content: str


@dataclass(frozen=True)
class DemoThread:
    external_id: str
    title: str
    # What the conversation is meant to exercise in Phase 3 (documentation only).
    scenario: str
    messages: tuple[DemoMessage, ...]


def _t(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC)


AINO = ("demo-user-aino", "Aino Virtanen (synthetic)")
JARI = ("demo-user-jari", "Jari Laine (synthetic)")
LEENA = ("demo-user-leena", "Leena Koski (synthetic)")
PETRI = ("demo-user-petri", "Petri Salo (synthetic)")
SANNA = ("demo-user-sanna", "Sanna Mäkelä (synthetic)")


def _m(thread: str, n: int, who: tuple[str, str], sent_at: datetime, content: str) -> DemoMessage:
    return DemoMessage(f"{thread}-m{n:02d}", who[0], who[1], sent_at, content)


DEMO_THREADS: tuple[DemoThread, ...] = (
    DemoThread(
        external_id="demo-thread-site42-connectivity",
        title="Intermittent connectivity at Site 42",
        scenario="confirmed_resolution",
        messages=(
            _m("site42", 1, AINO, _t(14, 8, 2),
               "Site 42 keeps dropping connections. Customers behind S42-RTR-01 lose sessions "
               "every 20-30 minutes. Restarted the router but the issue came back."),
            _m("site42", 2, JARI, _t(14, 8, 9),
               "We had this before on the same router family. Don't reboot the whole router. "
               "Restart the affected service instead, in our case it was the DHCP relay "
               "service on S42-RTR-01. A full reboot only hides it for a while."),
            _m("site42", 3, AINO, _t(14, 8, 21),
               "Restarted only the DHCP relay service. Leases are being handed out again."),
            _m("site42", 4, AINO, _t(14, 9, 35),
               "That worked. The connection is stable now, no drops in the last hour."),
        ),
    ),
    DemoThread(
        external_id="demo-thread-friday-lunch",
        title="Friday lunch",
        scenario="irrelevant_chatter",
        messages=(
            _m("lunch", 1, LEENA, _t(16, 10, 45), "Anyone up for lunch at 11:30 today?"),
            _m("lunch", 2, PETRI, _t(16, 10, 47), "Yes! The new ramen place?"),
            _m("lunch", 3, SANNA, _t(16, 10, 52), "Count me in. Meet at the lobby."),
            _m("lunch", 4, LEENA, _t(16, 10, 53), "Great, see you there."),
        ),
    ),
    DemoThread(
        external_id="demo-thread-olt17-link-flaps",
        title="OLT-17 uplink flapping",
        scenario="unresolved_problem",
        messages=(
            _m("olt17", 1, PETRI, _t(20, 13, 5),
               "OLT-17 uplink port 1/1 is flapping roughly every 10 minutes since this morning. "
               "About 300 FTTH customers see short outages."),
            _m("olt17", 2, SANNA, _t(20, 13, 14),
               "Optical levels on the uplink look slightly high on the RX side. Could be a "
               "dirty connector or the SFP. Has anyone checked the patch panel?"),
            _m("olt17", 3, PETRI, _t(20, 13, 40),
               "Cleaned the connector, still flapping. Field team can swap the SFP tomorrow "
               "morning at the earliest."),
            _m("olt17", 4, SANNA, _t(20, 14, 2),
               "OK. Let's keep the incident open and monitor until the swap."),
        ),
    ),
    DemoThread(
        external_id="demo-thread-pe03-bgp-flap",
        title="BGP session flapping on PE-03",
        scenario="multiple_suggested_fixes",
        messages=(
            _m("pe03", 1, LEENA, _t(22, 7, 50),
               "BGP session between PE-03 and the upstream peer keeps going down and up. "
               "Hold timer expired messages in the log."),
            _m("pe03", 2, JARI, _t(22, 7, 58),
               "Check the MTU on the interconnect. Last time a mismatch after a config change "
               "dropped large UPDATE packets and the session timed out."),
            _m("pe03", 3, SANNA, _t(22, 8, 3),
               "Could also be BFD. If BFD timers are too aggressive on that link, tune them to "
               "300 ms x 3 before touching anything else."),
            _m("pe03", 4, PETRI, _t(22, 8, 10),
               "I would just clear the BGP session and see if it comes back clean."),
            _m("pe03", 5, LEENA, _t(22, 8, 31),
               "MTU was 1500 on our side and 9000 on the peer. Aligned it to 9000 and the "
               "session has been up for 20 minutes now. Leaving BFD as is for now."),
        ),
    ),
)


def demo_message_url(thread_external_id: str, message_external_id: str) -> str:
    return f"{_URL}/{thread_external_id}/{message_external_id}"
