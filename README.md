# Dockyard - Distributed Container Orchestration System

## Project Overview

Dockyard is a lightweight, distributed container orchestration system that enables remote Docker container management across EC2 instances using gRPC. Built as a progressive learning project, it demonstrates modern microservices architecture, distributed systems design, and DevOps best practices.

## Current Status: Lab 02 Complete ✅

### What's Working Now

**Core Functionality**:
- Remote container launch via gRPC
- Container stop functionality with graceful/force options
- Named container deployment
- YAML-based configuration support
- EC2 agent deployment
- Local CLI tool
- Batch operations support

**Example Commands**:
```bash
# Basic container launch
dockyard launch nginx:latest

# Named containers
dockyard launch redis:alpine --name cache

# YAML configuration support
dockyard launch -f app.yaml

# Stop containers
dockyard stop web-server
dockyard stop --force nginx
dockyard stop --timeout 30 redis cache
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.8+ | Core implementation |
| **RPC Framework** | gRPC | Client-server communication |
| **Container Runtime** | Docker | Container management |
| **CLI Framework** | Click | User interface |
| **Configuration** | YAML | Container definitions |
| **Cloud Platform** | AWS EC2 | Agent deployment |

### Architecture

```
┌─────────────────┐         gRPC          ┌─────────────────┐
│   Local CLI     │◄──────────────────────►│   EC2 Agent     │
│                 │      Port 50051        │                 │
└─────────────────┘                        └─────────────────┘
        │                                           │
        │                                           │
    User Input                                Docker Daemon
```

### Project Structure

```
dockyard/
├── agent/                  # Server component (EC2)
│   ├── main.py            # gRPC server implementation
│   └── requirements.txt   # Agent-specific dependencies
│
├── cli/                   # Client component (Local)
│   ├── main.py            # CLI implementation
│   └── requirements.txt   # CLI-specific dependencies
│
├── proto/                 # gRPC definitions
│   └── dockyard.proto     # Service contracts
│
├── docs/                  # Documentation
│   └── Lab-01/           # Lab 01 documentation
│
├── labs/                  # Lab resources
│   └── lab1-launch/      # Sample configurations
│
└── requirements.txt       # Development dependencies
```

## Lab Roadmap

### ✅ Lab 01: Basic Container Launch
**Status**: Complete
**Branch**: `lab-01`

**Features Implemented**:
- gRPC service setup
- Container launch functionality
- Named containers
- YAML configuration support
- EC2 deployment

**Key Files**:
- `proto/dockyard.proto` - Service definition
- `agent/main.py` - Server implementation
- `cli/main.py` - Client implementation

---

### ✅ Lab 02: Container Stop Functionality
**Status**: Complete
**Branch**: `lab-02`

**Features Implemented**:
- Stop containers by name or ID
- Batch stop operations
- Force stop with timeout
- Graceful shutdown support

**New Commands**:
```bash
dockyard stop web-server
dockyard stop --force nginx
dockyard stop --timeout 30 redis cache
dockyard stop container1 container2 container3
```

**Key Files**:
- `proto/dockyard.proto` - Updated with StopContainer RPC
- `agent/main.py` - StopContainer method implementation
- `cli/main.py` - Stop command with options
- `labs/lab2-stop/` - Examples and test scripts

---

### 📋 Lab 03: Container Exec Functionality
**Status**: Planned
**Branch**: `lab-03`

**Features to Implement**:
- Execute commands in containers
- Interactive shell support
- Non-interactive command execution
- User context switching

**New Commands**:
```bash
dockyard exec web-server bash
dockyard exec web-server "ls -la"
dockyard exec --user root web-server "apt update"
```

**Technical Requirements**:
- Add `ExecContainer` RPC with streaming
- Implement Docker exec API
- Handle stdin/stdout/stderr streams
- TTY allocation for interactive sessions

---

### 📋 Lab 04: Container Logs Functionality
**Status**: Planned
**Branch**: `lab-04`

**Features to Implement**:
- View container logs
- Real-time log streaming
- Log filtering and searching
- Timestamp support

**New Commands**:
```bash
dockyard logs web-server
dockyard logs -f web-server        # Follow
dockyard logs --tail 100 web-server
dockyard logs --since 1h web-server
```

**Technical Requirements**:
- Add `GetLogs` RPC with streaming
- Implement Docker logs API
- Real-time log following
- Log buffering and pagination

---

### 📋 Lab 05: Advanced Features
**Status**: Planned
**Branch**: `lab-05`

**Features to Implement**:
- Container listing and inspection
- Resource monitoring
- Network management
- Volume operations

**New Commands**:
```bash
# Container operations
dockyard ps [-a]
dockyard inspect web-server
dockyard stats web-server
dockyard rm web-server

# Network operations
dockyard network ls
dockyard network create mynet

# Volume operations
dockyard volume ls
dockyard volume create myvol
```

**Technical Requirements**:
- Multiple new RPC endpoints
- Advanced Docker API integration
- Resource metrics collection
- Network/volume lifecycle management

## Learning Objectives by Lab

### Lab 01 ✅
- [x] gRPC service design
- [x] Protocol Buffer definitions
- [x] Docker SDK basics
- [x] CLI development with Click
- [x] EC2 deployment

### Lab 02 ✅
- [x] Container lifecycle management
- [x] State machine handling
- [x] Error recovery patterns
- [x] Batch operations

### Lab 03
- [ ] Bidirectional streaming
- [ ] Interactive I/O handling
- [ ] Process management
- [ ] Security contexts

### Lab 04
- [ ] Real-time data streaming
- [ ] Log aggregation patterns
- [ ] Time-based filtering
- [ ] Buffer management

### Lab 05
- [ ] Complete CRUD operations
- [ ] Resource monitoring
- [ ] Network isolation
- [ ] Persistent storage

## Development Setup

### Prerequisites
- Python 3.8+
- Docker
- AWS EC2 instance
- Basic networking knowledge

### Quick Start

```bash
# Clone repository
git clone <repository-url>
cd dockyard

# Checkout desired lab
git checkout lab-01  # or lab-02, lab-03, etc.

# Install development dependencies
make install-dev

# Generate gRPC code
make proto

# Install component dependencies
make install-agent  # For agent
make install-cli    # For CLI

# Run agent (on EC2)
python3 agent/main.py

# Use CLI (locally)
python3 cli/main.py --host <ec2-ip> launch nginx:latest
```

## Repository Structure

### Branch Strategy
- `main` - Latest stable version with all labs
- `lab-01` - Lab 01 implementation
- `lab-02` - Lab 02 implementation (includes lab-01)
- `lab-03` - Lab 03 implementation (includes lab-01, lab-02)
- `lab-04` - Lab 04 implementation (cumulative)
- `lab-05` - Complete implementation

### Progression Path
Each lab branch contains:
1. Previous lab functionality
2. New features for current lab
3. Updated documentation
4. Test cases and examples

## Key Design Decisions

### Why gRPC?
- Language agnostic communication
- Efficient binary protocol
- Built-in streaming support
- Strong typing with Protocol Buffers

### Why Separate Requirements?
- Component independence
- Minimal dependencies per service
- Easier deployment and scaling
- Better security posture

### Why EC2 for Agent?
- Real-world deployment scenario
- Network isolation testing
- Production-like environment
- Scalability demonstration

## Future Enhancements (Beyond Lab 05)

### Potential Lab 06: Security
- TLS/mTLS for gRPC
- Authentication tokens
- RBAC implementation
- Secrets management

### Potential Lab 07: High Availability
- Multiple agent support
- Load balancing
- Failover mechanisms
- State synchronization

### Potential Lab 08: Orchestration
- Docker Compose support
- Service dependencies
- Health checks
- Auto-restart policies

### Potential Lab 09: Monitoring
- Prometheus metrics
- Grafana dashboards
- Log aggregation
- Alerting

### Potential Lab 10: Kubernetes Migration
- Container to Pod mapping
- Service discovery
- ConfigMaps/Secrets
- Deployment strategies

## Contributing

This project is designed for learning. Each lab builds upon the previous one, introducing new concepts progressively. Feel free to:
- Extend existing labs
- Add new features
- Improve documentation
- Share your implementations

## Resources

### Documentation
- [Lab 01 Guide](docs/Lab-01/README.md)
- [gRPC Python Documentation](https://grpc.io/docs/languages/python/)
- [Docker SDK for Python](https://docker-py.readthedocs.io/)
- [Click Documentation](https://click.palletsprojects.com/)

### Prerequisites Knowledge
- Python programming
- Basic Docker commands
- Linux command line
- Network fundamentals

## License

This is an educational project designed for learning distributed systems and container orchestration.

---

**Current Focus**: Lab 02 is complete with container stop functionality. Ready to proceed with Lab 03 (Container Exec) implementation when needed.