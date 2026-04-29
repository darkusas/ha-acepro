"""ACEPRO aceBUS UDP client – asyncio datagram endpoint + state machine.

Ported from acepro-net.js (Node-RED node) to Python / asyncio.
"""
from __future__ import annotations

import asyncio
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Callable

from .const import (
    CMD_GET_VAL,
    CMD_ON_CHANGE,
    CMD_SET_VAL,
    INIT_RETRY_DELAY,
    INIT_RETRY_TILL_TO,
    MAIN_TIMER_PERIOD,
    PACKET_SIZE,
    PACKET_STRUCT,
    RX_RETRY_TILL_TO,
    RX_WARN_DELAY,
    TX_NOT_RELEVANT,
    TX_RETRY_DELAY,
    TX_RETRY_TILL_TO,
    VAL_REN_TIME,
)

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CRC32 – Ethernet polynomial, unreflected (mirrors acepro-net.js)
# ---------------------------------------------------------------------------
_CRC_POLY = 0x04C11DB7
_CRC_TABLE: list[int] = []


def _build_crc_table() -> list[int]:
    """Build the 256-entry CRC32 lookup table (Ethernet polynomial)."""
    table: list[int] = []
    top_bit = 1 << 31
    for i in range(256):
        remainder = i << 24
        for _ in range(8):
            if remainder & top_bit:
                remainder = ((remainder << 1) & 0xFFFFFFFF) ^ _CRC_POLY
            else:
                remainder = (remainder << 1) & 0xFFFFFFFF
        table.append(remainder)
    return table


def crc32_acepro(data: bytes) -> int:
    """Compute ACEPRO CRC32 (Ethernet polynomial, unreflected)."""
    global _CRC_TABLE  # noqa: PLW0603
    if not _CRC_TABLE:
        _CRC_TABLE = _build_crc_table()
    crc = 0xFFFFFFFF
    for byte in data:
        crc = (_CRC_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)) & 0xFFFFFFFF
    return crc


# ---------------------------------------------------------------------------
# Packet encode / decode
# ---------------------------------------------------------------------------

def encode_packet(
    cmd: int,
    src: int,
    dst: int,
    state: int,
    ioid: int,
    val: float,
) -> bytes:
    """Encode a 28-byte aceBUS UDP packet (big-endian)."""
    return struct.pack(PACKET_STRUCT, cmd, src, dst, state, ioid, val)


def decode_packet(data: bytes) -> dict | None:
    """Decode a 28-byte aceBUS UDP packet; return None on error."""
    if len(data) < PACKET_SIZE:
        return None
    try:
        cmd, src, dst, state, ioid, val = struct.unpack(
            PACKET_STRUCT, data[:PACKET_SIZE]
        )
        return {
            "CMD": cmd,
            "SRC": src,
            "DST": dst,
            "State": state,
            "IOID": ioid,
            "Val": val,
        }
    except struct.error as exc:
        _LOGGER.debug("ACEPRO: packet decode error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Object state constants (mirrors AcOS_* in acepro-net.js)
# ---------------------------------------------------------------------------
class _State:  # pylint: disable=too-few-public-methods
    """State machine constants for each tracked IOID (mirrors AcOS_* in acepro-net.js).

    INIT      – waiting for the first reply from the module.
    READY     – value received; monitoring for timeouts.
    WARN_TO   – no packet received within RX_WARN_DELAY; retrying GetVal.
    ERR_TO    – repeated timeouts; module considered unreachable.
    SET_TX    – a SetVal has been sent; waiting for the module's echo.
    ERR_TX_TO – SetVal not confirmed within TX_RETRY_TILL_TO retries.
    DISABLED  – module reported ioid_state == -1 (IOID not available).
    """

    INIT = 0
    READY = 100
    WARN_TO = 200
    ERR_TO = 300
    SET_TX = 400
    ERR_TX_TO = 500
    DISABLED = 600


# ---------------------------------------------------------------------------
# Per-IOID tracking object
# ---------------------------------------------------------------------------

@dataclass
class _AceObj:
    """Tracks one (host, IOID) subscription."""

    topic: str
    ioid: int
    dst_name: str
    dst_crc: int

    # Value / state
    ioid_state: int = -996699   # last received IOIDState from module; -996699 = "never received"
    actual_val: float = 0.0     # value delivered to callbacks
    last_val: float | None = None  # last value that was notified
    last_val_ren_time: float = 0.0

    # RX tracking
    rx_val: float = 0.0
    rx_time: float = 0.0
    cnt_rx: int = 0

    # TX tracking
    tx_val: float = 0.0
    tx_cmd_time: float = 0.0
    cnt_tx: int = 0
    cnt_val_ch: int = 0

    # Callbacks registered for this IOID
    callbacks: list[Callable[[float | None, int], None]] = field(
        default_factory=list
    )

    # State machine
    st: int = _State.INIT
    last_st: int = -1
    tx_cache: dict = field(default_factory=dict)
    cnt_to: int = 0
    cnt_warn_to: int = 0
    cnt_retry: int = 0
    next_time: float = 0.0
    last_notify_txt: str = ""


# ---------------------------------------------------------------------------
# asyncio DatagramProtocol
# ---------------------------------------------------------------------------

class _AceproProtocol(asyncio.DatagramProtocol):
    """asyncio UDP datagram protocol for ACEPRO."""

    def __init__(self, client: "AceproClient") -> None:
        self._client = client
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(  # type: ignore[override]
        self, transport: asyncio.BaseTransport
    ) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple) -> None:  # type: ignore[override]
        self._client._on_datagram_received(data, addr)  # pylint: disable=protected-access

    def error_received(self, exc: Exception) -> None:
        _LOGGER.error("ACEPRO UDP error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        _LOGGER.warning("ACEPRO UDP connection lost: %s", exc)


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------

class AceproClient:
    """Manages ACEPRO aceBUS UDP communication.

    One instance per config entry.  Each entity calls :meth:`register_ioid`
    to subscribe for value updates and :meth:`send_value` to write values.
    """

    def __init__(
        self,
        broadcast_address: str,
        port: int,
    ) -> None:
        self._broadcast_address = broadcast_address
        self._port = port
        # Unique source identifier for outgoing packets
        self._src_crc = crc32_acepro(
            f"ha_acepro_{broadcast_address}_{port}".encode()
        )
        self._registry: dict[str, _AceObj] = {}
        self._transport: asyncio.DatagramTransport | None = None
        self._timer_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Create the UDP socket and start the periodic timer."""
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Bind to all interfaces so we receive broadcast replies on any NIC
        sock.bind(("0.0.0.0", self._port))

        protocol = _AceproProtocol(self)
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: protocol, sock=sock
        )
        _LOGGER.info(
            "ACEPRO UDP bound to 0.0.0.0:%s, broadcasting to %s",
            self._port, self._broadcast_address,
        )
        self._timer_task = asyncio.create_task(self._timer_loop())

    async def stop(self) -> None:
        """Stop the UDP listener and cancel the timer."""
        if self._timer_task:
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass
            self._timer_task = None
        if self._transport:
            self._transport.close()
            self._transport = None
        self._registry.clear()
        _LOGGER.info("ACEPRO UDP stopped")

    # ------------------------------------------------------------------
    # Entity subscription API
    # ------------------------------------------------------------------

    def register_ioid(
        self,
        host: str,
        ioid: int,
        callback: Callable[[float | None, int], None],
    ) -> None:
        """Subscribe to value updates for (host, ioid).

        *callback* is called as ``callback(value, ioid_state)`` where
        *value* is the float value (or ``None`` if unavailable) and
        *ioid_state* is the raw status code from the module (0 = OK).
        """
        dst_crc = crc32_acepro(host.encode("ascii"))
        key = f"{dst_crc:08X}_{ioid}"

        if key not in self._registry:
            obj = _AceObj(
                topic=f"{host}_{ioid}",
                ioid=ioid,
                dst_name=host,
                dst_crc=dst_crc,
            )
            self._registry[key] = obj
            # Send initial GetVal to bootstrap the state machine
            self._netw_send(
                obj,
                {
                    "CMD": CMD_GET_VAL,
                    "Src": self._src_crc,
                    "Dst": dst_crc,
                    "State": 0,
                    "IOID": ioid,
                    "val": 0.0,
                },
            )
            obj.next_time = time.monotonic() + INIT_RETRY_DELAY
        else:
            obj = self._registry[key]
            # Deliver the last known value immediately to the new subscriber
            if obj.st >= _State.READY:
                val = obj.actual_val if obj.ioid_state == 0 else None
                try:
                    callback(val, obj.ioid_state)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("ACEPRO: initial callback error")

        obj.callbacks.append(callback)
        _LOGGER.debug("ACEPRO: registered %s/%s", host, ioid)

    def unregister_ioid(
        self,
        host: str,
        ioid: int,
        callback: Callable,
    ) -> None:
        """Unsubscribe from value updates for (host, ioid)."""
        dst_crc = crc32_acepro(host.encode("ascii"))
        key = f"{dst_crc:08X}_{ioid}"
        if key in self._registry:
            obj = self._registry[key]
            try:
                obj.callbacks.remove(callback)
            except ValueError:
                pass
            if not obj.callbacks:
                del self._registry[key]
                _LOGGER.debug("ACEPRO: removed %s/%s (no more subscribers)", host, ioid)

    def send_value(self, host: str, ioid: int, value: float) -> None:
        """Send a SetVal command for (host, ioid)."""
        dst_crc = crc32_acepro(host.encode("ascii"))
        key = f"{dst_crc:08X}_{ioid}"
        obj = self._registry.get(key)
        if obj is None:
            _LOGGER.warning("ACEPRO: no registered object for %s/%s", host, ioid)
            return
        if obj.ioid_state == -1:
            _LOGGER.warning("ACEPRO: IOID %s/%s is disabled, cannot write", host, ioid)
            return
        # If already at the target value, no need to send
        if obj.rx_val == value:
            obj.tx_val = value
            obj.actual_val = value
            return

        obj.st = _State.SET_TX
        obj.tx_val = value
        obj.tx_cmd_time = time.monotonic()
        obj.cnt_retry = 0
        self._netw_send(
            obj,
            {
                "CMD": CMD_SET_VAL,
                "Src": self._src_crc,
                "Dst": dst_crc,
                "State": 0,
                "IOID": ioid,
                "val": value,
            },
        )
        obj.next_time = time.monotonic() + TX_RETRY_DELAY
        _LOGGER.debug("ACEPRO: SetVal %s/%s = %s", host, ioid, value)

    # ------------------------------------------------------------------
    # Internal – packet I/O
    # ------------------------------------------------------------------

    def _netw_send(self, obj: _AceObj, tx_pack: dict | None) -> None:
        """Encode and broadcast a UDP packet."""
        if tx_pack is None:
            tx_pack = obj.tx_cache
        else:
            obj.tx_cache = tx_pack

        if not tx_pack:
            return
        if self._transport is None or self._transport.is_closing():
            _LOGGER.debug("ACEPRO: transport not ready, dropping packet")
            return

        data = encode_packet(
            tx_pack["CMD"],
            tx_pack["Src"],
            tx_pack["Dst"],
            tx_pack["State"],
            tx_pack["IOID"],
            tx_pack["val"],
        )
        self._transport.sendto(data, (self._broadcast_address, self._port))

    def _on_datagram_received(self, data: bytes, addr: tuple) -> None:
        """Dispatch an incoming datagram to the correct AceObj."""
        pkt = decode_packet(data)
        if pkt is None:
            return
        # Key built from packet's SRC field (= CRC32 of the sending module's host)
        key = f"{pkt['SRC']:08X}_{pkt['IOID']}"
        obj = self._registry.get(key)
        if obj is not None:
            self._data_processing(pkt, obj)

    # ------------------------------------------------------------------
    # Internal – state machine (mirrors DataProcessing in acepro-net.js)
    # ------------------------------------------------------------------

    def _data_processing(self, rx_pkt: dict | None, obj: _AceObj) -> None:  # noqa: C901 – complexity mirrors original
        """Process an incoming packet (or a timer-driven timeout event)."""
        now = time.monotonic()

        # --- Apply incoming packet ----------------------------------------
        if rx_pkt is not None:
            if rx_pkt["CMD"] != CMD_ON_CHANGE:
                return  # we only react to OnChange notifications
            obj.ioid_state = rx_pkt["State"]
            if rx_pkt["State"] == 0:
                obj.rx_val = rx_pkt["Val"]
            obj.cnt_rx += 1
            obj.rx_time = now
            if obj.st < _State.SET_TX:
                obj.actual_val = obj.rx_val

        if obj.ioid_state == -1 and rx_pkt is not None:
            obj.st = _State.DISABLED

        # --- State transitions --------------------------------------------
        if obj.st == _State.INIT:
            if rx_pkt is None:
                self._netw_send(obj, None)
                obj.cnt_retry += 1
                if obj.cnt_retry > INIT_RETRY_TILL_TO:
                    obj.st = _State.ERR_TO
                    obj.cnt_to = 1
                obj.next_time = now + INIT_RETRY_DELAY
            else:
                # Packet received → advance to READY, then immediately
                # fall through to READY logic (mirrors JS fall-through)
                obj.st = _State.READY
                obj.cnt_retry = 0
                # fall through intentionally:
                obj.next_time = now + RX_WARN_DELAY
                obj.st = _State.WARN_TO
                obj.cnt_warn_to += 1
                obj.cnt_retry = 1
                self._request_get_val(obj)

        elif obj.st == _State.READY:
            obj.next_time = now + RX_WARN_DELAY
            obj.st = _State.WARN_TO
            obj.cnt_warn_to += 1
            obj.cnt_retry = 1
            self._request_get_val(obj)

        elif obj.st == _State.WARN_TO:
            obj.next_time = now + RX_WARN_DELAY
            if rx_pkt is not None:
                obj.cnt_retry = 0
                obj.st = _State.READY
            else:
                self._netw_send(obj, None)
                obj.cnt_retry += 1
                if obj.cnt_retry > RX_RETRY_TILL_TO:
                    obj.st = _State.ERR_TO
                    obj.cnt_to += 1

        elif obj.st == _State.ERR_TO:
            obj.next_time = now + RX_WARN_DELAY
            if rx_pkt is not None:
                obj.cnt_retry = 0
                obj.st = _State.READY
            else:
                self._netw_send(obj, None)
                obj.cnt_retry += 1

        elif obj.st == _State.SET_TX:
            obj.next_time = now + TX_RETRY_DELAY
            if rx_pkt is not None:
                obj.cnt_retry = 0
                if obj.rx_val == obj.tx_val:
                    obj.actual_val = obj.tx_val
                    obj.cnt_tx += 1
                    obj.st = _State.READY
                elif (now - obj.tx_cmd_time) > TX_NOT_RELEVANT:
                    obj.actual_val = obj.rx_val
                    obj.st = _State.READY
            else:
                self._netw_send(obj, None)
                obj.cnt_retry += 1
                if obj.cnt_retry > TX_RETRY_TILL_TO:
                    obj.st = _State.ERR_TX_TO
                    obj.cnt_to += 1

        elif obj.st == _State.ERR_TX_TO:
            obj.next_time = now + RX_WARN_DELAY
            if rx_pkt is not None:
                obj.cnt_retry = 0
                obj.st = _State.READY
            else:
                obj.cnt_retry += 1
                obj.st = _State.ERR_TO
                self._request_get_val(obj)

        elif obj.st == _State.DISABLED:
            obj.next_time = now + RX_WARN_DELAY
            if rx_pkt is not None and obj.ioid_state != -1:
                obj.cnt_retry = 0
                obj.st = _State.READY
            else:
                obj.cnt_retry += 1
                self._request_get_val(obj)

        # --- Deliver updated value to entities ----------------------------
        self._notify_callbacks(obj)

    def _request_get_val(self, obj: _AceObj) -> None:
        """Send a GetVal request for the given object."""
        self._netw_send(
            obj,
            {
                "CMD": CMD_GET_VAL,
                "Src": self._src_crc,
                "Dst": obj.dst_crc,
                "State": 0,
                "IOID": obj.ioid,
                "val": 0.0,
            },
        )

    def _notify_callbacks(self, obj: _AceObj) -> None:
        """Fire all registered callbacks if the value or availability changed."""
        if obj.st < _State.READY:
            return
        now = time.monotonic()
        val: float | None = obj.actual_val if obj.ioid_state == 0 else None
        force_refresh = (now - obj.last_val_ren_time) > VAL_REN_TIME

        if val == obj.last_val and not force_refresh:
            return

        obj.last_val = val
        obj.last_val_ren_time = now
        obj.cnt_val_ch += 1

        for cb in list(obj.callbacks):
            try:
                cb(val, obj.ioid_state)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("ACEPRO: error in callback for %s", obj.topic)

    # ------------------------------------------------------------------
    # Periodic timer
    # ------------------------------------------------------------------

    async def _timer_loop(self) -> None:
        """Drive the state machines at MAIN_TIMER_PERIOD intervals."""
        while True:
            await asyncio.sleep(MAIN_TIMER_PERIOD)
            now = time.monotonic()
            for obj in list(self._registry.values()):
                if obj.next_time > 0 and obj.next_time < now:
                    self._data_processing(None, obj)
