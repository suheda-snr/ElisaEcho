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
    # Live feed only: deliver after the other conversations have finished and the analysis
    # window has passed (the engineer goes off to try the suggested fix, or the conversation
    # happens later).
    deferred: bool = False


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


def _m(
    thread: str, n: int, who: tuple[str, str], sent_at: datetime, content: str, deferred: bool = False
) -> DemoMessage:
    return DemoMessage(f"{thread}-m{n:02d}", who[0], who[1], sent_at, content, deferred)


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
               "Restarted only the DHCP relay service. Leases are being handed out again.",
               deferred=True),
            _m("site42", 4, AINO, _t(14, 9, 35),
               "That worked. The connection is stable now, no drops in the last hour.",
               deferred=True),
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
    DemoThread(
        external_id="demo-thread-site17-connectivity",
        title="Connection drops at Site 17",
        # Same symptoms as Site 42, different cause and fix (a second expert's knowledge).
        scenario="alternative_fix",
        messages=(
            _m("site17", 1, PETRI, _t(28, 9, 10),
               "Site 17 customers behind S17-RTR-02 drop every half hour, looks like the Site 42 "
               "issue. S17-RTR-02 runs firmware 4.0. I restarted the DHCP relay service like last "
               "time but the drops continue."),
            _m("site17", 2, LEENA, _t(28, 9, 18),
               "Then it is probably not the relay. Check the DHCP lease time on S17-RTR-02. After "
               "last week's config template push some routers got a 60 second lease."),
            _m("site17", 3, PETRI, _t(28, 9, 41),
               "Lease time was 60 seconds. Set it back to 24 hours and the drops stopped. "
               "Restarting the relay service alone did not help on this router."),
        ),
    ),
    DemoThread(
        external_id="demo-thread-site58-connectivity",
        title="Customers losing sessions at Site 58",
        # Independent confirmation of the Site 42 fix, with a stated firmware version
        # (consolidation: supporting evidence vs. Site 17's different outcome on firmware 4.0).
        scenario="supporting_evidence",
        messages=(
            _m("site58", 1, SANNA, _t(30, 14, 5),
               "Site 58: customers behind S58-RTR-01 lose their sessions every 20 minutes or so. "
               "The router is on firmware 3.2.", deferred=True),
            _m("site58", 2, JARI, _t(30, 14, 12),
               "Same router family as Site 42. Restart only the DHCP relay service, not the whole "
               "router.", deferred=True),
            _m("site58", 3, SANNA, _t(30, 15, 20),
               "Restarted the DHCP relay service on S58-RTR-01. No drops for over an hour, fixed.",
               deferred=True),
        ),
    ),
)


def demo_message_url(thread_external_id: str, message_external_id: str) -> str:
    return f"{_URL}/{thread_external_id}/{message_external_id}"
