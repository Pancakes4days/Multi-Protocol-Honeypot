#!/usr/bin/env python3
"""
Minecraft Honeypot Server
Emulates a Minecraft server to log connection attempts and potential attacks
"""

import socket
import json
import logging
import struct
import time
from datetime import datetime
from pathlib import Path

# Configure logging
LOG_DIR = Path("/logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "honeypot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class MinecraftHoneypot:
    def __init__(self, host='0.0.0.0', port=25565):
        self.host = host
        self.port = port
        self.connections = []
        
    def start(self):
        """Start the honeypot server"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            logger.info(f" Honeypot started on {self.host}:{self.port}")
            logger.info("Waiting for connections...")
            
            while True:
                try:
                    client_socket, address = server_socket.accept()
                    self.handle_connection(client_socket, address)
                except KeyboardInterrupt:
                    logger.info("Shutting down...")
                    break
                except Exception as e:
                    logger.error(f"Error accepting connection: {e}")
                    
        finally:
            server_socket.close()
            
    def handle_connection(self, client_socket, address):
        """Handle incoming connection"""
        ip, port = address
        connection_time = datetime.now().isoformat()
        
        logger.info(f" NEW CONNECTION from {ip}:{port}")
        
        connection_log = {
            "timestamp": connection_time,
            "source_ip": ip,
            "source_port": port,
            "packets": []
        }
        
        try:
            client_socket.settimeout(10)
            
            # Read multiple packets
            packet_count = 0
            while packet_count < 10:  # Limit to prevent infinite loops
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        break
                        
                    packet_count += 1
                    packet_info = self.parse_packet(data)
                    connection_log["packets"].append(packet_info)
                    
                    logger.info(f"   Packet {packet_count} from {ip}: {len(data)} bytes")
                    
                    # Try to parse as handshake
                    if packet_count == 1:
                        handshake_info = self.parse_handshake(data)
                        if handshake_info:
                            connection_log["handshake"] = handshake_info
                            logger.info(f"   Handshake: protocol={handshake_info.get('protocol_version')}, "
                                      f"next_state={handshake_info.get('next_state')}")
                            
                            # Send server list ping response if status request
                            if handshake_info.get('next_state') == 1:
                                self.send_status_response(client_socket)
                    
                    # Small delay to receive more packets
                    time.sleep(0.1)
                    
                except socket.timeout:
                    break
                except Exception as e:
                    logger.warning(f"    Error reading packet: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"   Connection error from {ip}: {e}")
            connection_log["error"] = str(e)
            
        finally:
            # Log the complete connection
            self.log_connection(connection_log)
            client_socket.close()
            logger.info(f"   Connection closed from {ip}")
            
    def parse_packet(self, data):
        """Parse basic packet information"""
        return {
            "timestamp": datetime.now().isoformat(),
            "length": len(data),
            "hex": data[:64].hex(),  # First 64 bytes
            "printable": ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data[:64])
        }
        
    def parse_handshake(self, data):
        """Try to parse Minecraft handshake packet"""
        try:
            pos = 0
            # Read packet length (VarInt)
            packet_length, pos = self.read_varint(data, pos)
            
            # Read packet ID (VarInt) - should be 0x00 for handshake
            packet_id, pos = self.read_varint(data, pos)
            
            if packet_id != 0:
                return None
                
            # Read protocol version (VarInt)
            protocol_version, pos = self.read_varint(data, pos)
            
            # Read server address (String)
            server_address, pos = self.read_string(data, pos)
            
            # Read server port (Unsigned Short)
            if pos + 2 <= len(data):
                server_port = struct.unpack('>H', data[pos:pos+2])[0]
                pos += 2
            else:
                return None
                
            # Read next state (VarInt)
            next_state, pos = self.read_varint(data, pos)
            
            return {
                "protocol_version": protocol_version,
                "server_address": server_address,
                "server_port": server_port,
                "next_state": next_state,
                "next_state_name": "status" if next_state == 1 else "login" if next_state == 2 else "unknown"
            }
            
        except Exception as e:
            logger.debug(f"Could not parse handshake: {e}")
            return None
            
    def read_varint(self, data, pos):
        """Read a VarInt from data"""
        result = 0
        shift = 0
        while pos < len(data):
            byte = data[pos]
            pos += 1
            result |= (byte & 0x7F) << shift
            if not byte & 0x80:
                break
            shift += 7
        return result, pos
        
    def read_string(self, data, pos):
        """Read a string from data"""
        length, pos = self.read_varint(data, pos)
        if pos + length > len(data):
            return "", pos
        string = data[pos:pos+length].decode('utf-8', errors='ignore')
        return string, pos + length
        
    def send_status_response(self, client_socket):
        """Send fake server status response"""
        try:
            status = {
                "version": {
                    "name": "1.20.4",
                    "protocol": 765
                },
                "players": {
                    "max": 20,
                    "online": 3,
                    "sample": [
                        {"name": "Steve", "id": "00000000-0000-0000-0000-000000000000"},
                        {"name": "Alex", "id": "00000000-0000-0000-0000-000000000001"}
                    ]
                },
                "description": {
                    "text": "§aWelcome to the Server!§r\n§7Easy survival server"
                },
                "favicon": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            }
            
            # Wait for status request packet
            request_data = client_socket.recv(1024)
            
            # Send status response
            status_json = json.dumps(status)
            status_bytes = status_json.encode('utf-8')
            
            # Packet: length + packet_id (0x00) + json_length + json
            packet_id = b'\x00'
            json_length = self.write_varint(len(status_bytes))
            packet_data = packet_id + json_length + status_bytes
            packet_length = self.write_varint(len(packet_data))
            
            client_socket.sendall(packet_length + packet_data)
            logger.info(f"   Sent server status response")
            
        except Exception as e:
            logger.debug(f"Could not send status response: {e}")
            
    def write_varint(self, value):
        """Write a VarInt"""
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
        
    def log_connection(self, connection_log):
        """Log connection to JSON file"""
        log_file = LOG_DIR / "connections.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(connection_log) + '\n')

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info(" MINECRAFT HONEYPOT STARTING")
    logger.info("=" * 60)
    
    honeypot = MinecraftHoneypot()
    honeypot.start()
