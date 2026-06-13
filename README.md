# 🍯 Minecraft Honeypot

A complete Minecraft server honeypot for learning about network security and attack patterns.

## What's Included

- **Minecraft Honeypot Server**: Python-based fake Minecraft server
- **Docker Setup**: Containerized for safety and easy deployment
- **Log Analysis Tool**: Analyze attack patterns and statistics
- **Attack Simulator**: Test your own honeypot safely

## Quick Start

### 1. Upload Files to Your VPS

```bash
# On your personal computer, in the directory with the files:
scp minecraft_honeypot.py Dockerfile docker-compose.yml honeypot@YOUR_VPS_IP:~/
scp analyze_logs.py attack_simulator.py honeypot@YOUR_VPS_IP:~/
```

### 2. SSH into Your VPS

```bash
ssh honeypot@YOUR_VPS_IP
```

### 3. Build and Start the Honeypot

```bash
# Build the Docker image
docker-compose build

# Start the honeypot
docker-compose up -d

# Check it's running
docker ps
```

You should see:
```
CONTAINER ID   IMAGE                    STATUS         PORTS
abc123def456   minecraft-honeypot       Up 2 seconds   0.0.0.0:25565->25565/tcp
```

### 4. Watch Real-Time Logs

```bash
# Follow live logs
docker logs -f minecraft-honeypot

# Or just check recent logs
docker logs minecraft-honeypot --tail 50
```

## Analyzing Attacks

### View Statistics

```bash
# Make the analyzer executable
chmod +x analyze_logs.py

# Run analysis
python3 analyze_logs.py
```

**Output includes:**
- Total connections
- Top source IPs
- Protocol versions seen
- Connection types (status vs login)
- Timeline of attacks

### View Recent Connections

```bash
# Show last 10 connections in detail
python3 analyze_logs.py recent 10

# Show last 20
python3 analyze_logs.py recent 20
```

## Testing Your Honeypot

### Simulate Attacks from Your Computer

```bash
# Make simulator executable
chmod +x attack_simulator.py

# Test from your personal computer (NOT the VPS):
python3 attack_simulator.py YOUR_VPS_IP
```

This runs 5 different attack simulations:
1. **Server List Ping** - Normal Minecraft client behavior
2. **Login Attempt** - Trying to join the server
3. **Old Protocol** - Using outdated Minecraft version
4. **Malformed Packet** - Sending garbage data
5. **Rapid Connections** - Multiple quick connections

### Using Actual Minecraft Client

You can also test with the real Minecraft game:

1. Open Minecraft
2. Go to Multiplayer
3. Add Server: `YOUR_VPS_IP:25565`
4. The server will appear in your list!
5. Try to connect

All connection attempts are logged!

## Log Files

Logs are stored in the `logs/` directory:

- **`logs/honeypot.log`** - Human-readable logs
- **`logs/connections.jsonl`** - Structured JSON data (one connection per line)

### View Raw Logs

```bash
# View main log file
cat logs/honeypot.log

# View JSON connection data
cat logs/connections.jsonl | jq .

# Count total connections
wc -l logs/connections.jsonl
```

## What You'll Learn

After running this for a few days, you'll discover:

### 1. Attack Frequency
- How quickly bots find new servers
- Geographic distribution of attackers
- Peak attack times

### 2. Common Patterns
- Scanner bots checking server status
- Login attempt patterns
- Exploit attempts (e.g., Log4Shell)

### 3. Attacker Behavior
- Protocol versions used
- Connection sequences
- Automated vs manual attempts

##  Management Commands

### Stop the Honeypot
```bash
docker-compose down
```

### Restart the Honeypot
```bash
docker-compose restart
```

### Rebuild After Changes
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

### Clear Logs
```bash
# Stop honeypot first
docker-compose down

# Clear logs
rm -rf logs/*

# Restart
docker-compose up -d
```

### View Resource Usage
```bash
docker stats minecraft-honeypot
```

##  Cost Management

### Check How Long It's Been Running
```bash
# See container uptime
docker ps
```

### Stop When Not Needed
```bash
# Stop but keep data
docker-compose down

# Restart later
docker-compose up -d
```

### Complete Cleanup
```bash
# Stop and remove everything
docker-compose down
docker system prune -a

# Your logs are still in logs/ directory
# Back them up before destroying the VPS!
```

## Downloading Logs to Your Computer

```bash
# From your personal computer:
scp -r honeypot@YOUR_VPS_IP:~/logs ./honeypot-logs

# Then analyze locally:
python3 analyze_logs.py honeypot-logs/connections.jsonl
```

## Security Notes

###  What's Safe
- Running this honeypot in Docker
- Exposing port 25565
- Analyzing the attacks
- Learning from the data

###  Be Careful
- Don't run other services on this VPS
- Monitor for DoS attacks (high bandwidth usage)
- Check DigitalOcean billing regularly
- Don't store sensitive data on this server

###  Don't Do This
- Don't attack others from this server
- Don't use the data for illegal purposes
- Don't ignore bandwidth costs
- Don't expose your personal computer

##  Interesting Things to Look For

### 1. Scanner Bots
```bash
# Look for IPs that only do status checks
grep "next_state_name.*status" logs/connections.jsonl
```

### 2. Login Attempts
```bash
# Find login attempts
grep "next_state_name.*login" logs/connections.jsonl
```

### 3. Unique Exploit Attempts
```bash
# Check for unusual packets
grep "error" logs/connections.jsonl
```

## Advanced Analysis

### Geographic Location of Attackers

Use online IP lookup services:
```bash
# Extract unique IPs
cat logs/connections.jsonl | jq -r '.source_ip' | sort -u

# Then look them up at: https://ipinfo.io/YOUR_IP
```

### Attack Timeline Visualization

```bash
# Extract timestamps
cat logs/connections.jsonl | jq -r '.timestamp' | cut -d'T' -f1 | sort | uniq -c
```

## Learning Resources

### Understanding What You're Seeing

- **Port scanners**: Automated tools checking for open ports
- **Minecraft scanners**: Bots specifically looking for Minecraft servers
- **Exploit attempts**: Trying known vulnerabilities (like Log4Shell)
- **Brute force**: Trying to connect repeatedly

### Real-World Application

Use this knowledge to:
- Understand how to secure real servers
- Implement rate limiting
- Configure firewalls effectively
- Detect suspicious activity
- Use fail2ban or similar tools

## Troubleshooting

### Honeypot Won't Start
```bash
# Check if port is already in use
sudo netstat -tulpn | grep 25565

# Check Docker logs
docker logs minecraft-honeypot
```

### No Attacks Showing Up
- Wait 24-48 hours (scanners need time to find you)
- Verify firewall: `sudo ufw status`
- Test manually: `python3 attack_simulator.py YOUR_VPS_IP`

### Container Keeps Restarting
```bash
# Check error logs
docker logs minecraft-honeypot --tail 100

# Rebuild container
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Sample Output

After running for 24 hours, you might see:

```
 MINECRAFT HONEYPOT - LOG ANALYSIS
======================================================================

 Total Connections: 127

 Top Source IPs:
   185.220.101.45       -  23 connections
   192.42.116.186       -  15 connections
   167.99.84.203        -  12 connections

🔢 Unique IPs: 89

 Connection Types:
   Status     -  98 connections
   Login      -  29 connections
```

##  Next Steps

Once comfortable with this basic honeypot:

1. **Add more logging** - Capture full packet data
2. **Create alerts** - Get notified of suspicious activity
3. **Deploy multiple honeypots** - Compare different locations
4. **Integrate with ELK stack** - Advanced log analysis
5. **Research specific exploits** - Learn about CVEs

##  License & Disclaimer

This is for **educational purposes only**. 

- Use responsibly
- Don't attack others
- Respect privacy laws
- Follow DigitalOcean's terms of service

## Contributing

Found ways to improve this honeypot? Great! Consider:
- Adding more packet analysis
- Improving logging format
- Creating visualization tools
- Documenting attack patterns
