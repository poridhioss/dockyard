# Lab 02: Container Stop Operations

## Introduction

Welcome to Dockyard Lab 02! In this lab, you'll extend the container launch functionality from Lab 01 by adding comprehensive container stop operations. You'll learn how to gracefully stop containers, force-kill them, handle batch operations, and manage various edge cases.

**What You'll Learn:**
- Container lifecycle management (stop vs kill)
- gRPC service extension (adding new RPCs)
- Batch operations and error handling
- Docker API for container termination
- CLI command design with multiple options

**What You'll Build:**
- `StopContainer` RPC method in the agent
- `stop` command in the CLI with various options
- Support for graceful stop, force kill, and batch operations
- Comprehensive error handling for edge cases

## Prerequisites

- Completed Lab 01 or familiar with basic gRPC and Docker concepts
- AWS EC2 instance with SSH access
- Python 3.8+ installed locally
- Basic understanding of containers and networking

## Getting Started

### 1. Clone Repository and Checkout Lab 02

```bash
# Clone the repository
git clone <your-repo-url>
cd dockyard

# Checkout lab-02 branch
git checkout lab-02

# Verify you're on the right branch and see what's included
git branch
ls -la
```

### 2. Understanding the Lab 02 Changes

Before we deploy and test, let's understand what's new in Lab 02 compared to Lab 01:

#### 2.1 Protocol Buffer Changes (`proto/dockyard.proto`)

**What was added:**
```protobuf
service DockyardService {
    rpc LaunchContainer(LaunchRequest) returns (LaunchResponse);
    rpc StopContainer(StopRequest) returns (StopResponse);  // ← NEW
}

// NEW: Stop request message
message StopRequest {
    string container_identifier = 1; // name or ID
    bool force = 2;                  // force stop (kill vs graceful)
    int32 timeout = 3;              // timeout in seconds
}

// NEW: Stop response message
message StopResponse {
    bool success = 1;
    string container_id = 2;
    string message = 3;
}
```

**Why these changes:**
- `container_identifier`: Flexible - accepts both container name and ID
- `force`: Distinguishes between graceful stop (SIGTERM) and force kill (SIGKILL)
- `timeout`: Configurable graceful stop timeout before force killing

#### 2.2 Agent Changes (`agent/main.py`)

**What was added:**
```python
def StopContainer(self, request, context):
    try:
        container_identifier = request.container_identifier
        force = request.force
        timeout = request.timeout if request.timeout > 0 else 10

        # Find container by name or ID
        container = self.docker_client.containers.get(container_identifier)

        # Check if container is already stopped
        container.reload()
        if container.status in ['exited', 'stopped']:
            return dockyard_pb2.StopResponse(
                success=True,
                container_id=container.id[:12],
                message=f"Container '{container_identifier}' is already stopped"
            )

        # Stop the container
        if force:
            logger.info(f"Force stopping container: {container.id[:12]}")
            container.kill()  # SIGKILL - immediate
        else:
            logger.info(f"Gracefully stopping container: {container.id[:12]} (timeout: {timeout}s)")
            container.stop(timeout=timeout)  # SIGTERM then SIGKILL

        return dockyard_pb2.StopResponse(
            success=True,
            container_id=container.id[:12],
            message=f"Container '{container_identifier}' stopped successfully"
        )

    except docker.errors.NotFound:
        return dockyard_pb2.StopResponse(
            success=False,
            message=f"Container '{container_identifier}' not found"
        )
    except Exception as e:
        return dockyard_pb2.StopResponse(
            success=False,
            message=f"Error: {str(e)}"
        )
```

**Key concepts:**
- **Container Lookup**: Uses `containers.get()` which accepts both names and IDs
- **State Checking**: Always `reload()` container state before operations
- **Graceful vs Force**:
  - `container.stop(timeout)` sends SIGTERM, waits, then SIGKILL
  - `container.kill()` sends SIGKILL immediately
- **Error Handling**: Specific handling for missing containers and API errors

#### 2.3 CLI Changes (`cli/main.py`)

**What was added:**
```python
def stop_container(self, container_identifier, force=False, timeout=10):
    request = dockyard_pb2.StopRequest(
        container_identifier=container_identifier,
        force=force,
        timeout=timeout
    )

    try:
        response = self.stub.StopContainer(request)
        return response
    except grpc.RpcError as e:
        click.echo(f"Error: Failed to connect to agent - {e.details()}", err=True)
        return None

@cli.command()
@click.argument('containers', nargs=-1, required=True)
@click.option('--force', '-f', is_flag=True, help='Force stop (kill instead of graceful stop)')
@click.option('--timeout', '-t', default=10, help='Timeout in seconds for graceful stop (default: 10)')
@click.pass_context
def stop(ctx, containers, force, timeout):
    \"\"\"Stop one or more containers\"\"\"
    client = ctx.obj['client']

    # Handle multiple containers
    failed_containers = []
    stopped_containers = []

    for container in containers:
        click.echo(f"Stopping container '{container}'...")

        response = client.stop_container(
            container_identifier=container,
            force=force,
            timeout=timeout
        )

        if response:
            if response.success:
                click.echo(f"Success: {response.message}")
                stopped_containers.append(container)
                if response.container_id:
                    click.echo(f"Container ID: {response.container_id}")
            else:
                click.echo(f"Failed to stop '{container}': {response.message}", err=True)
                failed_containers.append(container)
        else:
            failed_containers.append(container)

    # Summary for batch operations
    if len(containers) > 1:
        click.echo(f"\nSummary: {len(stopped_containers)} stopped, {len(failed_containers)} failed")
        if failed_containers:
            click.echo(f"Failed containers: {', '.join(failed_containers)}", err=True)

    client.close()

    # Exit with error code if any containers failed to stop
    if failed_containers:
        sys.exit(1)
```

**Key features:**
- **Batch Operations**: `nargs=-1` allows multiple container arguments
- **Progress Reporting**: Shows progress for each container individually
- **Summary**: Provides summary for batch operations
- **Error Handling**: Individual container failures don't stop the batch
- **Exit Codes**: Non-zero exit if any containers failed

## Step-by-Step Setup and Testing

### 3. EC2 Instance Setup

#### 3.1 Launch and Configure EC2 Instance

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@<your-ec2-ip>

# Update and install required packages
sudo apt update
sudo apt install -y docker.io python3-venv net-tools

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

#### 3.2 Deploy Agent to EC2

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

#### 3.3 Start the Agent

```bash
# Start agent in background
nohup python3 agent/main.py > agent.log 2>&1 &

# Check agent started successfully
sleep 2
cat agent.log

# Should see:
# INFO:__main__:Connected to Docker daemon
# INFO:__main__:Agent started on port 50051

# Verify agent is listening
netstat -tlnp | grep 50051
# Should show: tcp6  0  0 :::50051  :::*  LISTEN
```

### 4. Local CLI Setup

#### 4.1 Setup Local Environment

```bash
# From your local machine, in the dockyard directory
# Create and activate virtual environment
python3 -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install CLI dependencies
pip install -r cli/requirements.txt

# Generate gRPC code locally
python3 -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. proto/dockyard.proto

# Verify CLI works
python3 cli/main.py --help
```

#### 4.2 Test CLI Connection

```bash
# Test connection to your EC2 agent (replace with your EC2 IP)
export EC2_IP="your-ec2-ip-address"

# Test basic connectivity with launch command
python3 cli/main.py --host $EC2_IP launch nginx:latest --name test-connection

# Verify container was created on EC2
ssh -i your-key.pem ubuntu@$EC2_IP "docker ps"
```

### 5. Testing Lab 02 Stop Functionality

Now let's test all the stop functionality we implemented:

#### 5.1 Basic Stop Operations

```bash
# Launch a few test containers first
python3 cli/main.py --host $EC2_IP launch nginx:latest --name web-server
python3 cli/main.py --host $EC2_IP launch redis:alpine --name cache
python3 cli/main.py --host $EC2_IP launch nginx:alpine --name app-server

# Verify containers are running
ssh -i your-key.pem ubuntu@$EC2_IP "docker ps"

# Test basic graceful stop
python3 cli/main.py --host $EC2_IP stop web-server

# Expected output:
# Stopping container 'web-server'...
# Success: Container 'web-server' stopped successfully
# Container ID: 1234567890ab

# Verify container stopped gracefully (exit code 0)
ssh -i your-key.pem ubuntu@$EC2_IP "docker ps -a | grep web-server"
# Should show: Exited (0)
```

#### 5.2 Force Stop Operations

```bash
# Test force stop (immediate kill)
python3 cli/main.py --host $EC2_IP stop --force cache

# Expected output:
# Stopping container 'cache'...
# Success: Container 'cache' stopped successfully
# Container ID: 9876543210ba

# Verify container was force-killed (exit code 137)
ssh -i your-key.pem ubuntu@$EC2_IP "docker ps -a | grep cache"
# Should show: Exited (137)

# Exit code 137 = 128 + 9 (SIGKILL)
```

#### 5.3 Custom Timeout Operations

```bash
# Launch another container
python3 cli/main.py --host $EC2_IP launch busybox:latest --name timeout-test

# Test custom timeout (5 seconds instead of default 10)
python3 cli/main.py --host $EC2_IP stop --timeout 5 timeout-test

# Expected output:
# Stopping container 'timeout-test'...
# Success: Container 'timeout-test' stopped successfully
# Container ID: abcdef123456
```

#### 5.4 Batch Stop Operations

```bash
# Launch multiple containers for batch testing
python3 cli/main.py --host $EC2_IP launch nginx:alpine --name nginx1
python3 cli/main.py --host $EC2_IP launch nginx:alpine --name nginx2
python3 cli/main.py --host $EC2_IP launch nginx:alpine --name nginx3

# Test batch stop (multiple containers at once)
python3 cli/main.py --host $EC2_IP stop nginx1 nginx2 nginx3

# Expected output:
# Stopping container 'nginx1'...
# Success: Container 'nginx1' stopped successfully
# Container ID: 111111111111
# Stopping container 'nginx2'...
# Success: Container 'nginx2' stopped successfully
# Container ID: 222222222222
# Stopping container 'nginx3'...
# Success: Container 'nginx3' stopped successfully
# Container ID: 333333333333
#
# Summary: 3 stopped, 0 failed
```

#### 5.5 Error Handling Tests

```bash
# Test stopping already stopped container
python3 cli/main.py --host $EC2_IP stop nginx1

# Expected output:
# Stopping container 'nginx1'...
# Success: Container 'nginx1' is already stopped
# Container ID: 111111111111

# Test stopping non-existent container
python3 cli/main.py --host $EC2_IP stop non-existent-container

# Expected output:
# Stopping container 'non-existent-container'...
# Failed to stop 'non-existent-container': Container 'non-existent-container' not found

# Test mixed success/failure batch operation
python3 cli/main.py --host $EC2_IP stop nginx2 non-existent nginx3

# Expected output shows individual results plus summary:
# Summary: 2 stopped, 1 failed
# Failed containers: non-existent
```

#### 5.6 Container State Verification

```bash
# Check all container states on EC2
ssh -i your-key.pem ubuntu@$EC2_IP "docker ps -a"

# You should see various exit codes:
# - Exited (0): Gracefully stopped containers
# - Exited (137): Force-killed containers
# - Up: Any still running containers
```

### 6. Understanding the Results

#### 6.1 Exit Codes Explained

- **Exit 0**: Container stopped gracefully (received SIGTERM and shut down properly)
- **Exit 137**: Container was force-killed (SIGKILL = 128 + 9)
- **Exit 143**: Container was terminated (SIGTERM = 128 + 15)

#### 6.2 Stop vs Kill Operations

**Graceful Stop (`container.stop()`):**
1. Sends SIGTERM to main process
2. Waits for timeout period (default 10s)
3. If still running, sends SIGKILL
4. Usually results in Exit 0

**Force Kill (`container.kill()`):**
1. Immediately sends SIGKILL
2. No graceful shutdown opportunity
3. Always results in Exit 137

### 7. Advanced Testing Scenarios

#### 7.1 Test with Long-Running Containers

```bash
# Launch a container that ignores SIGTERM (for educational purposes)
python3 cli/main.py --host $EC2_IP launch nginx:latest --name stubborn-container

# Try graceful stop with short timeout
python3 cli/main.py --host $EC2_IP stop --timeout 2 stubborn-container

# Try force stop
python3 cli/main.py --host $EC2_IP stop --force stubborn-container
```

#### 7.2 Test Container ID vs Name

```bash
# Launch container and get its ID
python3 cli/main.py --host $EC2_IP launch nginx:alpine --name id-test

# Get the container ID
CONTAINER_ID=$(ssh -i your-key.pem ubuntu@$EC2_IP "docker ps --format '{{.ID}}' --filter name=id-test")

# Stop using container ID instead of name
python3 cli/main.py --host $EC2_IP stop $CONTAINER_ID
```

### 8. Troubleshooting Common Issues

#### 8.1 Agent Connection Issues

```bash
# Check if agent is running on EC2
ssh -i your-key.pem ubuntu@$EC2_IP "ps aux | grep python3 | grep agent"

# Check if port 50051 is listening
ssh -i your-key.pem ubuntu@$EC2_IP "netstat -tlnp | grep 50051"

# Check agent logs for errors
ssh -i your-key.pem ubuntu@$EC2_IP "tail -f agent.log"

# Restart agent if needed
ssh -i your-key.pem ubuntu@$EC2_IP "pkill -f 'python3 agent/main.py' && source agent_venv/bin/activate && nohup python3 agent/main.py > agent.log 2>&1 &"
```

#### 8.2 Protocol Buffer Version Issues

If you see `ImportError: cannot import name 'runtime_version'`:

```bash
# On EC2:
ssh -i your-key.pem ubuntu@$EC2_IP
source agent_venv/bin/activate
pip install 'protobuf<5.0,>=4.21.0'
python3 -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. proto/dockyard.proto

# Locally:
pip install 'protobuf<5.0,>=4.21.0'
python3 -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. proto/dockyard.proto
```

#### 8.3 Docker Permission Issues

```bash
# On EC2, if you get permission denied:
sudo usermod -aG docker ubuntu
newgrp docker
# Or restart your SSH session
```

## Key Learning Points

### 1. gRPC Service Extension
- How to add new RPCs to existing services
- Backward compatibility considerations
- Proto file evolution best practices

### 2. Container Lifecycle Management
- Difference between graceful stop and force kill
- Understanding container exit codes
- Proper state checking before operations

### 3. Error Handling in Distributed Systems
- Individual vs batch operation error handling
- User-friendly error messages
- Graceful degradation (continue batch even if one fails)

### 4. CLI Design Patterns
- Multiple argument handling (`nargs=-1`)
- Flag vs option patterns (`--force` vs `--timeout`)
- Progress reporting for long operations
- Summary reporting for batch operations

### 5. Docker API Usage
- Container lookup by name or ID
- State management and reloading
- Different termination methods

## Next Steps

Congratulations! You've successfully implemented and tested container stop functionality. You now have:

- ✅ Extended gRPC service with new RPC method
- ✅ Comprehensive container stop operations
- ✅ Batch operation support
- ✅ Robust error handling
- ✅ User-friendly CLI with multiple options

**Ready for Lab 03?** The next lab will cover container exec functionality - running commands inside containers interactively.

**Want to explore more?** Try:
- Implementing container restart functionality
- Adding container status/health checks
- Building a simple container monitoring dashboard
- Exploring Docker networking and volume operations

## Cleanup

When you're done testing, clean up your EC2 resources:

```bash
# Stop and remove all test containers
ssh -i your-key.pem ubuntu@$EC2_IP "docker stop \$(docker ps -aq) && docker rm \$(docker ps -aq)"

# Stop the agent
ssh -i your-key.pem ubuntu@$EC2_IP "pkill -f 'python3 agent/main.py'"

# Remember to terminate your EC2 instance if you're not continuing to Lab 03
```