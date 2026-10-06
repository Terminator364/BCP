from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "windows" / "bcp_server_v2.py").read_text(encoding="utf-8")
FABRIC = (ROOT / "windows" / "execution_fabric" / "transport_cockpit.py").read_text(encoding="utf-8")

for route in ('"/v2/cockpit"', '"/v2/deliveries"'):
    assert route in SERVER, route

post = SERVER.split("    def do_POST(self):", 1)[1]
for forbidden in (
    'if path == "/v2/cockpit"',
    'if path == "/v2/deliveries"',
    'body.get("command")',
    'body.get("argv")',
    'body.get("shell")',
):
    assert forbidden not in post, forbidden

for forbidden in (
    "subprocess",
    "os.system",
    "shell=True",
    "time.sleep",
    "while True",
    "api.telegram.org",
    "drive.googleapis.com",
    "requests.",
    "urllib.request",
):
    assert forbidden not in FABRIC, forbidden

for required in (
    "CriticalStore",
    "ActionReceiptRegistry",
    "select_transport_route",
    "build_cockpit_projection",
    "field_certified",
    "PROVIDER_ACK",
    "DESTINATION_READBACK",
):
    assert required in FABRIC, required

# Cockpit is evidence-derived; hidden model reasoning is not a source.
for forbidden in ("chain_of_thought", "reasoning_trace", "hidden_reasoning"):
    assert forbidden not in FABRIC.casefold(), forbidden

print("BCP_R3_PHASE6_TRANSPORT_BOUNDARY=PASS")
print("network_mutation_surface=false")
print("hidden_reasoning_projection=false")
print("field_certified=false")
