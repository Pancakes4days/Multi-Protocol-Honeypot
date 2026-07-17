#!/usr/bin/env python3
"""
Minecraft Honeypot Server
Emulates a Minecraft server to log connection attempts and potential attacks.

The server never executes attacker-supplied data. It only frames and logs
the Minecraft protocol handshake/status/login phases, replies with a canned
status response, then drops the connection.
"""

import os
import socket
import json
import logging
import struct
import threading
from datetime import datetime
from pathlib import Path

# Configure logging. The log directory defaults to /logs (the container mount)
# but can be overridden for local runs and tests.
LOG_DIR = Path(os.environ.get("HONEYPOT_LOG_DIR", "/logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "honeypot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# --- Safety limits (protect the honeypot host from resource-exhaustion) ------
MAX_CONNECTIONS = 200          # cap concurrent handler threads
LISTEN_BACKLOG = 128
SOCKET_TIMEOUT = 10            # seconds of inactivity before dropping a client
MAX_PACKET_SIZE = 32 * 1024    # reject a packet whose declared length exceeds this
MAX_BYTES_PER_CONN = 64 * 1024 # total bytes we are willing to read from one client
MAX_PACKETS = 10               # cap logged packets per connection
MAX_VARINT_BYTES = 5           # Minecraft VarInts are at most 5 bytes
MAX_STRING_LEN = 32767

# Canned server-list-ping response the honeypot advertises.
STATUS_RESPONSE = {
    "version": {"name": "1.20.4", "protocol": 765},
    "players": {
        "max": 20,
        "online": 3,
        "sample": [
            {"name": "Steve", "id": "00000000-0000-0000-0000-000000000000"},
            {"name": "Alex", "id": "00000000-0000-0000-0000-000000000001"},
        ],
    },
    "description": {"text": "§aWelcome to the Server!§r\n§7Easy survival server"},
    "favicon": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
}


def write_varint(value):
    """Encode an int as a Minecraft VarInt."""
    result = b''
    while True:
        byte = value & 0x7F
        value >>= 7
        if value != 0:
            byte |= 0x80
        result += bytes([byte])
        if value == 0:
            break
    return result


def read_varint_bytes(data, pos):
    """Read a VarInt from an in-memory buffer. Returns (value, new_pos)."""
    result = 0
    for i in range(MAX_VARINT_BYTES):
        if pos >= len(data):
            raise ValueError("truncated VarInt")
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << (7 * i)
        if not byte & 0x80:
            return result, pos
    raise ValueError("VarInt too long")


class _PacketReader:
    """
    Buffered, length-framed reader over a blocking socket.

    Handles the reality of TCP: a handshake and status request often arrive in
    a single segment, or a single logical packet may be split across several
    recv() calls. Framing by the leading VarInt length fixes both. Hard caps on
    per-packet and per-connection bytes prevent a malicious client from forcing
    unbounded memory use.
    """

    def __init__(self, sock):
        self.sock = sock
        self.buf = bytearray()
        self.total_read = 0
        self.raw_preview = bytearray()  # first bytes seen, for logging

    def _fill(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("peer closed connection")
            self.total_read += len(chunk)
            if self.total_read > MAX_BYTES_PER_CONN:
                raise ValueError("connection exceeded byte cap")
            self.buf.extend(chunk)
            if len(self.raw_preview) < 256:
                self.raw_preview.extend(chunk[:256 - len(self.raw_preview)])

    def read(self, n):
        self._fill(n)
        data = bytes(self.buf[:n])
        del self.buf[:n]
        return data

    def read_varint(self):
        result = 0
        for i in range(MAX_VARINT_BYTES):
            self._fill(1)
            byte = self.buf[0]
            del self.buf[:1]
            result |= (byte & 0x7F) << (7 * i)
            if not byte & 0x80:
                return result
        raise ValueError("VarInt too long")

    def read_packet(self):
        """Read one length-prefixed packet body (without the length prefix)."""
        length = self.read_varint()
        if length <= 0 or length > MAX_PACKET_SIZE:
            raise ValueError(f"invalid packet length {length}")
        return self.read(length)


class MinecraftHoneypot:
    def __init__(self, host='0.0.0.0', port=25565):
        self.host = host
        self.port = port
        self._log_lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(MAX_CONNECTIONS)

    def start(self):
        """Start the honeypot server (one thread per connection)."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(LISTEN_BACKLOG)
            logger.info(f" Honeypot started on {self.host}:{self.port}")
            logger.info("Waiting for connections...")

            while True:
                try:
                    client_socket, address = server_socket.accept()
                except KeyboardInterrupt:
                    logger.info("Shutting down...")
                    break
                except OSError as e:
                    logger.error(f"Error accepting connection: {e}")
                    continue

                # Bound concurrency: if all slots are busy, drop rather than
                # spawn an unbounded number of threads.
                if not self._slots.acquire(blocking=False):
                    logger.warning(
                        f" Connection limit ({MAX_CONNECTIONS}) reached, "
                        f"dropping {address[0]}:{address[1]}"
                    )
                    client_socket.close()
                    continue

                thread = threading.Thread(
                    target=self._serve,
                    args=(client_socket, address),
                    daemon=True,
                )
                thread.start()

        finally:
            server_socket.close()

    def _serve(self, client_socket, address):
        try:
            self.handle_connection(client_socket, address)
        finally:
            self._slots.release()

    def handle_connection(self, client_socket, address):
        """Handle a single connection in its own thread."""
        ip, port = address
        connection_time = datetime.now().isoformat()

        logger.info(f" NEW CONNECTION from {ip}:{port}")

        connection_log = {
            "timestamp": connection_time,
            "source_ip": ip,
            "source_port": port,
            "packets": [],
        }

        reader = _PacketReader(client_socket)

        try:
            client_socket.settimeout(SOCKET_TIMEOUT)

            # --- Packet 1: handshake ---------------------------------------
            body = reader.read_packet()
            connection_log["packets"].append(self.packet_info(body))
            logger.info(f"   Handshake packet from {ip}: {len(body)} bytes")

            handshake = self.parse_handshake(body)
            if handshake:
                connection_log["handshake"] = handshake
                logger.info(
                    f"   Handshake: protocol={handshake.get('protocol_version')}, "
                    f"next_state={handshake.get('next_state_name')}"
                )

                if handshake.get("next_state") == 1:
                    self.handle_status(reader, client_socket, connection_log, ip)
                elif handshake.get("next_state") == 2:
                    self.handle_login(reader, connection_log, ip)
                else:
                    self.drain_extra_packets(reader, connection_log)
            else:
                # Not a valid handshake — capture a few more packets for study.
                self.drain_extra_packets(reader, connection_log)

        except socket.timeout:
            logger.info(f"   Timeout from {ip}")
        except (ConnectionError, ValueError) as e:
            logger.warning(f"   Protocol error from {ip}: {e}")
            connection_log["error"] = str(e)
        except Exception as e:
            logger.error(f"   Connection error from {ip}: {e}")
            connection_log["error"] = str(e)
        finally:
            # Preserve whatever raw bytes we saw, even on a parse failure.
            if reader.raw_preview and not connection_log["packets"]:
                connection_log["packets"].append(
                    self.packet_info(bytes(reader.raw_preview))
                )
            self.log_connection(connection_log)
            try:
                client_socket.close()
            except OSError:
                pass
            logger.info(f"   Connection closed from {ip}")

    def handle_status(self, reader, client_socket, connection_log, ip):
        """Status phase: read the status request, reply, echo the ping."""
        # Status request (packet id 0x00, empty). It may already be buffered
        # alongside the handshake — the framed reader handles either case.
        try:
            request = reader.read_packet()
            connection_log["packets"].append(self.packet_info(request))
        except (ConnectionError, ValueError, socket.timeout):
            # Some scanners send only the handshake; reply anyway.
            pass

        self.send_status_response(client_socket)
        logger.info(f"   Sent server status response to {ip}")

        # Optional ping/pong (packet id 0x01 + 8-byte payload). Echoing it back
        # makes the latency show up in a real client.
        try:
            ping = reader.read_packet()
            connection_log["packets"].append(self.packet_info(ping))
            if ping and ping[0] == 0x01:
                client_socket.sendall(write_varint(len(ping)) + ping)
                logger.info(f"   Echoed ping/pong to {ip}")
        except (ConnectionError, ValueError, socket.timeout):
            pass

    def handle_login(self, reader, connection_log, ip):
        """Login phase: capture the attempted username, then drop."""
        try:
            body = reader.read_packet()
            connection_log["packets"].append(self.packet_info(body))
            pos = 0
            packet_id, pos = read_varint_bytes(body, pos)
            if packet_id == 0x00:
                username, _ = self.read_string(body, pos)
                connection_log["login_username"] = username
                logger.info(f"   Login attempt from {ip}: username={username!r}")
        except (ConnectionError, ValueError, socket.timeout):
            pass

    def drain_extra_packets(self, reader, connection_log):
        """Read and log a bounded number of further packets for analysis."""
        while len(connection_log["packets"]) < MAX_PACKETS:
            try:
                body = reader.read_packet()
            except (ConnectionError, ValueError, socket.timeout):
                break
            connection_log["packets"].append(self.packet_info(body))

    def packet_info(self, data):
        """Summarize a packet body for the log."""
        return {
            "timestamp": datetime.now().isoformat(),
            "length": len(data),
            "hex": data[:64].hex(),
            "printable": ''.join(
                chr(b) if 32 <= b <= 126 else '.' for b in data[:64]
            ),
        }

    def parse_handshake(self, body):
        """Parse a Minecraft handshake packet body (length prefix already removed)."""
        try:
            pos = 0
            packet_id, pos = read_varint_bytes(body, pos)
            if packet_id != 0:
                return None

            protocol_version, pos = read_varint_bytes(body, pos)
            server_address, pos = self.read_string(body, pos)

            if pos + 2 > len(body):
                return None
            server_port = struct.unpack('>H', body[pos:pos + 2])[0]
            pos += 2

            next_state, pos = read_varint_bytes(body, pos)

            return {
                "protocol_version": protocol_version,
                "server_address": server_address,
                "server_port": server_port,
                "next_state": next_state,
                "next_state_name": (
                    "status" if next_state == 1
                    else "login" if next_state == 2
                    else "unknown"
                ),
            }
        except (ValueError, struct.error) as e:
            logger.debug(f"Could not parse handshake: {e}")
            return None

    def read_string(self, data, pos):
        """Read a length-prefixed UTF-8 string from a buffer."""
        length, pos = read_varint_bytes(data, pos)
        if length < 0 or length > MAX_STRING_LEN or pos + length > len(data):
            return "", pos
        string = data[pos:pos + length].decode('utf-8', errors='ignore')
        return string, pos + length

    def send_status_response(self, client_socket):
        """Send the canned server-list-ping response."""
        try:
            status_bytes = json.dumps(STATUS_RESPONSE).encode('utf-8')
            packet_data = b'\x00' + write_varint(len(status_bytes)) + status_bytes
            client_socket.sendall(write_varint(len(packet_data)) + packet_data)
        except OSError as e:
            logger.debug(f"Could not send status response: {e}")

    def log_connection(self, connection_log):
        """Append a connection record to the JSONL log (thread-safe)."""
        log_file = LOG_DIR / "connections.jsonl"
        line = json.dumps(connection_log) + '\n'
        with self._log_lock:
            with open(log_file, 'a') as f:
                f.write(line)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info(" MINECRAFT HONEYPOT STARTING")
    logger.info("=" * 60)

    honeypot = MinecraftHoneypot()
    honeypot.start()
