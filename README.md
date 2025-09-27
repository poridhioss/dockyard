# Dockyard - Distributed Container Orchestration System

## Project Overview

Dockyard is a lightweight, distributed container orchestration system that enables remote Docker container management across EC2 instances using gRPC. Built as a progressive learning project, it demonstrates modern microservices architecture, distributed systems design, and DevOps best practices.

## Current Status: Lab 05 Complete ✅

### What's Working Now

**Core Functionality**:
- Remote container launch via gRPC
- Container stop functionality with graceful/force options
- Container exec functionality with interactive support
- Container logs functionality with streaming support
- Container management (list, inspect, remove)
- Resource monitoring with real-time statistics
- Named container deployment
- YAML-based configuration support
- EC2 agent deployment
- Local CLI tool
- Batch operations support
- Bidirectional streaming for real-time communication
- Server-side streaming for log data and statistics

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

# Execute commands in containers
dockyard exec web-server ls -la
dockyard exec --interactive web-server bash
dockyard exec --user root web-server whoami
dockyard exec --env "DEBUG=true" web-server python script.py

# View container logs
dockyard logs web-server
dockyard logs -f web-server               # Follow mode
dockyard logs --tail 100 web-server       # Last 100 lines
dockyard logs --since 1h web-server       # Last hour
dockyard logs --timestamps web-server     # With timestamps

# Container management
dockyard ps                               # List running containers
dockyard ps -a                            # List all containers
dockyard inspect web-server               # Detailed container info
dockyard rm web-server                    # Remove container
dockyard rm --force web-server            # Force remove running container
dockyard rm container1 container2         # Batch removal

# Resource monitoring
dockyard stats                            # Real-time stats for all containers
dockyard stats web-server                 # Stats for specific container
dockyard stats --no-stream               # Single snapshot
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
│   ├── Lab-01/           # Lab 01 documentation
│   ├── Lab-02/           # Lab 02 documentation
│   ├── Lab-03/           # Lab 03 documentation
│   └── Lab-04/           # Lab 04 documentation
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

### ✅ Lab 03: Container Exec Functionality
**Status**: Complete
**Branch**: `lab-03`

**Features Implemented**:
- Execute commands in containers
- Interactive shell support with TTY allocation
- Non-interactive command execution
- User context switching
- Environment variable injection
- Working directory control
- Cross-platform terminal handling
- Bidirectional streaming communication

**New Commands**:
```bash
dockyard exec web-server bash                    # Interactive shell
dockyard exec web-server ls -la                 # Command execution
dockyard exec --user root web-server whoami     # User switching
dockyard exec --interactive web-server bash     # Explicit interactive mode
dockyard exec --env "DEBUG=true" web-server env # Environment variables
dockyard exec --workdir /tmp web-server pwd     # Working directory
```

**Key Files**:
- `proto/dockyard.proto` - Updated with ExecContainer RPC (bidirectional streaming)
- `agent/main.py` - ExecContainer method with threading and socket handling
- `cli/main.py` - Exec command with cross-platform terminal support
- `docs/Lab-03/` - Complete documentation and examples

---

### ✅ Lab 04: Container Logs Functionality
**Status**: Complete
**Branch**: `lab-04`

**Features Implemented**:
- View container logs with streaming support
- Real-time log streaming and following
- Log tail operations (last N lines)
- Time-based log filtering
- Timestamp display support
- Stream separation (stdout/stderr)
- Server-side streaming for efficient log delivery

**New Commands**:
```bash
dockyard logs web-server                   # Basic logs
dockyard logs -f web-server                # Follow mode
dockyard logs --tail 100 web-server        # Last 100 lines
dockyard logs --since 1h web-server        # Last hour
dockyard logs --timestamps web-server      # With timestamps
dockyard logs --no-stderr web-server       # Stdout only
```

**Key Files**:
- `proto/dockyard.proto` - Updated with GetLogs RPC (server-side streaming)
- `agent/main.py` - GetLogs method with Docker logs API integration
- `cli/main.py` - Logs command with follow, tail, since, timestamps options
- `docs/Lab-04/` - Complete documentation and examples

---

### ✅ Lab 05: Container Management and Resource Monitoring
**Status**: Complete
**Branch**: `lab-05`

**Features Implemented**:
- Container listing with table formatting
- Container inspection with detailed JSON output
- Container removal with batch operations
- Real-time resource monitoring with streaming statistics
- Human-readable data formatting
- Force operations for running containers

**New Commands**:
```bash
# Container management
dockyard ps                               # List running containers
dockyard ps -a                            # List all containers (including stopped)
dockyard inspect web-server               # Detailed container inspection (JSON)
dockyard rm web-server                    # Remove container
dockyard rm --force web-server            # Force remove running container
dockyard rm container1 container2         # Batch removal

# Resource monitoring
dockyard stats                            # Real-time stats for all containers
dockyard stats web-server                 # Stats for specific container
dockyard stats --no-stream               # Single snapshot
```

**Key Files**:
- `proto/dockyard.proto` - Updated with ListContainers, InspectContainer, RemoveContainer, GetStats RPCs
- `agent/main.py` - Container management and statistics methods with Docker API integration
- `cli/main.py` - ps, inspect, rm, stats commands with table formatting and streaming support

---

### 📋 Lab 06: Advanced Features
**Status**: Planned
**Branch**: `lab-06`

**Features to Implement**:
- Network management
- Volume operations
- Health checks
- Auto-restart policies

**New Commands**:
```bash
# Network operations
dockyard network ls
dockyard network create mynet
dockyard network rm mynet

# Volume operations
dockyard volume ls
dockyard volume create myvol
dockyard volume rm myvol
```

**Technical Requirements**:
- Network lifecycle management
- Volume operations
- Health monitoring
- Policy enforcement

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

### Lab 03 ✅
- [x] Bidirectional streaming
- [x] Interactive I/O handling
- [x] Process management
- [x] Security contexts

### Lab 04 ✅
- [x] Real-time data streaming
- [x] Log aggregation patterns
- [x] Time-based filtering
- [x] Buffer management

### Lab 05 ✅
- [x] Complete CRUD operations
- [x] Resource monitoring
- [x] Table-based data presentation
- [x] Real-time streaming statistics

### Lab 06
- [ ] Network isolation
- [ ] Persistent storage
- [ ] Health monitoring
- [ ] Policy enforcement

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
- [Lab 02 Guide](docs/Lab-02/README.md)
- [Lab 03 Guide](docs/Lab-03/README.md)
- [Lab 04 Guide](docs/Lab-04/README.md)
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

**Current Focus**: Lab 05 is complete with container management (ps, inspect, rm) and resource monitoring (stats) functionality including real-time streaming statistics, table formatting, and batch operations. Ready to proceed with Lab 06 (Network & Volume Management) implementation when needed.