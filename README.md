# Dockyard - Distributed Container Orchestration System

## Project Overview

Dockyard is a lightweight, distributed container orchestration system that enables remote Docker container management across EC2 instances using gRPC. Built as a progressive learning project, it demonstrates modern microservices architecture, distributed systems design, and DevOps best practices.

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
└── requirements.txt       # Development dependencies
```

## Lab Roadmap

###  Lab 01: Basic Container Launch
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



###  Lab 02: Container Stop Functionality
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



###  Lab 03: Container Exec Functionality
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



###  Lab 04: Container Logs Functionality
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



###  Lab 05: Container Management and Resource Monitoring
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



## Learning Objectives by Lab

### Lab 01 
- [x] gRPC service design
- [x] Protocol Buffer definitions
- [x] Docker SDK basics
- [x] CLI development with Click
- [x] EC2 deployment

### Lab 02 
- [x] Container lifecycle management
- [x] State machine handling
- [x] Error recovery patterns
- [x] Batch operations

### Lab 03 
- [x] Bidirectional streaming
- [x] Interactive I/O handling
- [x] Process management
- [x] Security contexts

### Lab 04 
- [x] Real-time data streaming
- [x] Log aggregation patterns
- [x] Time-based filtering
- [x] Buffer management

### Lab 05 
- [x] Complete CRUD operations
- [x] Resource monitoring
- [x] Table-based data presentation
- [x] Real-time streaming statistics



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

