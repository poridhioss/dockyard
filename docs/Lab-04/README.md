# Lab 04: Container Logs Operations

## Introduction

Welcome to Dockyard Lab 04! In this lab, you'll extend your container orchestration system by adding comprehensive container logs functionality. You'll learn how to stream logs from containers, implement real-time log following, handle time-based filtering, and work with gRPC server-side streaming patterns.

**What You'll Learn:**
- Server-side gRPC streaming for log data
- Docker logs API integration
- Real-time log streaming and following
- Time-based log filtering
- Stream multiplexing (stdout/stderr separation)
- Efficient log tail operations

**What You'll Build:**
- `GetLogs` streaming RPC method in the agent
- `logs` command in the CLI with multiple options
- Support for follow mode, tail, timestamps, and time filtering
- Real-time log streaming infrastructure
- Proper stream handling and buffering

## Prerequisites

- Completed Lab 03 or familiar with gRPC streaming and container operations
- AWS EC2 instance with SSH access
- Python 3.8+ installed locally
- Basic understanding of logging, streaming, and Docker

## Getting Started

### 1. Clone Repository and Checkout Lab 04

```bash
# Clone the repository
git clone <your-repo-url>
cd dockyard

# Checkout lab-04 branch
git checkout lab-04

# Verify you're on the right branch and see what's included
git branch
ls -la
```

### 2. Understanding the Lab 04 Changes

Before we deploy and test, let's understand what's new in Lab 04 compared to Lab 03:

#### 2.1 Protocol Buffer Changes (`proto/dockyard.proto`)

**What was added:**
```protobuf
service DockyardService {
    rpc LaunchContainer(LaunchRequest) returns (LaunchResponse);
    rpc StopContainer(StopRequest) returns (StopResponse);
    rpc ExecContainer(stream ExecRequest) returns (stream ExecResponse);
    rpc GetLogs(LogsRequest) returns (stream LogsResponse);  // NEW
}

// NEW: Log request configuration
message LogsRequest {
    string container_identifier = 1; // name or ID
    bool follow = 2;                 // follow log output (like tail -f)
    int32 tail = 3;                  // number of lines from end (0 = all)
    string since = 4;                // relative time (e.g., "1h", "30m", "10s")
    bool timestamps = 5;             // show timestamps
    bool stdout = 6;                 // include stdout (default true)
    bool stderr = 7;                 // include stderr (default true)
}

// NEW: Streaming log response
message LogsResponse {
    oneof response_type {
        LogsStatus status = 1;
        LogEntry log = 2;
    }
}

// NEW: Log operation status
message LogsStatus {
    bool success = 1;
    string message = 2;
    bool finished = 3;               // true when all logs have been sent (for non-follow mode)
}

// NEW: Individual log entry
message LogEntry {
    bytes data = 1;                  // log line data
    string stream_type = 2;          // "stdout" or "stderr"
    string timestamp = 3;            // ISO 8601 timestamp (if timestamps enabled)
}
```

**Why these changes:**
- **Server-side Streaming**: `stream LogsResponse` enables continuous log streaming
- **Flexible Options**: Support for all common Docker log options
- **Time Filtering**: Relative time format for viewing recent logs
- **Stream Separation**: Distinguish between stdout and stderr
- **Status Updates**: Clear indication of streaming status and completion

#### 2.2 Agent Changes (`agent/main.py`)

**What was added:**
```python
def GetLogs(self, request, context):
    """Stream container logs with optional following"""
    import datetime
    import re

    try:
        container_identifier = request.container_identifier
        follow = request.follow
        tail = request.tail if request.tail > 0 else "all"
        since = request.since
        timestamps = request.timestamps

        # Default to True for stdout and stderr unless explicitly set to False
        stdout = True if not hasattr(request, 'stdout') else request.stdout
        stderr = True if not hasattr(request, 'stderr') else request.stderr

        # Since proto3 defaults booleans to False, we need better logic
        if not request.stdout and not request.stderr:
            stdout = True
            stderr = True

        logger.info(f"Getting logs for container: {container_identifier}, follow={follow}, tail={tail}, since={since}")

        # Find the container
        try:
            container = self.docker_client.containers.get(container_identifier)
        except docker.errors.NotFound:
            yield dockyard_pb2.LogsResponse(
                status=dockyard_pb2.LogsStatus(
                    success=False,
                    message=f"Container '{container_identifier}' not found"
                )
            )
            return

        # Parse the 'since' parameter to datetime if provided
        since_datetime = None
        if since:
            # Parse relative time format (e.g., "1h", "30m", "10s")
            match = re.match(r'^(\d+)([smhd])$', since)
            if match:
                value, unit = match.groups()
                value = int(value)

                if unit == 's':
                    delta = datetime.timedelta(seconds=value)
                elif unit == 'm':
                    delta = datetime.timedelta(minutes=value)
                elif unit == 'h':
                    delta = datetime.timedelta(hours=value)
                elif unit == 'd':
                    delta = datetime.timedelta(days=value)

                since_datetime = datetime.datetime.utcnow() - delta
                logger.info(f"Logs since: {since_datetime}")

        # Send initial success status
        yield dockyard_pb2.LogsResponse(
            status=dockyard_pb2.LogsStatus(
                success=True,
                message=f"Streaming logs for container '{container_identifier}'"
            )
        )

        # Get logs from Docker
        logs_generator = container.logs(
            stdout=stdout,
            stderr=stderr,
            stream=True,
            follow=follow,
            tail=tail,
            since=since_datetime,
            timestamps=timestamps
        )

        # Stream logs to client
        for log_line in logs_generator:
            if not log_line:
                continue

            # Parse Docker's stream format when both stdout and stderr are requested
            if stdout and stderr and len(log_line) >= 8:
                # Docker multiplexes stdout/stderr with 8-byte header
                stream_type = log_line[0]

                if stream_type in [1, 2]:
                    try:
                        size = int.from_bytes(log_line[4:8], 'big')
                        if size <= len(log_line) - 8:
                            payload = log_line[8:8+size]
                            stream_name = 'stdout' if stream_type == 1 else 'stderr'
                        else:
                            payload = log_line
                            stream_name = 'stdout'
                    except:
                        payload = log_line
                        stream_name = 'stdout'
                else:
                    payload = log_line
                    stream_name = 'stdout'
            else:
                payload = log_line
                stream_name = 'stdout' if stdout else 'stderr'

            # Extract timestamp if present
            timestamp_str = ""
            if timestamps and payload:
                try:
                    decoded = payload.decode('utf-8', errors='replace')
                    ts_match = re.match(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s+(.*)$', decoded)
                    if ts_match:
                        timestamp_str = ts_match.group(1)
                        payload = ts_match.group(2).encode('utf-8')
                except:
                    pass

            # Send log entry
            yield dockyard_pb2.LogsResponse(
                log=dockyard_pb2.LogEntry(
                    data=payload,
                    stream_type=stream_name,
                    timestamp=timestamp_str
                )
            )

        # Send finished status for non-follow mode
        if not follow:
            yield dockyard_pb2.LogsResponse(
                status=dockyard_pb2.LogsStatus(
                    success=True,
                    message="All logs retrieved",
                    finished=True
                )
            )

    except Exception as e:
        logger.error(f"GetLogs error: {e}")
        yield dockyard_pb2.LogsResponse(
            status=dockyard_pb2.LogsStatus(
                success=False,
                message=f"Internal error: {str(e)}",
                finished=True
            )
        )
```

**Key concepts:**
- **Docker Logs API**: Using `container.logs()` with streaming and various options
- **Time Parsing**: Converting relative time formats to datetime objects
- **Stream Multiplexing**: Parsing Docker's 8-byte header format for stdout/stderr
- **Timestamp Extraction**: Parsing ISO 8601 timestamps from log data
- **Generator Pattern**: Yielding log entries as they arrive

#### 2.3 CLI Changes (`cli/main.py`)

**What was added:**
```python
def get_logs(self, container_identifier, follow=False, tail=0, since=None, timestamps=False, stdout=True, stderr=True):
    """Get container logs with streaming support"""
    request = dockyard_pb2.LogsRequest(
        container_identifier=container_identifier,
        follow=follow,
        tail=tail,
        since=since or '',
        timestamps=timestamps,
        stdout=stdout,
        stderr=stderr
    )

    try:
        response_stream = self.stub.GetLogs(request)
        return response_stream
    except grpc.RpcError as e:
        click.echo(f"Error: Failed to connect to agent - {e.details()}", err=True)
        return None

@cli.command()
@click.argument('container', required=True)
@click.option('--follow', '-f', is_flag=True, help='Follow log output (like tail -f)')
@click.option('--tail', '-n', default=0, help='Number of lines from end (0 = all)')
@click.option('--since', help='Show logs since relative time (e.g., 1h, 30m, 10s)')
@click.option('--timestamps', '-t', is_flag=True, help='Show timestamps')
@click.option('--no-stdout', is_flag=True, help='Do not include stdout')
@click.option('--no-stderr', is_flag=True, help='Do not include stderr')
@click.pass_context
def logs(ctx, container, follow, tail, since, timestamps, no_stdout, no_stderr):
    """View container logs

    Examples:
        dockyard logs web-server
        dockyard logs -f web-server
        dockyard logs --tail 100 web-server
        dockyard logs --since 1h web-server
        dockyard logs -f -t web-server
    """
    client = ctx.obj['client']

    # Determine which streams to include
    stdout = not no_stdout
    stderr = not no_stderr

    if not stdout and not stderr:
        click.echo("Error: Cannot exclude both stdout and stderr", err=True)
        sys.exit(1)

    # Validate tail option
    if tail < 0:
        click.echo("Error: Tail value must be non-negative", err=True)
        sys.exit(1)

    # Validate since format if provided
    if since:
        import re
        if not re.match(r'^\d+[smhd]$', since):
            click.echo("Error: Invalid since format. Use format like '1h', '30m', '10s', '7d'", err=True)
            sys.exit(1)

    click.echo(f"{'Following' if follow else 'Getting'} logs for container '{container}'...")

    if tail > 0:
        click.echo(f"Showing last {tail} lines")
    if since:
        click.echo(f"Logs since {since} ago")

    try:
        # Get response stream
        response_stream = client.get_logs(
            container_identifier=container,
            follow=follow,
            tail=tail,
            since=since,
            timestamps=timestamps,
            stdout=stdout,
            stderr=stderr
        )

        if not response_stream:
            sys.exit(1)

        # Handle responses
        for response in response_stream:
            if response.HasField('status'):
                status = response.status
                if not status.success:
                    click.echo(f"Error: {status.message}", err=True)
                    sys.exit(1)

                if status.finished:
                    # Non-follow mode completed
                    break

            elif response.HasField('log'):
                log_entry = response.log
                data = log_entry.data

                # Format output with optional coloring for stderr
                if log_entry.stream_type == 'stderr':
                    # Output to stderr
                    if timestamps and log_entry.timestamp:
                        sys.stderr.buffer.write(f"{log_entry.timestamp} ".encode('utf-8'))
                    sys.stderr.buffer.write(data)
                    sys.stderr.buffer.flush()
                else:
                    # Output to stdout
                    if timestamps and log_entry.timestamp:
                        sys.stdout.buffer.write(f"{log_entry.timestamp} ".encode('utf-8'))
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()

        client.close()

    except KeyboardInterrupt:
        click.echo("\nLog streaming interrupted by user")
        client.close()
        sys.exit(130)  # Standard exit code for Ctrl+C
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        client.close()
        sys.exit(1)
```

**Key features:**
- **Multiple Options**: All standard Docker log options supported
- **Stream Control**: Choose stdout, stderr, or both
- **Input Validation**: Validate tail values and time formats
- **Real-time Streaming**: Direct binary output to stdout/stderr
- **Graceful Interruption**: Proper Ctrl+C handling

## Step-by-Step Setup and Testing

### 3. EC2 Instance Setup

#### 3.1 Launch and Configure EC2 Instance

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

### 5. Testing Lab 04 Logs Functionality

Now let's test all the logs functionality we implemented:

#### 5.1 Basic Log Retrieval

```bash
# Launch a test container first
python3 cli/main.py --host $EC2_IP launch nginx:alpine --name web-server

# Verify container is running
ssh -i your-key.pem ubuntu@$EC2_IP "docker ps | grep web-server"

# Test basic log retrieval
python3 cli/main.py --host $EC2_IP logs web-server

# Expected output:
# Getting logs for container 'web-server'...
# /docker-entrypoint.sh: /docker-entrypoint.d/ is not empty, will attempt to perform configuration
# /docker-entrypoint.sh: Looking for shell scripts in /docker-entrypoint.d/
# /docker-entrypoint.sh: Launching /docker-entrypoint.d/10-listen-on-ipv6-by-default.sh
# [... nginx startup logs ...]
```

#### 5.2 Tail Operation

```bash
# Test tail option - show last 10 lines
python3 cli/main.py --host $EC2_IP logs --tail 10 web-server

# Expected output:
# Getting logs for container 'web-server'...
# Showing last 10 lines
# [Last 10 lines of logs]

# Test tail with specific number
python3 cli/main.py --host $EC2_IP logs --tail 5 web-server
# Shows only last 5 lines

python3 cli/main.py --host $EC2_IP logs -n 20 web-server
# Shows last 20 lines using short option
```

#### 5.3 Follow Mode

```bash
# Test follow mode (like tail -f)
python3 cli/main.py --host $EC2_IP logs -f web-server

# Expected output:
# Following logs for container 'web-server'...
# [Existing logs]
# [Waits for new logs...]
# Press Ctrl+C to stop following

# In another terminal, generate some activity
python3 cli/main.py --host $EC2_IP exec web-server sh -c "echo 'Test log entry'"

# You should see the new log appear in the follow terminal

# Test follow with tail
python3 cli/main.py --host $EC2_IP logs -f --tail 5 web-server
# Shows last 5 lines then follows new logs
```

#### 5.4 Timestamps

```bash
# Test with timestamps
python3 cli/main.py --host $EC2_IP logs --timestamps web-server

# Expected output:
# Getting logs for container 'web-server'...
# 2024-09-27T06:11:13.689620830Z /docker-entrypoint.sh: /docker-entrypoint.d/ is not empty
# 2024-09-27T06:11:13.692097806Z /docker-entrypoint.sh: Looking for shell scripts
# [... logs with ISO 8601 timestamps ...]

# Test timestamps with follow
python3 cli/main.py --host $EC2_IP logs -f -t web-server
# Shows timestamps for all logs including new ones
```

#### 5.5 Time-based Filtering

```bash
# Create a long-running container with periodic logs
python3 cli/main.py --host $EC2_IP launch busybox:latest --name test-logs

# Generate some logs over time
python3 cli/main.py --host $EC2_IP exec test-logs sh -c \
  "for i in 1 2 3 4 5; do echo \"Log entry \$i at \$(date)\"; sleep 60; done" &

# Wait a few minutes, then test time filtering

# Test logs from last 2 minutes
python3 cli/main.py --host $EC2_IP logs --since 2m test-logs

# Test logs from last 30 seconds
python3 cli/main.py --host $EC2_IP logs --since 30s test-logs

# Test logs from last hour
python3 cli/main.py --host $EC2_IP logs --since 1h test-logs

# Test logs from last day
python3 cli/main.py --host $EC2_IP logs --since 1d test-logs
```

#### 5.6 Stream Filtering

```bash
# Launch a container that produces both stdout and stderr
python3 cli/main.py --host $EC2_IP launch busybox:latest --name test-streams

# Generate stdout and stderr
python3 cli/main.py --host $EC2_IP exec test-streams sh -c \
  "echo 'This is stdout'; echo 'This is stderr' >&2; echo 'More stdout'"

# Get all logs (default)
python3 cli/main.py --host $EC2_IP logs test-streams
# Shows both stdout and stderr

# Get only stdout
python3 cli/main.py --host $EC2_IP logs --no-stderr test-streams
# Shows only: This is stdout, More stdout

# Get only stderr
python3 cli/main.py --host $EC2_IP logs --no-stdout test-streams
# Shows only: This is stderr
```

#### 5.7 Combined Options

```bash
# Test multiple options together
python3 cli/main.py --host $EC2_IP logs --tail 10 --timestamps web-server
# Last 10 lines with timestamps

python3 cli/main.py --host $EC2_IP logs --since 5m --timestamps web-server
# Logs from last 5 minutes with timestamps

python3 cli/main.py --host $EC2_IP logs -f --tail 5 -t web-server
# Follow mode showing last 5 lines with timestamps

# Complex combination
python3 cli/main.py --host $EC2_IP logs --since 10m --tail 20 --timestamps --no-stderr web-server
# Last 20 lines from the last 10 minutes, timestamps, stdout only
```

#### 5.8 Error Handling

```bash
# Test with non-existent container
python3 cli/main.py --host $EC2_IP logs non-existent-container

# Expected output:
# Getting logs for container 'non-existent-container'...
# Error: Container 'non-existent-container' not found

# Test with invalid tail value
python3 cli/main.py --host $EC2_IP logs --tail -5 web-server

# Expected output:
# Error: Tail value must be non-negative

# Test with invalid since format
python3 cli/main.py --host $EC2_IP logs --since 5x web-server

# Expected output:
# Error: Invalid since format. Use format like '1h', '30m', '10s', '7d'

# Test excluding both stdout and stderr
python3 cli/main.py --host $EC2_IP logs --no-stdout --no-stderr web-server

# Expected output:
# Error: Cannot exclude both stdout and stderr
```

#### 5.9 Real-time Log Streaming Test

```bash
# Launch a container that generates continuous logs
python3 cli/main.py --host $EC2_IP launch busybox:latest --name log-generator

# Start a log generator in the background
ssh -i your-key.pem ubuntu@$EC2_IP \
  "docker exec -d log-generator sh -c 'while true; do date; echo \"Log entry at \$(date)\"; sleep 2; done'"

# Follow the logs in real-time
python3 cli/main.py --host $EC2_IP logs -f log-generator

# You should see new log entries appearing every 2 seconds
# Press Ctrl+C to stop following

# Test with timestamps to see exact timing
python3 cli/main.py --host $EC2_IP logs -f -t log-generator
```

### 6. Understanding the Results

#### 6.1 Streaming Architecture

- **Server-side Streaming**: Agent sends logs as they're generated
- **Non-blocking**: Follow mode doesn't block other operations
- **Efficient**: Only requested data is sent (tail, since filtering)

#### 6.2 Time Format Support

**Supported time units:**
- `s` - seconds (e.g., `30s`)
- `m` - minutes (e.g., `5m`)
- `h` - hours (e.g., `2h`)
- `d` - days (e.g., `1d`)

#### 6.3 Docker Log Stream Format

**When both stdout and stderr are requested:**
- Docker multiplexes streams with 8-byte headers
- Byte 0: stream type (1=stdout, 2=stderr)
- Bytes 4-7: payload size (big-endian)
- Remaining bytes: actual log data

### 7. Advanced Testing Scenarios

#### 7.1 High-Volume Log Testing

```bash
# Create a container that generates many logs quickly
python3 cli/main.py --host $EC2_IP launch busybox:latest --name high-volume

# Generate high-volume logs
ssh -i your-key.pem ubuntu@$EC2_IP \
  "docker exec -d high-volume sh -c 'for i in \$(seq 1 1000); do echo \"Log line \$i\"; done'"

# Test tail with high volume
python3 cli/main.py --host $EC2_IP logs --tail 100 high-volume
# Should efficiently show only last 100 lines

# Test streaming performance
python3 cli/main.py --host $EC2_IP logs -f high-volume
```

#### 7.2 Multi-line Log Testing

```bash
# Create container with multi-line logs
python3 cli/main.py --host $EC2_IP launch busybox:latest --name multi-line

# Generate multi-line logs (like stack traces)
python3 cli/main.py --host $EC2_IP exec multi-line sh -c \
  "echo 'Error occurred:'; echo '  at function1()'; echo '  at function2()'; echo '  at main()'"

# View multi-line logs
python3 cli/main.py --host $EC2_IP logs multi-line
# Should preserve multi-line format
```

#### 7.3 Long-Running Container Logs

```bash
# Test with a container that has been running for a while
python3 cli/main.py --host $EC2_IP launch nginx:alpine --name long-runner

# Let it run for some time, then check various time ranges
sleep 300  # Wait 5 minutes

# Get all logs
python3 cli/main.py --host $EC2_IP logs long-runner

# Get recent logs only
python3 cli/main.py --host $EC2_IP logs --since 1m long-runner

# Compare the difference in output volume
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

#### 8.2 Log Streaming Issues

**No logs appearing:**
```bash
# Check if container is actually generating logs
ssh -i your-key.pem ubuntu@$EC2_IP "docker logs <container-name>"

# Check container status
ssh -i your-key.pem ubuntu@$EC2_IP "docker ps -a | grep <container-name>"
```

**Follow mode not working:**
```bash
# Ensure container is running
python3 cli/main.py --host $EC2_IP launch nginx:alpine --name test-follow

# Generate activity to produce logs
python3 cli/main.py --host $EC2_IP exec test-follow sh -c "echo 'test'"

# Try follow mode again
python3 cli/main.py --host $EC2_IP logs -f test-follow
```

#### 8.3 Time Filtering Issues

**Logs not showing with --since:**
```bash
# Make sure container has been running long enough
ssh -i your-key.pem ubuntu@$EC2_IP "docker ps --format 'table {{.Names}}\t{{.Status}}'"

# Try without time filter first
python3 cli/main.py --host $EC2_IP logs <container-name>

# Then try with longer time period
python3 cli/main.py --host $EC2_IP logs --since 1h <container-name>
```

## Key Learning Points

### 1. gRPC Server-side Streaming
- Unidirectional streaming from server to client
- Efficient for continuous data like logs
- Generator pattern for memory efficiency

### 2. Docker Logs API
- Stream parameter for real-time logs
- Follow mode for continuous monitoring
- Tail and since options for filtering

### 3. Time Parsing and Filtering
- Relative time format parsing
- UTC datetime calculations
- Efficient time-based filtering

### 4. Stream Multiplexing
- Docker's 8-byte header format
- Separating stdout and stderr
- Binary data handling

### 5. CLI Design for Streaming
- Non-blocking I/O patterns
- Direct binary output to stdout/stderr
- Proper signal handling for interruption

## Next Steps

Congratulations! You've successfully implemented and tested container logs functionality with server-side streaming. You now have:

- Server-side gRPC streaming for continuous data
- Full Docker logs API integration
- Real-time log following capability
- Time-based and line-based filtering
- Proper stream separation and multiplexing

**Ready for Advanced Features?** Consider implementing:
- Log aggregation from multiple containers
- Log search and grep functionality
- Log rotation and archival
- Structured logging support (JSON logs)
- Log forwarding to external systems

**Want to explore more?** Try:
- Building a web-based log viewer
- Implementing log analytics and metrics
- Adding log alerting based on patterns
- Creating log correlation across containers

## Cleanup

When you're done testing, clean up your EC2 resources:

```bash
# Stop and remove all test containers
ssh -i your-key.pem ubuntu@$EC2_IP "docker stop \$(docker ps -aq) && docker rm \$(docker ps -aq)"

# Stop the agent
ssh -i your-key.pem ubuntu@$EC2_IP "pkill -f 'python3 agent/main.py'"

# Remember to terminate your EC2 instance when you're done
```

---

**Congratulations on completing Lab 04!** You've built a sophisticated container logging system with real-time streaming, comprehensive filtering options, and production-ready features.