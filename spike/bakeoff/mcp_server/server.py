#!/usr/bin/env python
"""A trivial, locally-authored stdio MCP server — the hermetic target for SPIKE-06.

THROWAWAY (SC#5). Runs only while a bake-off adapter is talking to it.

Why locally authored rather than ``npx -y <some-public-server>``
---------------------------------------------------------------
``T-01-06-EOP`` in this plan's threat register: a stdio MCP server is a subprocess
executing with the user's full privileges, and ``npx -y`` fetches and runs whatever the
registry currently serves under that name. RESEARCH §Security flags exactly this. Nothing
about SPIKE-06 requires a third-party server — the question is whether tool *args* and
*structured results* survive a framework's tracing layer, and forty lines of local Python
answer it while pulling in nothing and reaching nowhere.

So this server, deliberately:

* touches no filesystem path, opens no socket, spawns nothing, reads no environment;
* answers from a frozen in-memory table;
* is identical for both adapters, so the comparison is of the two frameworks and not of
  two MCP endpoints. (Both adapters also share ``mcp==1.28.1``, so it is also one
  protocol version — 01-04's note.)

Why two tools, and why one returns a model
------------------------------------------
``add`` mirrors 01-04's tool-call gate, so a failure here is separable from a model
problem. ``room_status`` returns a **Pydantic model**, which makes FastMCP populate
``CallToolResult.structuredContent`` — and that field is the entire subject of SPIKE-06.
A server whose tools returned only strings would leave nothing for the artifact half to
carry, and the spike would report "no structured results visible" about a server that
never sent any. That is the same vacuity trap 01-04 caught in the no-cloud assertion,
relocated: **the probe must emit the thing the measurement is looking for.**

Run manually:  python spike/bakeoff/mcp_server/server.py     (speaks MCP on stdin/stdout)
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

SERVER_NAME = "paaf-spike-probe"

mcp = FastMCP(SERVER_NAME)


class RoomStatus(BaseModel):
    """A structured reading. The point is that it is NOT a string."""

    room: str = Field(description="Canonical room name.")
    temperature_c: float = Field(description="Temperature in degrees Celsius.")
    humidity_pct: int = Field(description="Relative humidity, percent.")
    devices: list[str] = Field(description="Devices currently present in the room.")


#: Frozen fixture data. No I/O of any kind.
_ROOMS: dict[str, RoomStatus] = {
    "kitchen": RoomStatus(
        room="kitchen",
        temperature_c=21.5,
        humidity_pct=44,
        devices=["kettle", "ceiling-lamp"],
    ),
    "study": RoomStatus(
        room="study",
        temperature_c=19.0,
        humidity_pct=51,
        devices=["desk-lamp", "space-heater"],
    ),
}


@mcp.tool(description="Add two integers and return their sum.")
def add(a: int, b: int) -> int:
    """Deliberately the same shape as 01-04's gate tool."""
    return a + b


@mcp.tool(description="Look up the current status of a room by name.")
def room_status(room: str) -> RoomStatus:
    """Returns a STRUCTURED result, which is what SPIKE-06 needs to be able to lose."""
    key = room.strip().lower()
    if key not in _ROOMS:
        raise ValueError(f"unknown room {room!r}; known rooms: {sorted(_ROOMS)}")
    return _ROOMS[key]


if __name__ == "__main__":
    # stdio only. Never print to stdout anywhere in this file — stdout IS the MCP transport.
    mcp.run(transport="stdio")
