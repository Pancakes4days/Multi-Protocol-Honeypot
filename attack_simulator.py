#!/usr/bin/env python3
"""
Minecraft Honeypot Attack Simulator
Simulates various connection attempts to test your honeypot
"""

import socket
import struct
import time
import sys

class MinecraftClient:
    """Simulates Minecraft client connections"""
    
    def __init__(self, host, port=25565):
        self.host = host
        self.port = port
    
    def write_varint(self, value):
        """Encode a VarInt"""
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
    
    def write_string(self, string):
        """Encode a string"""
        encoded = string.encode('utf-8')
        return self.write_varint(len(encoded)) + encoded
    
    def send_handshake(self, sock, protocol_version=765, next_state=1):
        """Send handshake packet"""
        # Build handshake packet
        packet_id = self.write_varint(0x00)
        protocol = self.write_varint(protocol_version)
        server_address = self.write_string(self.host)
        server_port = struct.pack('>H', self.port)
        next_state_bytes = self.write_varint(next_state)
        
        packet_data = packet_id + protocol + server_address + server_port + next_state_bytes
        packet_length = self.write_varint(len(packet_data))
        
        sock.sendall(packet_length + packet_data)
    
    def send_status_request(self, sock):
        """Send status request packet"""
        packet_id = self.write_varint(0x00)
        packet_length = self.write_varint(len(packet_id))
        sock.sendall(packet_length + packet_id)
    
    def test_server_list_ping(self):
        """Test server list ping (what Minecraft client does)"""
        print(f"   Testing Server List Ping to {self.host}:{self.port}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.host, self.port))
            print("   Connected")
            
            # Send handshake for status
            self.send_handshake(sock, protocol_version=765, next_state=1)
            print("   Sent handshake (status)")
            
            # Send status request
            self.send_status_request(sock)
            print("   Sent status request")
            
            # Try to receive response
            time.sleep(0.5)
            try:
                response = sock.recv(4096)
                if response:
                    print(f"   Received response: {len(response)} bytes")
                else:
                    print("     No response received")
            except socket.timeout:
                print("     Response timeout")
            
            sock.close()
            print("    Test completed\n")
            
        except Exception as e:
            print(f"    Error: {e}\n")
    
    def test_login_attempt(self):
        """Test login attempt"""
        print(f"   Testing Login Attempt to {self.host}:{self.port}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.host, self.port))
            print("   Connected")
            
            # Send handshake for login
            self.send_handshake(sock, protocol_version=765, next_state=2)
            print("    Sent handshake (login)")
            
            # Send login start packet
            packet_id = self.write_varint(0x00)
            username = self.write_string("TestPlayer")
            packet_data = packet_id + username
            packet_length = self.write_varint(len(packet_data))
            sock.sendall(packet_length + packet_data)
            print("    Sent login start (username: TestPlayer)")
            
            time.sleep(0.5)
            sock.close()
            print("    Test completed\n")
            
        except Exception as e:
            print(f"   Error: {e}\n")
    
    def test_old_protocol(self):
        """Test with old protocol version"""
        print(f"    Testing Old Protocol Version to {self.host}:{self.port}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.host, self.port))
            print("    Connected")
            
            # Send handshake with old protocol (1.8 = 47)
            self.send_handshake(sock, protocol_version=47, next_state=1)
            print("    Sent handshake (protocol 47 - Minecraft 1.8)")
            
            self.send_status_request(sock)
            print("    Sent status request")
            
            time.sleep(0.5)
            sock.close()
            print("    Test completed\n")
            
        except Exception as e:
            print(f"    Error: {e}\n")
    
    def test_malformed_packet(self):
        """Test with malformed packet"""
        print(f" Testing Malformed Packet to {self.host}:{self.port}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.host, self.port))
            print("    Connected")
            
            # Send random/malformed data
            malformed = b'\x00\xff\xfe\xfd' * 20
            sock.sendall(malformed)
            print("    Sent malformed packet")
            
            time.sleep(0.5)
            sock.close()
            print("    Test completed\n")
            
        except Exception as e:
            print(f"    Error: {e}\n")
    
    def test_rapid_connections(self, count=5):
        """Test rapid connections (potential DoS simulation)"""
        print(f" Testing Rapid Connections ({count}x) to {self.host}:{self.port}")
        
        for i in range(count):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((self.host, self.port))
                
                self.send_handshake(sock, protocol_version=765, next_state=1)
                
                sock.close()
                print(f"    Connection {i+1}/{count}")
                time.sleep(0.1)
                
            except Exception as e:
                print(f"    Connection {i+1}/{count} failed: {e}")
        
        print("    Test completed\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 attack_simulator.py <host> [port]")
        print("\nExamples:")
        print("  python3 attack_simulator.py localhost")
        print("  python3 attack_simulator.py 192.168.1.100 25565")
        sys.exit(1)
    
    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    
    print("=" * 70)
    print(" MINECRAFT HONEYPOT ATTACK SIMULATOR")
    print("=" * 70)
    print(f"Target: {host}:{port}\n")
    
    client = MinecraftClient(host, port)
    
    # Run all tests
    tests = [
        ("Server List Ping", client.test_server_list_ping),
        ("Login Attempt", client.test_login_attempt),
        ("Old Protocol", client.test_old_protocol),
        ("Malformed Packet", client.test_malformed_packet),
        ("Rapid Connections", lambda: client.test_rapid_connections(5)),
    ]
    
    for test_name, test_func in tests:
        test_func()
        time.sleep(1)
    
    print("=" * 70)
    print(" All tests completed!")
    print("\n Check your honeypot logs:")
    print("   docker logs minecraft-honeypot")
    print("   python3 analyze_logs.py")

if __name__ == "__main__":
    main()
