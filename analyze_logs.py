#!/usr/bin/env python3
"""
Honeypot Log Analyzer
Analyzes connection logs from the Minecraft honeypot
"""

import json
import sys
from collections import Counter
from pathlib import Path
from datetime import datetime

def analyze_logs(log_file):
    """Analyze honeypot logs"""
    
    if not Path(log_file).exists():
        print(f"  Log file not found: {log_file}")
        return
    
    connections = []
    
    # Read all connections
    with open(log_file, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    connections.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    if not connections:
        print("No connections logged yet")
        return
    
    # Statistics
    print("=" * 70)
    print("MINECRAFT HONEYPOT - LOG ANALYSIS")
    print("=" * 70)
    print()
    
    print(f"Total Connections: {len(connections)}")
    print()
    
    # IP addresses
    ips = [c['source_ip'] for c in connections]
    ip_counts = Counter(ips)
    
    print("Top Source IPs:")
    for ip, count in ip_counts.most_common(10):
        print(f"   {ip:20} - {count:3} connections")
    print()
    
    # Unique IPs
    print(f"Unique IPs: {len(ip_counts)}")
    print()
    
    # Protocol versions
    protocols = []
    for c in connections:
        if 'handshake' in c and 'protocol_version' in c['handshake']:
            protocols.append(c['handshake']['protocol_version'])
    
    if protocols:
        protocol_counts = Counter(protocols)
        print("   Protocol Versions Seen:")
        for proto, count in protocol_counts.most_common():
            print(f"   Protocol {proto:4} - {count:3} times")
        print()
    
    # Next states (login vs status)
    states = []
    for c in connections:
        if 'handshake' in c and 'next_state_name' in c['handshake']:
            states.append(c['handshake']['next_state_name'])
    
    if states:
        state_counts = Counter(states)
        print("Connection Types:")
        for state, count in state_counts.most_common():
            print(f"   {state.capitalize():10} - {count:3} connections")
        print()
    
    # Server addresses tried
    addresses = []
    for c in connections:
        if 'handshake' in c and 'server_address' in c['handshake']:
            addresses.append(c['handshake']['server_address'])
    
    if addresses:
        addr_counts = Counter(addresses)
        print("Server Addresses Requested:")
        for addr, count in addr_counts.most_common(10):
            print(f"   {addr:30} - {count:3} times")
        print()
    
    # Timeline
    timestamps = [datetime.fromisoformat(c['timestamp']) for c in connections]
    if timestamps:
        first_conn = min(timestamps)
        last_conn = max(timestamps)
        duration = last_conn - first_conn
        
        print("Timeline:")
        print(f"   First connection: {first_conn.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Last connection:  {last_conn.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Duration:         {duration}")
        print()
    
    # Recent connections
    print("Last 5 Connections:")
    for c in connections[-5:]:
        timestamp = datetime.fromisoformat(c['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        ip = c['source_ip']
        packet_count = len(c.get('packets', []))
        handshake = "✓" if 'handshake' in c else "✗"
        print(f"   {timestamp} - {ip:20} - {packet_count} packets - Handshake: {handshake}")
    print()
    
    print("=" * 70)

def show_recent_connections(log_file, n=10):
    """Show recent connections in detail"""
    
    if not Path(log_file).exists():
        print(f"Log file not found: {log_file}")
        return
    
    connections = []
    with open(log_file, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    connections.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    print(f"\nLast {n} Connections (Detailed):")
    print("=" * 70)
    
    for c in connections[-n:]:
        timestamp = datetime.fromisoformat(c['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n{timestamp}")
        print(f"From: {c['source_ip']}:{c['source_port']}")
        
        if 'handshake' in c:
            h = c['handshake']
            print(f"Handshake:")
            print(f"   Protocol: {h.get('protocol_version', 'N/A')}")
            print(f"   Server: {h.get('server_address', 'N/A')}:{h.get('server_port', 'N/A')}")
            print(f"   Next State: {h.get('next_state_name', 'N/A')}")
        
        if 'packets' in c:
            print(f"Received {len(c['packets'])} packet(s)")
        
        if 'error' in c:
            print(f"Error: {c['error']}")
        
        print("-" * 70)

if __name__ == "__main__":
    default_log = "logs/connections.jsonl"

    if len(sys.argv) > 1 and sys.argv[1] == "recent":
        # Usage: recent [count] [log_file]
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        log_file = sys.argv[3] if len(sys.argv) > 3 else default_log
        show_recent_connections(log_file, n)
    elif len(sys.argv) > 1:
        analyze_logs(sys.argv[1])
    else:
        analyze_logs(default_log)
