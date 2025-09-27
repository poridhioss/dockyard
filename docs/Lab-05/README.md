# Lab 05: Container Management and Resource Monitoring

## Introduction

Welcome to Dockyard Lab 05! In this lab, you'll extend your container orchestration system by adding comprehensive container management and resource monitoring capabilities. You'll learn how to list containers, inspect container details, remove containers in batch operations, and implement real-time resource statistics streaming.

**What You'll Learn:**
- Container lifecycle management (CRUD operations)
- Real-time resource monitoring with streaming
- Table-based data presentation
- Batch operations for container management
- Human-readable data formatting
- Force operations for running containers

**What You'll Build:**
- `ListContainers`, `InspectContainer`, `RemoveContainer`, and `GetStats` RPC methods in the agent
- `ps`, `inspect`, `rm`, and `stats` commands in the CLI
- Support for container listing, detailed inspection, batch removal, and streaming statistics
- Real-time statistics display with proper formatting
- Comprehensive container management infrastructure

## Prerequisites

- Completed Lab 04 or familiar with gRPC streaming and container operations
- AWS EC2 instance with SSH access
- Python 3.8+ installed locally
- Basic understanding of Docker container management and system monitoring

## Getting Started

### 1. Clone Repository and Checkout Lab 05

```bash
# Clone the repository
git clone <your-repo-url>
cd dockyard

# Checkout lab-05 branch
git checkout lab-05

# Verify you're on the right branch and see what's included
git branch
ls -la
```

### 2. Understanding the Lab 05 Changes

Before we deploy and test, let's understand what's new in Lab 05 compared to Lab 04:

#### 2.1 Protocol Buffer Changes (`proto/dockyard.proto`)

**New RPC Methods Added:**
```protobuf
service DockyardService {
    // Existing methods...
    rpc ListContainers(ListContainersRequest) returns (ListContainersResponse);
    rpc InspectContainer(InspectContainerRequest) returns (InspectContainerResponse);
    rpc RemoveContainer(RemoveContainerRequest) returns (RemoveContainerResponse);
    rpc GetStats(StatsRequest) returns (stream StatsResponse);
}
```

**New Message Types:**
- `ListContainersRequest` - Options for listing containers (all flag)
- `ListContainersResponse` - Container list with detailed info
- `InspectContainerRequest` - Container identifier for inspection
- `InspectContainerResponse` - Complete container inspection data
- `RemoveContainerRequest` - Container removal with force option
- `RemoveContainerResponse` - Removal operation result
- `StatsRequest` - Statistics request with streaming option
- `StatsResponse` - Resource statistics data
- `ContainerInfo` - Container metadata structure
- `ContainerStats` - Resource usage metrics

#### 2.2 Agent Changes (`agent/main.py`)

**New Methods Implemented:**
- `ListContainers()` - List running and stopped containers with metadata
- `InspectContainer()` - Get detailed container inspection data
- `RemoveContainer()` - Remove containers with force support
- `GetStats()` - Stream real-time resource statistics

**Key Features:**
- Container filtering and formatting
- JSON serialization for inspection data
- Resource calculation for CPU, memory, network, and I/O statistics
- Streaming statistics with proper error handling

#### 2.3 CLI Changes (`cli/main.py`)

**New Commands Added:**
- `ps` - List containers with table formatting
- `inspect` - Show detailed container information
- `rm` - Remove containers with batch and force support
- `stats` - Display real-time resource statistics

**Key Features:**
- Table-based output formatting
- Human-readable data sizes
- Batch operations support
- Real-time streaming display

## Lab 05 Architecture

### Container Management Flow
```
CLI Request → gRPC → Agent → Docker API → Response → Formatted Output
```

### Resource Monitoring Flow
```
CLI Request → gRPC Stream → Agent → Docker Stats → Continuous Updates → Real-time Display
```

## Step-by-Step Implementation

### Step 1: Environment Setup

#### 1.1 Install Dependencies

**On your local machine:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install CLI dependencies
pip install -r cli/requirements.txt

# Generate gRPC code
cd proto
python -m grpc_tools.protoc --python_out=../cli --grpc_python_out=../cli -I. dockyard.proto
cd ..
```

**On your EC2 instance:**
```bash
# Create virtual environment for agent
python3 -m venv agent_venv
source agent_venv/bin/activate

# Install agent dependencies
pip install -r agent/requirements.txt

# Create proto directory and copy proto file
mkdir -p proto
# Copy dockyard.proto to EC2 (via scp)

# Generate gRPC code
cd proto
python -m grpc_tools.protoc --python_out=.. --grpc_python_out=.. -I. dockyard.proto
cd ..
```

### Step 2: Deploy the Agent

#### 2.1 Upload Files to EC2

```bash
# Upload proto file
scp -i your-key.pem proto/dockyard.proto ubuntu@<EC2-IP>:~/proto/

# Upload agent implementation
scp -i your-key.pem agent/main.py ubuntu@<EC2-IP>:~/agent/
```

#### 2.2 Generate gRPC Code on EC2

```bash
ssh -i your-key.pem ubuntu@<EC2-IP>
cd ~/proto
source ~/agent_venv/bin/activate
python -m grpc_tools.protoc --python_out=.. --grpc_python_out=.. -I. dockyard.proto
```

#### 2.3 Start the Agent

```bash
cd ~/agent
source ~/agent_venv/bin/activate
python main.py
```

You should see:
```
INFO:__main__:Connected to Docker daemon
INFO:__main__:Agent started on port 50051
```

### Step 3: Test Container Management

#### 3.1 Test Container Listing

```bash
# List running containers
python cli/main.py --host <EC2-IP> ps

# List all containers (including stopped)
python cli/main.py --host <EC2-IP> ps -a
```

#### 3.2 Test Container Inspection

```bash
# Create a test container first
python cli/main.py --host <EC2-IP> launch nginx:alpine --name test-container

# Inspect the container
python cli/main.py --host <EC2-IP> inspect test-container
```

#### 3.3 Test Container Removal

```bash
# Remove a stopped container
python cli/main.py --host <EC2-IP> rm test-container

# Force remove a running container
python cli/main.py --host <EC2-IP> rm --force test-container

# Batch removal
python cli/main.py --host <EC2-IP> rm container1 container2 container3
```

### Step 4: Test Resource Monitoring

#### 4.1 Test Statistics Streaming

```bash
# Create a running container for testing
python cli/main.py --host <EC2-IP> launch nginx:alpine --name stats-test

# View real-time statistics for all containers
python cli/main.py --host <EC2-IP> stats

# View statistics for specific container
python cli/main.py --host <EC2-IP> stats stats-test

# Get single snapshot (no streaming)
python cli/main.py --host <EC2-IP> stats --no-stream
```

## Expected Output Examples

### Container Listing Output
```
CONTAINER ID IMAGE                COMMAND                        CREATED              STATUS          PORTS                NAMES
--------------------------------------------------------------------------------------------------------------------------------
ae339bbbc75b nginx:alpine         nginx -g daemon off;           2025-09-27 13:22:58  running                              stats-test
```

### Container Inspection Output
```json
{
  "Id": "ae339bbbc75b...",
  "Created": "2025-09-27T13:22:58.123Z",
  "State": {
    "Status": "running",
    "Running": true,
    ...
  },
  "Config": {
    "Image": "nginx:alpine",
    ...
  }
}
```

### Resource Statistics Output
```
CONTAINER    NAME            CPU %    MEM USAGE / LIMIT         MEM %    NET I/O         BLOCK I/O       PIDS
---------------------------------------------------------------------------------------------------------------
ae339bbbc75b stats-test      0.00%    10.2MB / 957.3MB          1.07%    1.1KB / 0B      0B / 0B         2
```

## Command Reference

### ps Command
```bash
# Basic usage
dockyard ps                    # List running containers
dockyard ps -a                 # List all containers

# Options
-a, --all                      # Show all containers (default shows just running)
```

### inspect Command
```bash
# Basic usage
dockyard inspect <container>   # Inspect container by name or ID

# Examples
dockyard inspect web-server    # Inspect by name
dockyard inspect ae339bbbc75b  # Inspect by ID
```

### rm Command
```bash
# Basic usage
dockyard rm <container>        # Remove container by name or ID
dockyard rm <container1> <container2>  # Batch removal

# Options
--force                        # Force removal of running container

# Examples
dockyard rm web-server         # Remove stopped container
dockyard rm --force web-server # Force remove running container
dockyard rm web1 web2 web3     # Remove multiple containers
```

### stats Command
```bash
# Basic usage
dockyard stats                 # Show stats for all running containers
dockyard stats <container>     # Show stats for specific container

# Options
--no-stream                    # Show single snapshot instead of streaming

# Examples
dockyard stats                 # Real-time stats for all containers
dockyard stats web-server      # Real-time stats for specific container
dockyard stats --no-stream     # Single snapshot
```

## Troubleshooting

### Common Issues

1. **"Method not found" Error**
   - Ensure agent has been restarted with updated code
   - Verify gRPC code was regenerated on both client and server

2. **Container Not Found**
   - Check container name/ID spelling
   - Use `dockyard ps -a` to see all containers

3. **Permission Denied on Container Removal**
   - Container might be running, use `--force` flag
   - Check if container is being used by other processes

4. **Statistics Not Displaying**
   - Ensure containers are running
   - Check agent logs for CPU calculation errors

### Verification Steps

1. **Verify Agent is Running:**
   ```bash
   ssh -i your-key.pem ubuntu@<EC2-IP> "ps aux | grep python"
   ```

2. **Check Agent Logs:**
   ```bash
   ssh -i your-key.pem ubuntu@<EC2-IP> "tail -f ~/agent.log"
   ```

3. **Test Basic Connectivity:**
   ```bash
   python cli/main.py --host <EC2-IP> ps
   ```

## What's Next?

Congratulations! You've successfully implemented container management and resource monitoring in your Dockyard system. You now have:

- Complete container lifecycle management (list, inspect, remove)
- Real-time resource monitoring with streaming statistics
- Professional table-based output formatting
- Batch operations and force operations support

In Lab 06, you'll extend the system further with network and volume management capabilities, adding even more advanced container orchestration features.

## Key Concepts Learned

- **Container Management**: CRUD operations for container lifecycle
- **Resource Monitoring**: Real-time statistics collection and streaming
- **Data Presentation**: Table formatting and human-readable output
- **Batch Operations**: Efficient multi-container operations
- **gRPC Streaming**: Server-side streaming for continuous data
- **Docker API Integration**: Advanced container inspection and statistics

Your Dockyard system now provides comprehensive container management capabilities similar to Docker CLI commands, with the added benefit of remote operation across distributed infrastructure.