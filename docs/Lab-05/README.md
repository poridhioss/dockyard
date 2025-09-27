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

Lab 05 represents a significant expansion of our container orchestration system, transforming it from a basic container launcher into a comprehensive management platform. While Lab 04 focused on observability through logs, Lab 05 completes the container lifecycle by adding full CRUD (Create, Read, Update, Delete) operations and real-time monitoring capabilities.

The evolution from Lab 04 to Lab 05 mirrors the progression from having a remote control for your containers to having a complete dashboard and management interface. You can now not only launch and monitor containers but also inspect their detailed configuration, manage their lifecycle, and observe their resource consumption in real-time.

#### 2.1 Protocol Buffer Evolution (`proto/dockyard.proto`)

The protocol definition has grown substantially to support four new major operations. Building upon the existing foundation of launch, stop, exec, and logs operations, we've added container management and monitoring capabilities.

**Service Definition Expansion:**
```protobuf
service DockyardService {
    rpc LaunchContainer(LaunchRequest) returns (LaunchResponse);
    rpc StopContainer(StopRequest) returns (StopResponse);
    rpc ExecContainer(stream ExecRequest) returns (stream ExecResponse);
    rpc GetLogs(LogsRequest) returns (stream LogsResponse);

    // NEW in Lab 05: Container Management Operations
    rpc ListContainers(ListContainersRequest) returns (ListContainersResponse);
    rpc InspectContainer(InspectContainerRequest) returns (InspectContainerResponse);
    rpc RemoveContainer(RemoveContainerRequest) returns (RemoveContainerResponse);
    rpc GetStats(StatsRequest) returns (stream StatsResponse);
}
```

The `ListContainers` RPC enables us to view all containers across our distributed infrastructure, much like running `docker ps` but remotely. The `InspectContainer` operation provides deep introspection into container configuration and state. `RemoveContainer` allows for cleanup operations with safety controls, while `GetStats` introduces our first resource monitoring capability with streaming statistics.

**Message Type Architecture:**
```protobuf
// Container listing with filtering options
message ListContainersRequest {
    bool all = 1;  // Show all containers (including stopped)
}

message ListContainersResponse {
    bool success = 1;
    repeated ContainerInfo containers = 2;
    string message = 3;
}

// Container metadata structure
message ContainerInfo {
    string id = 1;           // Container ID (short)
    string image = 2;        // Image name
    string command = 3;      // Command being run
    string created = 4;      // Creation time
    string status = 5;       // Current status
    string ports = 6;        // Port mappings
    string names = 7;        // Container name
}
```

The `ContainerInfo` message captures essential metadata that administrators need at a glance, similar to the columnar output of `docker ps`. This structured approach allows for consistent formatting across different client implementations.

**Resource Monitoring Infrastructure:**
```protobuf
// Statistics streaming request
message StatsRequest {
    repeated string container_identifiers = 1; // Empty = all running containers
    bool stream = 2;                          // Continuous streaming vs one-time
}

// Resource usage metrics
message ContainerStats {
    string container_id = 1;
    string name = 2;
    double cpu_percentage = 3;
    uint64 memory_usage = 4;         // Memory usage in bytes
    uint64 memory_limit = 5;         // Memory limit in bytes
    double memory_percentage = 6;
    uint64 network_rx = 7;           // Network received bytes
    uint64 network_tx = 8;           // Network transmitted bytes
    uint64 block_read = 9;           // Block I/O read bytes
    uint64 block_write = 10;         // Block I/O write bytes
    uint32 pids = 11;                // Number of PIDs
}
```

#### 2.2 Agent Implementation Evolution (`agent/main.py`)

The agent has evolved from a simple command executor to a comprehensive container management service. Each new method represents a different aspect of container lifecycle management.

**Container Listing Implementation:**
```python
def ListContainers(self, request, context):
    try:
        containers = self.docker_client.containers.list(all=request.all)
        container_infos = []

        for container in containers:
            # Format creation time consistently
            created_time = container.attrs['Created'][:19].replace('T', ' ')

            # Extract port information
            port_info = self._format_ports(container.ports)

            container_info = dockyard_pb2.ContainerInfo(
                id=container.short_id,
                image=container.image.tags[0] if container.image.tags else container.image.id[:12],
                command=' '.join(container.attrs['Config']['Cmd'] or []),
                created=created_time,
                status=container.status,
                ports=port_info,
                names=container.name
            )
            container_infos.append(container_info)
```

This implementation demonstrates how we bridge Docker's API with our gRPC interface, transforming Docker's container objects into our standardized message format. The method handles both running and stopped containers, providing the flexibility administrators need.

**Container Inspection Deep Dive:**
```python
def InspectContainer(self, request, context):
    try:
        container = self.docker_client.containers.get(request.container_identifier)

        # Get complete inspection data
        inspection_data = container.attrs

        return dockyard_pb2.InspectContainerResponse(
            success=True,
            json_data=json.dumps(inspection_data, indent=2),
            message=f"Container '{request.container_identifier}' inspected successfully"
        )
```

The inspection method provides complete transparency into container configuration, state, and metadata. By serializing the full Docker inspection data to JSON, we preserve all information while maintaining a simple protocol interface.

**Resource Statistics Streaming:**
```python
def GetStats(self, request, context):
    try:
        # Get containers to monitor
        if request.container_identifiers:
            containers = [self.docker_client.containers.get(cid) for cid in request.container_identifiers]
        else:
            containers = self.docker_client.containers.list()

        while True:
            stats_list = []
            for container in containers:
                # Get real-time statistics
                stats = container.stats(stream=False)

                # Calculate CPU percentage with delta method
                cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                           stats['precpu_stats']['cpu_usage']['total_usage']
                system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                              stats['precpu_stats']['system_cpu_usage']

                cpu_percentage = 0.0
                if system_delta > 0:
                    percpu_usage = stats['cpu_stats']['cpu_usage'].get('percpu_usage', [])
                    num_cpus = len(percpu_usage) if percpu_usage else 1
                    cpu_percentage = (cpu_delta / system_delta) * num_cpus * 100.0
```

The statistics implementation showcases real-time data processing, converting Docker's raw statistics into meaningful metrics. The CPU calculation demonstrates the complexity involved in transforming low-level system metrics into user-friendly percentages.

#### 2.3 CLI Enhancement (`cli/main.py`)

The CLI has been transformed from a simple command sender to a sophisticated interface with table formatting, batch operations, and real-time displays.

**Table-Based Container Listing:**
```python
@cli.command()
@click.option('-a', '--all', is_flag=True, help='Show all containers (default shows just running)')
def ps(ctx, all):
    try:
        response = ctx.obj['stub'].ListContainers(dockyard_pb2.ListContainersRequest(all=all))

        if response.success and response.containers:
            # Create formatted table
            headers = ["CONTAINER ID", "IMAGE", "COMMAND", "CREATED", "STATUS", "PORTS", "NAMES"]
            rows = []

            for container in response.containers:
                command = container.command[:30] + "..." if len(container.command) > 30 else container.command
                rows.append([
                    container.id,
                    container.image,
                    command,
                    container.created,
                    container.status,
                    container.ports,
                    container.names
                ])
```

This implementation shows how we've created a Docker-like experience with professional table formatting, making the remote container management feel familiar to Docker users.

**Real-Time Statistics Display:**
```python
@cli.command()
@click.argument('containers', nargs=-1)
@click.option('--no-stream', is_flag=True, help='Disable streaming, pull stats once')
def stats(ctx, containers, no_stream):
    try:
        if not no_stream:
            click.echo("Streaming container statistics... (Press Ctrl+C to stop)")

        for response in ctx.obj['stub'].GetStats(request):
            if response.stats:
                # Clear screen and show updated table
                if not no_stream:
                    click.echo('\033[H\033[J', nl=False)  # Clear screen

                # Format statistics table
                headers = ["CONTAINER", "NAME", "CPU %", "MEM USAGE / LIMIT", "MEM %", "NET I/O", "BLOCK I/O", "PIDS"]
                rows = []

                for stat in response.stats:
                    mem_usage = format_bytes(stat.memory_usage)
                    mem_limit = format_bytes(stat.memory_limit)
                    net_io = f"{format_bytes(stat.network_rx)} / {format_bytes(stat.network_tx)}"
                    block_io = f"{format_bytes(stat.block_read)} / {format_bytes(stat.block_write)}"

                    rows.append([
                        stat.container_id,
                        stat.name,
                        f"{stat.cpu_percentage:.2f}%",
                        f"{mem_usage} / {mem_limit}",
                        f"{stat.memory_percentage:.2f}%",
                        net_io,
                        block_io,
                        str(stat.pids)
                    ])
```

The statistics display demonstrates advanced terminal manipulation and real-time data presentation, creating a live dashboard experience similar to `htop` or `docker stats`.



## Step-by-Step Setup and Testing

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

### Step 2: EC2 Instance Setup

#### 2.1 Launch and Configure EC2 Instance

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@<your-ec2-ip>

# Update and install required packages
sudo apt update
sudo apt install -y docker.io python3-venv python3-pip net-tools

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add ubuntu user to docker group
sudo usermod -aG docker ubuntu

# Log out and back in for group changes to take effect
exit
ssh -i your-key.pem ubuntu@<your-ec2-ip>

# Test Docker access
docker --version
docker ps
```

### Step 3: Deploy Agent to EC2

```bash
# From your local machine, copy files to EC2
scp -r -i your-key.pem agent/ proto/ ubuntu@<your-ec2-ip>:~/

# SSH back into EC2
ssh -i your-key.pem ubuntu@<your-ec2-ip>

# Create and activate virtual environment
python3 -m venv agent_venv
source agent_venv/bin/activate

# Install Python dependencies
pip install -r agent/requirements.txt

# Generate gRPC code
python3 -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. proto/dockyard.proto

# Verify generated files
ls -la *pb2*
```

### Step 4: Start the Agent

```bash
# Start agent in background
nohup python3 agent/main.py > agent.log 2>&1 &

# Check agent started successfully
sleep 2
tail agent.log
```

You should see:
```
INFO:__main__:Connected to Docker daemon
INFO:__main__:Agent started on port 50051
```

### Step 5: Test Container Management

#### 5.1 Set Environment Variable

```bash
# Set your EC2 IP address (replace with your actual EC2 IP)
export EC2_IP="your-ec2-ip-address"
```

#### 5.2 Test Container Listing

```bash
# List running containers
python cli/main.py --host $EC2_IP ps

# List all containers (including stopped)
python cli/main.py --host $EC2_IP ps -a
```

#### 5.3 Test Container Inspection

```bash
# Create a test container first
python cli/main.py --host $EC2_IP launch nginx:alpine --name test-container

# Inspect the container
python cli/main.py --host $EC2_IP inspect test-container
```

#### 5.4 Test Container Removal

```bash
# Remove a stopped container
python cli/main.py --host $EC2_IP rm test-container

# Force remove a running container
python cli/main.py --host $EC2_IP rm --force test-container

# Batch removal
python cli/main.py --host $EC2_IP rm container1 container2 container3
```

### Step 6: Test Resource Monitoring

#### 6.1 Test Statistics Streaming

```bash
# Create a running container for testing
python cli/main.py --host $EC2_IP launch nginx:alpine --name stats-test

# View real-time statistics for all containers
python cli/main.py --host $EC2_IP stats

# View statistics for specific container
python cli/main.py --host $EC2_IP stats stats-test

# Get single snapshot (no streaming)
python cli/main.py --host $EC2_IP stats --no-stream
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
   ssh -i your-key.pem ubuntu@$EC2_IP "ps aux | grep python"
   ```

2. **Check Agent Logs:**
   ```bash
   ssh -i your-key.pem ubuntu@$EC2_IP "tail -f ~/agent.log"
   ```

3. **Test Basic Connectivity:**
   ```bash
   python cli/main.py --host $EC2_IP ps
   ```


## Key Concepts Learned

- **Container Management**: CRUD operations for container lifecycle
- **Resource Monitoring**: Real-time statistics collection and streaming
- **Data Presentation**: Table formatting and human-readable output
- **Batch Operations**: Efficient multi-container operations
- **gRPC Streaming**: Server-side streaming for continuous data
- **Docker API Integration**: Advanced container inspection and statistics

Your Dockyard system now provides comprehensive container management capabilities similar to Docker CLI commands, with the added benefit of remote operation across distributed infrastructure.