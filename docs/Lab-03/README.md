# Lab 03: Container Exec Operations

## Introduction

Welcome to Dockyard Lab 03! In this lab, you'll extend your container orchestration system by adding comprehensive container exec functionality. You'll learn how to execute commands inside running containers, handle interactive shell sessions, manage streaming I/O, and implement cross-platform terminal handling.

**What You'll Learn:**
- Bidirectional gRPC streaming for real-time communication
- Docker exec API with socket-level communication
- Cross-platform terminal handling (Windows/Unix)
- Interactive shell sessions with TTY allocation
- Command execution with user context switching
- Environment variable injection and working directory control

**What You'll Build:**
- `ExecContainer` streaming RPC method in the agent
- `exec` command in the CLI with interactive support
- Support for both interactive shells and one-time commands
- User context switching and environment control
- Cross-platform input handling for interactive sessions

## Prerequisites

- Completed Lab 02 or familiar with gRPC services and container operations
- AWS EC2 instance with SSH access
- Python 3.8+ installed locally
- Basic understanding of containers, terminals, and process management

## Getting Started

### 1. Clone Repository and Checkout Lab 03

```bash
# Clone the repository
git clone <your-repo-url>
cd dockyard

# Checkout lab-03 branch
git checkout lab-03

# Verify you're on the right branch and see what's included
git branch
ls -la
```

### 2. Understanding the Lab 03 Changes

Before we deploy and test, let's understand what's new in Lab 03 compared to Lab 02:

#### 2.1 Protocol Buffer Changes (`proto/dockyard.proto`)

**What was added:**
```protobuf
service DockyardService {
    rpc LaunchContainer(LaunchRequest) returns (LaunchResponse);
    rpc StopContainer(StopRequest) returns (StopResponse);
    rpc ExecContainer(stream ExecRequest) returns (stream ExecResponse);  // ← NEW
}

// NEW: Bidirectional streaming exec request
message ExecRequest {
    oneof request_type {
        ExecStart start = 1;      // Initial exec configuration
        ExecInput input = 2;      // Stdin data during execution
    }
}

// NEW: Exec start configuration
message ExecStart {
    string container_identifier = 1; // name or ID
    repeated string command = 2;     // command and arguments
    bool interactive = 3;            // allocate TTY for interactive session
    string user = 4;                 // user to run as (optional)
    string working_dir = 5;          // working directory (optional)
    map<string, string> environment = 6; // environment variables
}

// NEW: Stdin data for interactive sessions
message ExecInput {
    bytes data = 1;                  // stdin data
}

// NEW: Streaming exec response
message ExecResponse {
    oneof response_type {
        ExecStatus status = 1;       // Status updates and completion
        ExecOutput output = 2;       // Stdout/stderr data
    }
}

// NEW: Execution status and completion info
message ExecStatus {
    bool success = 1;
    string exec_id = 2;              // execution ID
    string message = 3;
    int32 exit_code = 4;             // command exit code (when finished)
    bool finished = 5;               // true when command execution is complete
}

// NEW: Output stream data
message ExecOutput {
    bytes data = 1;                  // stdout/stderr data
    string stream_type = 2;          // "stdout" or "stderr"
}
```

**Why these changes:**
- **Bidirectional Streaming**: `stream ExecRequest` and `stream ExecResponse` enable real-time communication
- **oneof Pattern**: Flexible message types for different phases of execution
- **Interactive Support**: TTY allocation and stdin streaming for shell sessions
- **Context Control**: User, working directory, and environment variable control
- **Output Separation**: Separate stdout and stderr streams

#### 2.2 Agent Changes (`agent/main.py`)

**What was added:**
```python
import threading
import queue

def ExecContainer(self, request_iterator, context):
    """Execute commands in a container with bidirectional streaming"""
    try:
        # Get the first request (should be ExecStart)
        first_request = next(request_iterator)

        if not first_request.HasField('start'):
            yield dockyard_pb2.ExecResponse(
                status=dockyard_pb2.ExecStatus(
                    success=False,
                    message="First request must be ExecStart"
                )
            )
            return

        exec_start = first_request.start
        container_identifier = exec_start.container_identifier
        command = list(exec_start.command)
        interactive = exec_start.interactive
        user = exec_start.user if exec_start.user else None
        working_dir = exec_start.working_dir if exec_start.working_dir else None
        environment = dict(exec_start.environment) if exec_start.environment else None

        # Find the container
        container = self.docker_client.containers.get(container_identifier)

        # Check if container is running
        container.reload()
        if container.status != 'running':
            yield dockyard_pb2.ExecResponse(
                status=dockyard_pb2.ExecStatus(
                    success=False,
                    message=f"Container '{container_identifier}' is not running (status: {container.status})"
                )
            )
            return

        # Create exec instance
        exec_config = {
            'cmd': command,
            'stdout': True,
            'stderr': True,
            'stdin': True,
            'tty': interactive,
        }

        if user:
            exec_config['user'] = user
        if working_dir:
            exec_config['workdir'] = working_dir
        if environment:
            exec_config['environment'] = environment

        exec_instance = self.docker_client.api.exec_create(
            container.id,
            **exec_config
        )
        exec_id = exec_instance['Id']

        # Start execution with socket for bidirectional communication
        exec_socket = self.docker_client.api.exec_start(
            exec_id,
            detach=False,
            tty=interactive,
            stream=True,
            socket=True
        )

        # Send initial success status
        yield dockyard_pb2.ExecResponse(
            status=dockyard_pb2.ExecStatus(
                success=True,
                exec_id=exec_id[:12],
                message="Execution started successfully"
            )
        )

        # Create queues for thread communication
        input_queue = queue.Queue()
        output_queue = queue.Queue()

        # Thread to handle stdin from client
        def handle_input():
            try:
                for request in request_iterator:
                    if request.HasField('input'):
                        input_data = request.input.data
                        if input_data:
                            exec_socket._sock.send(input_data)
            except Exception as e:
                logger.error(f"Input handling error: {e}")
            finally:
                # Close the socket when no more input
                try:
                    exec_socket._sock.shutdown(1)  # Shutdown write side
                except:
                    pass

        # Thread to handle stdout/stderr from container
        def handle_output():
            try:
                while True:
                    try:
                        # Receive data from exec socket
                        data = exec_socket._sock.recv(4096)
                        if not data:
                            break

                        # For TTY mode, all output comes as stdout
                        # For non-TTY mode, Docker multiplexes stdout/stderr
                        if interactive:
                            output_queue.put(('stdout', data))
                        else:
                            # Parse Docker's stream format for stdout/stderr separation
                            if len(data) >= 8:
                                stream_type = data[0]  # 1=stdout, 2=stderr
                                size = int.from_bytes(data[4:8], 'big')
                                payload = data[8:8+size] if size <= len(data)-8 else data[8:]

                                stream_name = 'stdout' if stream_type == 1 else 'stderr'
                                output_queue.put((stream_name, payload))
                            else:
                                # Fallback for malformed data
                                output_queue.put(('stdout', data))

                    except Exception as e:
                        logger.error(f"Output handling error: {e}")
                        break

                output_queue.put((None, None))  # Signal end
            except Exception as e:
                logger.error(f"Output thread error: {e}")
                output_queue.put((None, None))

        # Start threads
        input_thread = threading.Thread(target=handle_input)
        output_thread = threading.Thread(target=handle_output)

        input_thread.daemon = True
        output_thread.daemon = True

        input_thread.start()
        output_thread.start()

        # Send output to client
        try:
            while True:
                try:
                    stream_type, data = output_queue.get(timeout=1)
                    if stream_type is None:  # End signal
                        break

                    if data:
                        yield dockyard_pb2.ExecResponse(
                            output=dockyard_pb2.ExecOutput(
                                data=data,
                                stream_type=stream_type
                            )
                        )
                except queue.Empty:
                    # Check if exec is still running
                    try:
                        exec_info = self.docker_client.api.exec_inspect(exec_id)
                        if not exec_info.get('Running', True):
                            break
                    except:
                        break
                    continue

        except Exception as e:
            logger.error(f"Output streaming error: {e}")

        # Get final execution result
        try:
            exec_info = self.docker_client.api.exec_inspect(exec_id)
            exit_code = exec_info.get('ExitCode', 0)

            yield dockyard_pb2.ExecResponse(
                status=dockyard_pb2.ExecStatus(
                    success=True,
                    exec_id=exec_id[:12],
                    message="Execution completed",
                    exit_code=exit_code,
                    finished=True
                )
            )

            logger.info(f"Exec {exec_id[:12]} completed with exit code {exit_code}")

        except Exception as e:
            logger.error(f"Failed to get exec result: {e}")
            yield dockyard_pb2.ExecResponse(
                status=dockyard_pb2.ExecStatus(
                    success=False,
                    exec_id=exec_id[:12],
                    message=f"Failed to get execution result: {str(e)}",
                    finished=True
                )
            )

        # Cleanup
        try:
            exec_socket.close()
        except:
            pass
```

**Key concepts:**
- **Bidirectional Streaming**: Client sends commands/input, server streams back output
- **Socket-Level Communication**: Direct socket access for low-latency I/O
- **Threading**: Separate threads for handling input and output concurrently
- **Docker Stream Format**: Parsing Docker's multiplexed stdout/stderr format
- **TTY vs Non-TTY**: Different handling for interactive vs batch mode
- **Context Control**: User, working directory, and environment variable support

#### 2.3 CLI Changes (`cli/main.py`)

**What was added:**
```python
# Platform-specific imports
try:
    import select
    import tty
    import termios
    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False

try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

def exec_container(self, container_identifier, command, interactive=False, user=None, working_dir=None, environment=None):
    """Execute a command in a container with streaming support"""
    try:
        def generate_requests():
            # Send initial ExecStart request
            exec_start = dockyard_pb2.ExecStart(
                container_identifier=container_identifier,
                command=command,
                interactive=interactive,
                user=user or '',
                working_dir=working_dir or '',
                environment=environment or {}
            )

            yield dockyard_pb2.ExecRequest(start=exec_start)

            # For interactive mode, handle stdin input
            if interactive:
                # Set up raw terminal mode for interactive input
                old_settings = None
                try:
                    if HAS_TERMIOS:
                        old_settings = termios.tcgetattr(sys.stdin.fileno())
                        tty.setraw(sys.stdin.fileno())
                except:
                    pass  # Not a TTY

                try:
                    while True:
                        # Use platform-specific input handling
                        if HAS_TERMIOS and sys.platform != 'win32':
                            # Unix/Linux
                            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                            if ready:
                                data = sys.stdin.read(1).encode('utf-8')
                                if data:
                                    yield dockyard_pb2.ExecRequest(
                                        input=dockyard_pb2.ExecInput(data=data)
                                    )
                        elif HAS_MSVCRT:
                            # Windows
                            if msvcrt.kbhit():
                                data = msvcrt.getch()
                                if data:
                                    yield dockyard_pb2.ExecRequest(
                                        input=dockyard_pb2.ExecInput(data=data)
                                    )
                            else:
                                time.sleep(0.1)  # Prevent busy waiting
                        else:
                            # Fallback for unsupported platforms
                            time.sleep(0.1)
                except KeyboardInterrupt:
                    # Send Ctrl+C to container
                    yield dockyard_pb2.ExecRequest(
                        input=dockyard_pb2.ExecInput(data=b'\\x03')
                    )
                finally:
                    # Restore terminal settings
                    if old_settings and HAS_TERMIOS:
                        try:
                            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
                        except:
                            pass

        # Start streaming
        response_stream = self.stub.ExecContainer(generate_requests())
        return response_stream

@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument('container', required=True)
@click.argument('command', nargs=-1, required=False)
@click.option('--interactive', '-i', is_flag=True, help='Run in interactive mode (allocate TTY)')
@click.option('--user', '-u', help='Run as specified user')
@click.option('--workdir', '-w', help='Working directory inside container')
@click.option('--env', '-e', multiple=True, help='Set environment variables (KEY=VALUE)')
@click.pass_context
def exec(ctx, container, command, interactive, user, workdir, env):
    """Execute commands in a running container

    Examples:
        dockyard exec web-server ls -la
        dockyard exec --interactive web-server bash
        dockyard exec --user root web-server "apt update"
        dockyard exec --env "DEBUG=true" web-server python script.py
    """
    client = ctx.obj['client']

    # Parse command
    if not command and not interactive:
        click.echo("Error: Command is required unless using --interactive mode", err=True)
        sys.exit(1)

    # If interactive and no command, default to shell
    if interactive and not command:
        command = ['bash']  # Default to bash for interactive
    elif command:
        command = list(command)
    else:
        command = []

    # Parse environment variables
    environment = {}
    for env_var in env:
        if '=' in env_var:
            key, value = env_var.split('=', 1)
            environment[key] = value
        else:
            click.echo(f"Warning: Invalid environment variable format: {env_var}", err=True)

    click.echo(f"Executing {'interactive ' if interactive else ''}command in container '{container}'...")
    if command:
        click.echo(f"Command: {' '.join(command)}")

    try:
        # Get response stream
        response_stream = client.exec_container(
            container_identifier=container,
            command=command,
            interactive=interactive,
            user=user,
            working_dir=workdir,
            environment=environment
        )

        if not response_stream:
            sys.exit(1)

        exit_code = 0
        exec_started = False

        # Handle responses
        for response in response_stream:
            if response.HasField('status'):
                status = response.status
                if not status.success:
                    click.echo(f"Error: {status.message}", err=True)
                    sys.exit(1)

                if status.finished:
                    exit_code = status.exit_code
                    if not exec_started:
                        # Only show completion message if we haven't shown any output
                        click.echo(f"Command completed with exit code {exit_code}")
                    break
                elif not exec_started:
                    exec_started = True

            elif response.HasField('output'):
                output = response.output
                data = output.data

                # Write output directly to stdout/stderr
                if output.stream_type == 'stderr':
                    sys.stderr.buffer.write(data)
                    sys.stderr.buffer.flush()
                else:
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()

        client.close()

        # Exit with the same code as the command
        if exit_code != 0:
            sys.exit(exit_code)

    except KeyboardInterrupt:
        click.echo("\\nExecution interrupted by user")
        client.close()
        sys.exit(130)  # Standard exit code for Ctrl+C
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        client.close()
        sys.exit(1)
```

**Key features:**
- **Cross-Platform Input**: Handles Windows (`msvcrt`) and Unix (`termios`, `tty`, `select`) platforms
- **Interactive Sessions**: Raw terminal mode for interactive shell sessions
- **Context Settings**: `ignore_unknown_options` prevents CLI option conflicts
- **Real-Time Streaming**: Direct binary output streaming to stdout/stderr
- **Signal Handling**: Proper Ctrl+C forwarding to container
- **Environment Parsing**: Support for KEY=VALUE environment variables

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
venv\\Scripts\\activate
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

### 5. Testing Lab 03 Exec Functionality

Now let's test all the exec functionality we implemented:

#### 5.1 Basic Command Execution

```bash
# Launch a test container first
python3 cli/main.py --host $EC2_IP launch nginx:latest --name test-exec

# Verify container is running
ssh -i your-key.pem ubuntu@$EC2_IP "docker ps | grep test-exec"

# Test basic command execution
python3 cli/main.py --host $EC2_IP exec test-exec ls -la

# Expected output:
# Executing command in container 'test-exec'...
# Command: ls -la
# total 72
# drwxr-xr-x   1 root root 4096 Sep 25 16:06 .
# drwxr-xr-x   1 root root 4096 Sep 25 16:06 ..
# -rwxr-xr-x   1 root root    0 Sep 25 16:06 .dockerenv
# [... directory listing ...]

# Test simple commands
python3 cli/main.py --host $EC2_IP exec test-exec whoami
# Expected: root

python3 cli/main.py --host $EC2_IP exec test-exec pwd
# Expected: /
```

#### 5.2 User Context Switching

```bash
# Test running command as different user
python3 cli/main.py --host $EC2_IP exec --user nobody test-exec whoami
# Expected: nobody

# Test with different user (if available)
python3 cli/main.py --host $EC2_IP exec --user www-data test-exec whoami
# Expected: www-data (or error if user doesn't exist)
```

#### 5.3 Environment Variable Injection

```bash
# Test environment variables
python3 cli/main.py --host $EC2_IP exec --env "TEST_VAR=Hello World" test-exec env | grep TEST_VAR
# Expected: TEST_VAR=Hello World

# Test multiple environment variables
python3 cli/main.py --host $EC2_IP exec --env "DEBUG=true" --env "MODE=test" test-exec env | grep -E "(DEBUG|MODE)"
# Expected:
# DEBUG=true
# MODE=test
```

#### 5.4 Working Directory Control

```bash
# Test working directory (if path exists)
python3 cli/main.py --host $EC2_IP exec --workdir /var/log test-exec pwd
# Expected: /var/log

# Test with another directory
python3 cli/main.py --host $EC2_IP exec --workdir /tmp test-exec pwd
# Expected: /tmp
```

#### 5.5 Interactive Shell Sessions

```bash
# Test interactive mode (this will open a shell)
python3 cli/main.py --host $EC2_IP exec --interactive test-exec bash

# Expected: You'll get an interactive bash prompt like:
# Executing interactive command in container 'test-exec'...
# Command: bash
# root@1234567890ab:/#

# In the interactive session, you can run commands:
# ls
# ps aux
# echo "Hello from inside container"
# exit

# To test interactive mode without staying in it, use timeout or non-interactive commands
timeout 5 python3 cli/main.py --host $EC2_IP exec --interactive test-exec bash -c "echo 'Interactive test' && exit"
```

#### 5.6 Complex Command Arguments

```bash
# Test commands with multiple arguments and options
python3 cli/main.py --host $EC2_IP exec test-exec find /var -name "*.log" -type f
# Expected: List of log files (if any)

# Test commands with pipes and redirects (note: shell interpretation)
python3 cli/main.py --host $EC2_IP exec test-exec bash -c "ps aux | grep nginx | head -5"
# Expected: Process list filtered for nginx

# Test complex shell commands
python3 cli/main.py --host $EC2_IP exec test-exec bash -c "echo 'Current time:' && date && echo 'Disk usage:' && df -h /"
# Expected:
# Current time:
# [current date/time]
# Disk usage:
# [disk usage information]
```

#### 5.7 Error Handling Tests

```bash
# Test command on non-existent container
python3 cli/main.py --host $EC2_IP exec non-existent-container ls
# Expected: Error: Container 'non-existent-container' not found

# Test invalid command
python3 cli/main.py --host $EC2_IP exec test-exec invalid-command-that-doesnt-exist
# Expected: Command will run but exit with non-zero exit code

# Test command on stopped container
python3 cli/main.py --host $EC2_IP stop test-exec
python3 cli/main.py --host $EC2_IP exec test-exec ls
# Expected: Error: Container 'test-exec' is not running (status: exited)

# Restart container for more tests
python3 cli/main.py --host $EC2_IP launch nginx:latest --name test-exec
```

#### 5.8 Exit Code Testing

```bash
# Test successful command (exit code 0)
python3 cli/main.py --host $EC2_IP exec test-exec true
echo $?  # Should be 0

# Test failing command (exit code 1)
python3 cli/main.py --host $EC2_IP exec test-exec false
echo $?  # Should be 1

# Test command with specific exit code
python3 cli/main.py --host $EC2_IP exec test-exec bash -c "exit 42"
echo $?  # Should be 42
```

#### 5.9 Streaming Output Test

```bash
# Test command with continuous output
python3 cli/main.py --host $EC2_IP exec test-exec bash -c "for i in {1..5}; do echo 'Line $i'; sleep 1; done"
# Expected: You should see lines appear one by one with 1-second delays

# Test stderr vs stdout
python3 cli/main.py --host $EC2_IP exec test-exec bash -c "echo 'stdout message' && echo 'stderr message' >&2"
# Expected: Both messages should appear (stderr may be in different color if terminal supports it)
```

### 6. Advanced Testing Scenarios

#### 6.1 Cross-Platform Terminal Features

```bash
# Test Ctrl+C handling in interactive session (be careful!)
python3 cli/main.py --host $EC2_IP exec --interactive test-exec bash
# In the interactive session, try Ctrl+C - it should be forwarded to the container
# exit to return to local terminal
```

#### 6.2 Long-Running Interactive Sessions

```bash
# Test interactive session with tools (if available in nginx container)
python3 cli/main.py --host $EC2_IP exec --interactive test-exec bash

# Inside the container:
# apt update && apt install -y vim nano htop
# nano /tmp/test.txt  # Test text editor
# htop  # Test interactive process monitor (exit with 'q')
# exit
```

#### 6.3 Container State Verification

```bash
# Check exec processes in container (from another terminal)
ssh -i your-key.pem ubuntu@$EC2_IP "docker exec test-exec ps aux"

# Check container resource usage during exec
ssh -i your-key.pem ubuntu@$EC2_IP "docker stats test-exec --no-stream"
```

### 7. Understanding the Results

#### 7.1 Streaming Communication

- **Request Stream**: Client sends ExecStart followed by ExecInput messages
- **Response Stream**: Server sends ExecStatus and ExecOutput messages
- **Bidirectional**: Both streams operate independently and concurrently

#### 7.2 TTY vs Non-TTY Mode

**Interactive Mode (TTY=true):**
- All output comes as stdout
- Terminal control characters work
- Suitable for shell sessions

**Non-Interactive Mode (TTY=false):**
- Separate stdout/stderr streams
- No terminal control characters
- Suitable for automated commands

#### 7.3 Cross-Platform Considerations

**Windows:**
- Uses `msvcrt.kbhit()` and `msvcrt.getch()`
- Limited terminal control

**Unix/Linux:**
- Uses `select`, `tty`, and `termios`
- Full terminal control and raw mode

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

#### 8.2 Platform-Specific Issues

**Windows Path Issues:**
```bash
# If you see path translation issues, use quotes and forward slashes:
python3 cli/main.py --host $EC2_IP exec test-exec ls "/etc/"
```

**Terminal Issues:**
```bash
# If interactive mode doesn't work properly:
# Make sure you're using a proper terminal (not IDE console)
# On Windows, use PowerShell or Command Prompt, not Git Bash for interactive sessions
```

#### 8.3 Protocol Buffer Version Issues

If you see protobuf errors:

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

## Key Learning Points

### 1. Bidirectional gRPC Streaming
- Real-time communication patterns
- Streaming request and response handling
- Thread-safe queue-based communication

### 2. Docker Exec API
- Socket-level communication
- TTY allocation and management
- Stream multiplexing (stdout/stderr separation)

### 3. Cross-Platform Terminal Handling
- Platform detection and conditional imports
- Raw terminal mode for interactive sessions
- Input handling differences between Windows and Unix

### 4. Protocol Buffer Advanced Patterns
- `oneof` message types for flexible requests
- Streaming message design
- Binary data handling in protobuf

### 5. Interactive System Design
- Real-time input/output streaming
- Signal forwarding (Ctrl+C)
- Session management and cleanup

## Next Steps

Congratulations! You've successfully implemented and tested container exec functionality with bidirectional streaming. You now have:

- ✅ Bidirectional gRPC streaming for real-time communication
- ✅ Full container exec support with interactive shells
- ✅ Cross-platform terminal handling
- ✅ User context switching and environment control
- ✅ Comprehensive streaming I/O with stdout/stderr separation

**Ready for Advanced Features?** Consider implementing:
- Container attach functionality (attach to running processes)
- Container logs streaming
- File copy operations (cp to/from containers)
- Container networking management
- Volume operations and management

**Want to explore more?** Try:
- Building a web-based terminal interface
- Implementing container resource monitoring
- Adding authentication and authorization
- Creating container orchestration workflows

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

**Congratulations on completing Lab 03!** You've built a sophisticated container exec system with real-time bidirectional streaming, cross-platform support, and comprehensive terminal handling.