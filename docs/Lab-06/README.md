# Lab 06: Code Refactoring and Token-Based Authentication

## Introduction

Welcome to Dockyard Lab 06! In this lab, you'll transform the monolithic codebase into a clean, modular architecture while adding secure token-based authentication. You'll learn professional software engineering practices including separation of concerns, service layer pattern, dependency injection, and security best practices.

**What You'll Learn:**
- Clean architecture and modular code organization
- Service layer pattern for business logic separation
- Token-based authentication with gRPC interceptors
- Configuration management with environment variables
- Dependency injection for testability
- Professional project structure following Python conventions
- Security best practices for authentication

**What You'll Build:**
- Modular agent architecture with separate services, authentication, and utilities
- Modular CLI architecture with commands, formatters, and client abstraction
- Token-based authentication system using environment variables
- gRPC interceptors for transparent authentication
- Configuration management system with priority handling
- Comprehensive logging infrastructure
- Clean separation between business logic and transport layer

## Prerequisites

- Completed Lab 05 or familiar with container management operations
- AWS EC2 instance with SSH access
- Python 3.8+ installed locally
- Basic understanding of software architecture patterns
- Familiarity with authentication concepts

## Getting Started

### 1. Clone Repository and Checkout Lab 06

```bash
# Clone the repository
git clone <your-repo-url>
cd dockyard

# Checkout lab-06 branch
git checkout lab-06

# Verify you're on the right branch and see what's included
git branch
ls -la

# Generate protobuf files from proto definition
python3 -m grpc_tools.protoc \
  -I./proto \
  --python_out=. \
  --grpc_python_out=. \
  proto/dockyard.proto

# Verify protobuf files were created
ls -la dockyard_pb2*.py
```

### 2. Understanding the Lab 06 Changes

Lab 06 represents a fundamental architectural transformation of the Dockyard project. While Labs 01-05 focused on adding features and capabilities, Lab 06 focuses on code quality, maintainability, and security. This refactoring ensures the codebase can scale and remain maintainable as the project grows.

Think of this lab as renovating a house while keeping all the rooms functional. The original monolithic files (`agent/main.py` and `cli/main.py`) were becoming unwieldy with 900+ lines of code mixing concerns like business logic, network communication, authentication, and formatting. Lab 06 reorganizes everything into well-defined modules, each with a single responsibility.

The authentication system adds a critical security layer. Previously, anyone who could reach the agent's network endpoint could execute commands. Now, only clients with the correct authentication token can interact with the agent, protecting your infrastructure from unauthorized access.

## Architecture Overview

### Agent Architecture

The refactored agent follows a layered architecture pattern:

```
agent/
├── main.py                  # Application entry point
├── config.py                # Configuration management
├── auth/                    # Authentication layer
│   ├── token_validator.py   # Token validation logic
│   └── interceptor.py       # gRPC server interceptor
├── grpc_server/             # Transport layer
│   ├── server.py            # gRPC server setup
│   └── servicer.py          # RPC method implementations
├── services/                # Business logic layer
│   ├── container_service.py # Container operations
│   ├── exec_service.py      # Exec operations
│   ├── logs_service.py      # Logs operations
│   └── stats_service.py     # Stats operations
├── docker_client/           # Infrastructure layer
│   ├── client.py            # Docker SDK wrapper
│   └── utils.py             # Helper functions
└── utils/                   # Cross-cutting concerns
    ├── logger.py            # Logging setup
    └── exceptions.py        # Custom exceptions
```

Each layer has a specific responsibility:
- **Entry Point**: Wires everything together
- **Configuration**: Manages settings from files and environment
- **Authentication**: Validates tokens and secures endpoints
- **Transport**: Handles gRPC communication
- **Business Logic**: Implements container operations
- **Infrastructure**: Interfaces with Docker
- **Utilities**: Provides common functionality

### CLI Architecture

The refactored CLI follows a similar modular pattern:

```
cli/
├── main.py                  # Application entry point
├── config.py                # Configuration management
├── auth/                    # Authentication layer
│   ├── token_manager.py     # Token loading/saving
│   └── interceptor.py       # gRPC client interceptor
├── client/                  # Transport layer
│   └── grpc_client.py       # gRPC client wrapper
├── commands/                # Command layer
│   ├── base.py              # Base command class
│   ├── container.py         # Container commands
│   ├── exec.py              # Exec command
│   ├── logs.py              # Logs command
│   └── stats.py             # Stats command
├── formatters/              # Presentation layer
│   ├── table.py             # Table formatting
│   └── utils.py             # Formatting utilities
└── utils/                   # Cross-cutting concerns
    └── exceptions.py        # Custom exceptions
```

The CLI follows similar separation principles:
- **Entry Point**: Click CLI setup
- **Configuration**: User settings management
- **Authentication**: Token management and injection
- **Transport**: gRPC communication
- **Commands**: User-facing functionality
- **Formatters**: Output presentation
- **Utilities**: Common functionality

## Detailed Component Explanation

### Agent Components

#### 1. Configuration Management (`agent/config.py`)

The configuration system provides centralized management of all agent settings with support for both configuration files and environment variable overrides.

```python
class AgentConfig:
    """Centralized configuration management for the agent"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.getenv(
            'DOCKYARD_CONFIG',
            '/etc/dockyard/config.yaml'
        )
        self.config = self._load_config()
```

The configuration class loads settings from a YAML file but allows environment variables to take precedence. This follows the Twelve-Factor App methodology where configuration comes from the environment, making it easy to deploy the same code across different environments (development, staging, production) with different settings.

For example, the authentication token is always read from an environment variable for security:

```python
@property
def auth_token(self) -> Optional[str]:
    """Get authentication token from environment"""
    return os.getenv('DOCKYARD_AUTH_TOKEN')
```

This prevents sensitive credentials from being committed to version control. The Docker socket path, server port, and logging settings can all be configured similarly, with sensible defaults:

```python
@property
def docker_socket(self) -> str:
    return os.getenv('DOCKER_SOCKET') or \
           self.config.get('docker', {}).get('socket',
           'unix:///var/run/docker.sock')
```

#### 2. Authentication System

##### Token Validator (`agent/auth/token_validator.py`)

The token validator implements secure token comparison using constant-time algorithms to prevent timing attacks:

```python
class TokenValidator:
    """Validates authentication tokens"""

    def __init__(self):
        self.auth_token = os.getenv('DOCKYARD_AUTH_TOKEN')
        if not self.auth_token:
            raise ValueError(
                "DOCKYARD_AUTH_TOKEN environment variable is required"
            )

    def validate(self, provided_token: str) -> bool:
        """Validate provided token using constant-time comparison"""
        if not provided_token:
            return False
        return secrets.compare_digest(provided_token, self.auth_token)
```

The use of `secrets.compare_digest` is critical for security. A naive string comparison (`provided_token == self.auth_token`) would return False as soon as the first differing character is found, which takes less time than comparing the entire string. An attacker could exploit this timing difference to guess the token character by character. The constant-time comparison always takes the same amount of time regardless of where strings differ, preventing this attack vector.

The validator also includes a token generation helper for initial setup:

```python
@staticmethod
def generate_token() -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)
```

This generates a cryptographically secure 32-byte token encoded in URL-safe base64, providing 256 bits of entropy.

##### gRPC Interceptor (`agent/auth/interceptor.py`)

The server-side interceptor enforces authentication on all incoming requests:

```python
class TokenAuthInterceptor(grpc.ServerInterceptor):
    """gRPC server interceptor for token authentication"""

    def __init__(self, validator: TokenValidator):
        self.validator = validator

    def intercept_service(self, continuation, handler_call_details):
        """Intercept all RPC calls for authentication"""
        # Extract token from metadata
        metadata = dict(handler_call_details.invocation_metadata)
        auth_token = metadata.get('authorization', '')

        # Validate token
        if not self.validator.validate(auth_token):
            context = grpc.ServicerContext()
            context.abort(
                grpc.StatusCode.UNAUTHENTICATED,
                'Invalid or missing authentication token'
            )

        # Token valid, continue with request
        return continuation(handler_call_details)
```

This interceptor runs before every RPC method, extracting the `authorization` metadata field and validating it. If validation fails, the request is immediately rejected with an `UNAUTHENTICATED` status code. If successful, the request continues to the actual RPC handler. This centralized authentication ensures every endpoint is protected without duplicating authentication logic in each method.

#### 3. Service Layer

The service layer encapsulates all business logic, separating it from the transport (gRPC) and infrastructure (Docker SDK) layers.

##### Container Service (`agent/services/container_service.py`)

The container service handles all container lifecycle operations:

```python
class ContainerService:
    """Service for container lifecycle operations"""

    def __init__(self, docker_client):
        self.docker_client = docker_client.client

    def launch_container(
        self,
        image: str,
        name: str,
        config_file: str = None
    ) -> tuple:
        """Launch a container with optional YAML configuration"""
        try:
            # Pull image if not present
            if not self._image_exists(image):
                self.docker_client.images.pull(image)

            # Parse configuration
            container_config = {}
            if config_file:
                with open(config_file, 'r') as f:
                    yaml_config = yaml.safe_load(f)
                    container_config = self._parse_config(yaml_config)

            # Launch container
            container = self.docker_client.containers.run(
                image,
                name=name,
                detach=True,
                **container_config
            )

            return True, f"Container '{name}' launched successfully", \
                   container.short_id

        except Exception as e:
            return False, f"Failed to launch container: {str(e)}", None
```

This method demonstrates several important patterns:

1. **Dependency Injection**: The Docker client is injected via the constructor, making the service testable by allowing mock clients in tests.

2. **Error Handling**: All exceptions are caught and converted to user-friendly error messages with success/failure status.

3. **Return Tuples**: Consistent return signature `(success: bool, message: str, container_id: str)` makes it easy for callers to handle both success and failure cases.

4. **Configuration Parsing**: YAML configuration is parsed and validated before being passed to Docker, providing a safer interface than raw Docker API parameters.

The service also implements container listing with proper formatting:

```python
def list_containers(self, all: bool = False) -> List[Dict[str, str]]:
    """List containers with formatted output"""
    try:
        containers = self.docker_client.containers.list(all=all)
        container_list = []

        for container in containers:
            # Extract and format container metadata
            created_time = container.attrs['Created'][:19].replace('T', ' ')
            port_info = format_ports(container.ports)
            image = container.image.tags[0] if container.image.tags \
                    else container.image.id[:12]

            container_info = {
                'id': container.short_id,
                'image': image,
                'command': truncate_string(command, 30),
                'created': created_time,
                'status': container.status,
                'ports': port_info,
                'names': container.name
            }
            container_list.append(container_info)

        return container_list

    except Exception as e:
        raise ContainerOperationException(
            f"Failed to list containers: {str(e)}"
        )
```

This method transforms raw Docker API responses into clean, structured data suitable for display, handling edge cases like containers without tags and formatting timestamps into human-readable format.

##### Exec Service (`agent/services/exec_service.py`)

The exec service manages command execution inside containers with support for both interactive and non-interactive modes:

```python
class ExecService:
    """Service for container exec operations"""

    def execute_command(
        self,
        container_identifier: str,
        command: List[str],
        interactive: bool = False,
        user: str = None,
        working_dir: str = None,
        environment: dict = None,
        input_iterator = None
    ) -> Iterator[dict]:
        """Execute command in container with streaming output"""
        try:
            container = self.docker_client.containers.get(
                container_identifier
            )

            # Create exec instance
            exec_instance = container.exec_run(
                command,
                stdout=True,
                stderr=True,
                stdin=interactive,
                tty=interactive,
                user=user,
                workdir=working_dir,
                environment=environment,
                detach=False,
                stream=True
            )

            # Stream output
            for chunk in exec_instance.output:
                yield {
                    'stdout': chunk if isinstance(chunk, bytes) else None,
                    'stderr': None,
                    'exit_code': None
                }

            # Send final exit code
            yield {
                'stdout': None,
                'stderr': None,
                'exit_code': exec_instance.exit_code
            }

        except Exception as e:
            yield {
                'stdout': None,
                'stderr': f"Error: {str(e)}".encode(),
                'exit_code': 1
            }
```

The exec service uses Python generators (via `yield`) to stream output as it becomes available, rather than waiting for the entire command to complete. This provides real-time feedback for long-running commands. The final yield includes the exit code, allowing the client to determine if the command succeeded.

##### Logs Service (`agent/services/logs_service.py`)

The logs service provides flexible log retrieval with filtering and streaming:

```python
class LogsService:
    """Service for container logs operations"""

    def get_logs(
        self,
        container_identifier: str,
        follow: bool = False,
        tail: int = None,
        since: str = None,
        timestamps: bool = False,
        stdout: bool = True,
        stderr: bool = True
    ) -> Iterator[bytes]:
        """Get container logs with streaming support"""
        try:
            container = self.docker_client.containers.get(
                container_identifier
            )

            # Parse 'since' parameter
            since_time = self._parse_since(since) if since else None

            # Get logs
            log_stream = container.logs(
                stdout=stdout,
                stderr=stderr,
                stream=follow,
                follow=follow,
                timestamps=timestamps,
                tail=tail if tail else 'all',
                since=since_time
            )

            # Stream logs
            if follow:
                for log_line in log_stream:
                    yield log_line
            else:
                yield log_stream

        except Exception as e:
            yield f"Error: {str(e)}\n".encode()

    def _parse_since(self, since: str):
        """Parse 'since' parameter to datetime"""
        try:
            # Try parsing as duration (e.g., "1h", "30m", "2d")
            if since.endswith('s'):
                seconds = int(since[:-1])
                return datetime.utcnow() - timedelta(seconds=seconds)
            elif since.endswith('m'):
                minutes = int(since[:-1])
                return datetime.utcnow() - timedelta(minutes=minutes)
            elif since.endswith('h'):
                hours = int(since[:-1])
                return datetime.utcnow() - timedelta(hours=hours)
            elif since.endswith('d'):
                days = int(since[:-1])
                return datetime.utcnow() - timedelta(days=days)
            else:
                # Try parsing as ISO timestamp
                return datetime.fromisoformat(since.replace('Z', '+00:00'))
        except Exception:
            return None
```

The logs service handles both streaming (follow mode) and one-shot log retrieval. The `_parse_since` helper parses time specifications in multiple formats (relative durations like "1h" or absolute timestamps), providing a flexible interface similar to `docker logs --since`.

##### Stats Service (`agent/services/stats_service.py`)

The stats service calculates container resource usage metrics:

```python
class StatsService:
    """Service for container statistics monitoring"""

    def get_stats(
        self,
        container_identifiers: List[str],
        stream: bool = False
    ) -> Iterator[dict]:
        """Get resource statistics for containers"""
        try:
            containers = [
                self.docker_client.containers.get(cid)
                for cid in container_identifiers
            ]

            # Previous stats for delta calculations
            prev_stats = {}

            while True:
                stats_list = []

                for container in containers:
                    stats = container.stats(stream=False)

                    # Calculate CPU percentage
                    cpu_percent = self._calculate_cpu_percentage(
                        stats,
                        prev_stats.get(container.id)
                    )

                    # Calculate memory usage
                    mem_usage = stats['memory_stats'].get('usage', 0)
                    mem_limit = stats['memory_stats'].get('limit', 0)
                    mem_percent = (mem_usage / mem_limit * 100) \
                                  if mem_limit > 0 else 0

                    # Calculate network I/O
                    net_input, net_output = self._calculate_network_io(stats)

                    # Calculate block I/O
                    block_read, block_write = self._calculate_block_io(stats)

                    stats_list.append({
                        'container_id': container.short_id,
                        'name': container.name,
                        'cpu_percent': cpu_percent,
                        'mem_usage': mem_usage,
                        'mem_limit': mem_limit,
                        'mem_percent': mem_percent,
                        'net_input': net_input,
                        'net_output': net_output,
                        'block_read': block_read,
                        'block_write': block_write,
                        'pids': stats.get('pids_stats', {}).get('current', 0)
                    })

                    prev_stats[container.id] = stats

                yield {'containers': stats_list}

                if not stream:
                    break

                time.sleep(1)

        except Exception as e:
            yield {'error': str(e)}

    def _calculate_cpu_percentage(
        self,
        stats: dict,
        prev_stats: dict = None
    ) -> float:
        """Calculate CPU usage percentage using delta method"""
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage']

        if prev_stats:
            cpu_delta -= prev_stats['cpu_stats']['cpu_usage']['total_usage']
            system_delta -= prev_stats['cpu_stats']['system_cpu_usage']

        if system_delta > 0:
            num_cpus = len(stats['cpu_stats']['cpu_usage'].get(
                'percpu_usage', [1]
            ))
            cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0
            return round(cpu_percent, 2)

        return 0.0
```

The stats service performs complex calculations to derive meaningful metrics from raw Docker statistics. CPU percentage requires delta calculations between samples to determine actual usage. Network and block I/O are summed across all interfaces/devices. The service supports both streaming (continuous updates) and one-shot modes.

#### 4. gRPC Server Layer

##### Servicer (`agent/grpc_server/servicer.py`)

The servicer wires service layer methods to gRPC RPC methods:

```python
class DockyardServicer(dockyard_pb2_grpc.DockyardServiceServicer):
    """gRPC servicer implementing all RPC methods"""

    def __init__(self, docker_client):
        # Initialize all services
        self.container_service = ContainerService(docker_client)
        self.exec_service = ExecService(docker_client)
        self.logs_service = LogsService(docker_client)
        self.stats_service = StatsService(docker_client)

    def LaunchContainer(self, request, context):
        """Launch container RPC handler"""
        success, message, container_id = \
            self.container_service.launch_container(
                image=request.image,
                name=request.name,
                config_file=request.config_file if request.config_file else None
            )

        return dockyard_pb2.LaunchResponse(
            success=success,
            message=message,
            container_id=container_id or ''
        )

    def GetLogs(self, request, context):
        """Get logs RPC handler with streaming"""
        try:
            for log_data in self.logs_service.get_logs(
                container_identifier=request.container_identifier,
                follow=request.follow,
                tail=request.tail if request.tail > 0 else None,
                since=request.since if request.since else None,
                timestamps=request.timestamps,
                stdout=request.stdout,
                stderr=request.stderr
            ):
                yield dockyard_pb2.LogsResponse(
                    log=dockyard_pb2.LogEntry(
                        data=log_data,
                        stream_type="stdout"
                    )
                )

            # Send finished status for non-follow mode
            if not request.follow:
                yield dockyard_pb2.LogsResponse(
                    status=dockyard_pb2.LogsStatus(
                        success=True,
                        message="Logs completed",
                        finished=True
                    )
                )

        except Exception as e:
            yield dockyard_pb2.LogsResponse(
                status=dockyard_pb2.LogsStatus(
                    success=False,
                    message=f"Error: {str(e)}",
                    finished=True
                )
            )
```

The servicer is a thin translation layer between gRPC protobuf messages and service layer methods. It extracts parameters from request messages, calls service methods, and packages responses into protobuf messages. This separation means the business logic in services is completely independent of gRPC and could be reused with a different transport (HTTP REST, message queue, etc.).

##### Server (`agent/grpc_server/server.py`)

The server class manages gRPC server lifecycle:

```python
class DockyardServer:
    """gRPC server for Dockyard agent"""

    def __init__(self, docker_client, config: AgentConfig):
        self.docker_client = docker_client
        self.config = config
        self.server = None

    def start(self):
        """Start the gRPC server with authentication"""
        # Create servicer
        servicer = DockyardServicer(self.docker_client)

        # Create authentication interceptor
        validator = TokenValidator()
        interceptor = TokenAuthInterceptor(validator)

        # Create server with interceptor
        self.server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=10),
            interceptors=(interceptor,)
        )

        # Register servicer
        dockyard_pb2_grpc.add_DockyardServiceServicer_to_server(
            servicer,
            self.server
        )

        # Bind port
        port = self.config.server_port
        self.server.add_insecure_port(f'[::]:{port}')

        # Start server
        self.server.start()
        logger.info(f"Server started on port {port}")

    def wait_for_termination(self):
        """Wait for server termination"""
        if self.server:
            self.server.wait_for_termination()

    def stop(self, grace_period=5):
        """Stop the server gracefully"""
        if self.server:
            self.server.stop(grace_period)
```

The server manages the complete lifecycle: initialization with authentication, starting the server, waiting for termination, and graceful shutdown. The authentication interceptor is registered during server creation, ensuring it processes every request.

#### 5. Entry Point (`agent/main.py`)

The main entry point ties all components together:

```python
def main():
    """Main entry point for Dockyard agent"""
    # Load configuration
    config = AgentConfig()

    # Setup logging
    logger = setup_logger(
        name='dockyard',
        log_file=config.log_file,
        log_level=config.log_level,
        max_bytes=config.log_max_bytes,
        backup_count=config.log_backup_count
    )

    logger.info("=" * 60)
    logger.info("Dockyard Agent Starting...")
    logger.info("=" * 60)

    try:
        # Initialize Docker client
        docker_client = DockerClientWrapper(
            socket=config.docker_socket,
            timeout=config.docker_timeout
        )

        # Verify Docker connection
        if not docker_client.health_check():
            logger.error("Docker connection failed")
            sys.exit(1)

        logger.info("Docker connection established")

        # Create and start server
        server = DockyardServer(docker_client, config)
        server.start()

        logger.info("Agent is ready to accept requests")
        logger.info(f"Listening on 0.0.0.0:{config.server_port}")

        # Wait for termination
        server.wait_for_termination()

    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        server.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
```

The entry point follows the initialization pattern: load configuration, setup logging, initialize dependencies (Docker client), create the server, and start it. Proper error handling ensures clean shutdown on interrupts and informative error messages on failures.

### CLI Components

#### 1. Configuration Management (`cli/config.py`)

Similar to the agent, the CLI has centralized configuration:

```python
class CLIConfig:
    """Configuration management for CLI"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(
            os.path.expanduser('~'),
            '.dockyard',
            'config.yaml'
        )
        self.config = self._load_config()

    @property
    def auth_token(self) -> Optional[str]:
        """Get authentication token (priority: ENV > config file)"""
        return os.getenv('DOCKYARD_AUTH_TOKEN') or \
               self.config.get('auth', {}).get('token')

    @property
    def default_host(self) -> str:
        return os.getenv('DOCKYARD_HOST') or \
               self.config.get('agent', {}).get('host', 'localhost')

    @property
    def default_port(self) -> int:
        return int(os.getenv('DOCKYARD_PORT') or \
                  self.config.get('agent', {}).get('port', 50051))
```

The CLI configuration prioritizes environment variables over file-based config, allowing users to override settings per-command without modifying files.

#### 2. Authentication System

##### Token Manager (`cli/auth/token_manager.py`)

The token manager handles loading and saving authentication tokens:

```python
class TokenManager:
    """Manages authentication tokens for CLI"""

    def __init__(self, config: CLIConfig):
        self.config = config
        self._token = None

    def load_token(self) -> Optional[str]:
        """Load token from environment or config file"""
        if self._token:
            return self._token

        # Priority 1: Environment variable
        token = os.getenv('DOCKYARD_AUTH_TOKEN')
        if token:
            self._token = token
            return token

        # Priority 2: Config file
        token = self.config.auth_token
        if token:
            self._token = token
            return token

        return None

    def save_token(self, token: str):
        """Save token to config file"""
        config_dir = os.path.dirname(self.config.config_path)
        os.makedirs(config_dir, exist_ok=True)

        # Update config
        self.config.config.setdefault('auth', {})['token'] = token

        # Write to file with secure permissions
        with open(self.config.config_path, 'w') as f:
            yaml.dump(self.config.config, f)

        # Set file permissions to 0600 (owner read/write only)
        os.chmod(self.config.config_path, 0o600)

        self._token = token
```

The token manager provides a clean interface for token access with proper security: tokens saved to disk have restrictive permissions (0600) to prevent other users from reading them.

##### gRPC Client Interceptor (`cli/auth/interceptor.py`)

The client-side interceptor automatically adds authentication to all requests:

```python
class TokenAuthClientInterceptor(
    grpc.UnaryUnaryClientInterceptor,
    grpc.UnaryStreamClientInterceptor,
    grpc.StreamUnaryClientInterceptor,
    grpc.StreamStreamClientInterceptor
):
    """gRPC client interceptor for token authentication"""

    def __init__(self, token_manager: TokenManager):
        self.token_manager = token_manager

    def _add_auth_metadata(self, client_call_details):
        """Add authentication token to request metadata"""
        token = self.token_manager.load_token()
        if not token:
            raise AuthenticationException(
                "No authentication token found. "
                "Set DOCKYARD_AUTH_TOKEN environment variable."
            )

        # Create metadata with auth token
        metadata = []
        if client_call_details.metadata:
            metadata = list(client_call_details.metadata)
        metadata.append(('authorization', token))

        # Create new call details with auth metadata
        return grpc._interceptor._ClientCallDetails(
            client_call_details.method,
            client_call_details.timeout,
            metadata,
            client_call_details.credentials,
            client_call_details.wait_for_ready,
            client_call_details.compression
        )

    def intercept_unary_unary(self, continuation, client_call_details, request):
        """Intercept unary-unary RPCs"""
        new_details = self._add_auth_metadata(client_call_details)
        return continuation(new_details, request)

    def intercept_unary_stream(self, continuation, client_call_details, request):
        """Intercept unary-stream RPCs"""
        new_details = self._add_auth_metadata(client_call_details)
        return continuation(new_details, request)
```

The interceptor implements all four gRPC call types (unary-unary, unary-stream, stream-unary, stream-stream) to handle authentication transparently across all RPC methods. Commands don't need to know about authentication; it's handled automatically.

#### 3. Command Layer

##### Base Command (`cli/commands/base.py`)

The base command provides common functionality for all commands:

```python
class BaseCommand:
    """Base class for all CLI commands"""

    def __init__(self, client):
        self.client = client

    def handle_error(self, error: Exception):
        """Handle command errors consistently"""
        if isinstance(error, grpc.RpcError):
            if error.code() == grpc.StatusCode.UNAUTHENTICATED:
                click.echo(
                    "Authentication failed. Check your token.",
                    err=True
                )
            elif error.code() == grpc.StatusCode.UNAVAILABLE:
                click.echo(
                    "Cannot connect to agent. Check host and port.",
                    err=True
                )
            else:
                click.echo(f"Error: {error.details()}", err=True)
        else:
            click.echo(f"Error: {str(error)}", err=True)

        sys.exit(1)
```

The base command centralizes error handling, providing consistent, user-friendly error messages for common failure scenarios like authentication failures or connection issues.

##### Container Commands (`cli/commands/container.py`)

Container commands implement user-facing operations:

```python
class ContainerCommands(BaseCommand):
    """Container management commands"""

    def launch(self, image, name, config_file=None):
        """Launch a container"""
        try:
            click.echo(f"Launching container '{name}' from image '{image}'...")

            request = dockyard_pb2.LaunchRequest(
                image=image,
                name=name,
                config_file=config_file or ''
            )

            response = self.client.stub.LaunchContainer(request)

            if response.success:
                click.echo(f"Success: {response.message}")
                click.echo(f"Container ID: {response.container_id}")
            else:
                click.echo(f"Failed: {response.message}", err=True)
                sys.exit(1)

        except Exception as e:
            self.handle_error(e)

    def ps(self, all=False):
        """List containers"""
        try:
            request = dockyard_pb2.ListContainersRequest(all=all)
            response = self.client.stub.ListContainers(request)

            if not response.success:
                click.echo(f"Error: {response.message}", err=True)
                sys.exit(1)

            if not response.containers:
                click.echo("No containers found")
                return

            # Format as table
            headers = [
                'CONTAINER ID', 'IMAGE', 'COMMAND', 'CREATED',
                'STATUS', 'PORTS', 'NAMES'
            ]
            rows = [
                [
                    c.id, c.image, c.command, c.created,
                    c.status, c.ports, c.names
                ]
                for c in response.containers
            ]

            print_table(headers, rows)

        except Exception as e:
            self.handle_error(e)
```

Commands focus on user experience: informative messages, proper error handling, and clean output formatting. They translate user intent (CLI arguments) into RPC requests and responses into user-friendly output.

#### 4. Formatters (`cli/formatters/table.py`)

Formatters handle output presentation:

```python
def print_table(headers: List[str], rows: List[List[str]]):
    """Print data as formatted table"""
    if not rows:
        return

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Print header
    header_line = ' '.join(
        h.ljust(col_widths[i]) for i, h in enumerate(headers)
    )
    click.echo(header_line)
    click.echo('-' * len(header_line))

    # Print rows
    for row in rows:
        row_line = ' '.join(
            str(cell).ljust(col_widths[i])
            for i, cell in enumerate(row)
        )
        click.echo(row_line)
```

The table formatter calculates optimal column widths and aligns data for readable output. Utility formatters handle human-readable byte sizes and other formatting needs:

```python
def format_bytes(bytes_value: int) -> str:
    """Format bytes as human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f}{unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f}PB"
```

## Security Considerations

### Token-Based Authentication

The authentication system implements several security best practices:

1. **Environment Variables**: Tokens are stored in environment variables, never in code or version control.

2. **Constant-Time Comparison**: Uses `secrets.compare_digest()` to prevent timing attacks.

3. **Strong Token Generation**: 256-bit cryptographically secure random tokens.

4. **File Permissions**: Config files containing tokens have 0600 permissions (owner read/write only).

5. **Transport Security**: While this lab uses insecure gRPC for simplicity, production deployments should use TLS encryption.

### Best Practices

1. **Rotate Tokens Regularly**: Generate new tokens periodically.

2. **Secure Token Storage**: Keep tokens in secure secret management systems (HashiCorp Vault, AWS Secrets Manager, etc.) in production.

3. **Network Security**: Deploy agents behind firewalls, use VPNs or TLS.

4. **Principle of Least Privilege**: Use separate tokens for different clients with different permissions (future enhancement).

## Testing the Refactored System

### 1. Setup EC2 Instance

```bash
# Export EC2 IP
export EC2_IP=<your-ec2-ip>

# Connect to EC2
ssh -i key.pem ubuntu@$EC2_IP

# Update and install dependencies
sudo apt update
sudo apt install -y docker.io python3-venv python3-pip

# Start Docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ubuntu

# Logout and login again for group changes
exit
ssh -i key.pem ubuntu@$EC2_IP
```

### 2. Deploy Agent

```bash
# On EC2: Create project directory
mkdir -p ~/dockyard
cd ~/dockyard
```

```bash
# On local: Package and upload agent (includes protobuf files)
tar czf agent_deploy.tar.gz agent/ dockyard_pb2.py dockyard_pb2_grpc.py
scp -i key.pem agent_deploy.tar.gz ubuntu@$EC2_IP:~/dockyard/

# Alternatively, upload files separately
scp -i key.pem -r agent/ ubuntu@$EC2_IP:~/dockyard/
scp -i key.pem dockyard_pb2.py dockyard_pb2_grpc.py ubuntu@$EC2_IP:~/dockyard/
```

```bash
# On EC2: Extract and setup
cd ~/dockyard
tar xzf agent_deploy.tar.gz

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install grpcio grpcio-tools docker pyyaml

# Generate authentication token
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Example output: QHyhDmjnMrxCUNVXglxLO1nlxSEgujry6EgzcvLWyO4

# Set environment variables
export DOCKYARD_AUTH_TOKEN=<your-generated-token>
export PYTHONPATH=/home/ubuntu/dockyard

# Start agent
python3 -m agent.main

# Or run in background
nohup python3 -m agent.main > agent.log 2>&1 &
```

### 3. Configure Local CLI

```bash
# On local: Set authentication token
export DOCKYARD_AUTH_TOKEN=<your-generated-token>
export PYTHONPATH=$(pwd)

# Test connection
python3 cli/main.py --host $EC2_IP --port 50051 ps
```

### 4. Test All Commands

```bash
# Launch container
python3 cli/main.py --host $EC2_IP --port 50051 \
  launch nginx --name test-nginx

# List containers
python3 cli/main.py --host $EC2_IP --port 50051 ps

# Inspect container
python3 cli/main.py --host $EC2_IP --port 50051 \
  inspect test-nginx

# Get logs
python3 cli/main.py --host $EC2_IP --port 50051 \
  logs test-nginx --tail 10

# Execute command
python3 cli/main.py --host $EC2_IP --port 50051 \
  exec test-nginx -- ls /usr/share/nginx/html

# Get stats
python3 cli/main.py --host $EC2_IP --port 50051 \
  stats --no-stream test-nginx

# Stop container
python3 cli/main.py --host $EC2_IP --port 50051 \
  stop test-nginx

# Remove container
python3 cli/main.py --host $EC2_IP --port 50051 \
  rm test-nginx
```

### 5. Test Authentication

```bash
# Test without token (should fail)
unset DOCKYARD_AUTH_TOKEN
python3 cli/main.py --host $EC2_IP --port 50051 ps
# Expected: Authentication failed error

# Test with wrong token (should fail)
export DOCKYARD_AUTH_TOKEN=invalid-token
python3 cli/main.py --host $EC2_IP --port 50051 ps
# Expected: Authentication failed error

# Test with correct token (should succeed)
export DOCKYARD_AUTH_TOKEN=<your-generated-token>
python3 cli/main.py --host $EC2_IP --port 50051 ps
# Expected: Container list or "No containers found"
```

## Troubleshooting

### ModuleNotFoundError: No module named 'dockyard_pb2'

If you encounter this error when running the agent or CLI, it means the protobuf files are missing.

**Root Cause:**
The `dockyard_pb2.py` and `dockyard_pb2_grpc.py` files are generated from the proto definition and are required for both the agent and CLI to function.

**Solution:**

Generate the protobuf files from the proto definition:

```bash
# From the dockyard project root directory
python3 -m grpc_tools.protoc \
  -I./proto \
  --python_out=. \
  --grpc_python_out=. \
  proto/dockyard.proto

# Verify the files were created
ls -la dockyard_pb2*.py
```

This creates two files:
- `dockyard_pb2.py` - Message definitions (requests, responses, data structures)
- `dockyard_pb2_grpc.py` - Service definitions (RPC methods, client/server stubs)

**On EC2:**

If you encounter this error on EC2, ensure the protobuf files are included in your deployment:

```bash
# Option 1: Include in tarball (recommended)
tar czf agent_deploy.tar.gz agent/ dockyard_pb2.py dockyard_pb2_grpc.py
scp -i key.pem agent_deploy.tar.gz ubuntu@$EC2_IP:~/dockyard/

# Option 2: Upload separately
scp -i key.pem dockyard_pb2.py dockyard_pb2_grpc.py ubuntu@$EC2_IP:~/dockyard/
```

### PYTHONPATH Not Set

If imports fail with `ModuleNotFoundError: No module named 'agent'`, ensure PYTHONPATH is set:

```bash
# On EC2
export PYTHONPATH=/home/ubuntu/dockyard

# On local
export PYTHONPATH=$(pwd)
```

### Authentication Errors

**Error:** `UNAUTHENTICATED: Invalid or missing authentication token`

**Solution:** Ensure the `DOCKYARD_AUTH_TOKEN` environment variable is set on both agent and CLI:

```bash
# Check if token is set
echo $DOCKYARD_AUTH_TOKEN

# Set token if missing
export DOCKYARD_AUTH_TOKEN=<your-token>
```

### Permission Denied: /var/log/dockyard

**Warning:** `Failed to setup file logging: [Errno 13] Permission denied: '/var/log/dockyard'`

This is a harmless warning. The agent will continue to log to console. To fix:

```bash
# On EC2
sudo mkdir -p /var/log/dockyard
sudo chown ubuntu:ubuntu /var/log/dockyard
```

## Comparing Old vs New Architecture

### Before Refactoring (Labs 01-05)

**agent/main.py** - 900+ lines containing:
- Docker client initialization
- All container operations (launch, stop, list, inspect, remove)
- All exec logic with streaming
- All logs logic with filtering
- All stats calculations
- gRPC server setup
- gRPC servicer implementation
- No authentication
- Mixed concerns (business logic, transport, infrastructure)

**cli/main.py** - 800+ lines containing:
- All CLI commands
- gRPC client setup
- Formatting logic
- Output handling
- No authentication
- Mixed concerns (commands, formatting, networking)

### After Refactoring (Lab 06)

**Agent**: 20 files organized by concern:
- `agent/main.py` - 80 lines: Application entry point
- `agent/config.py` - 100 lines: Configuration management
- `agent/auth/` - 2 files, 150 lines: Authentication logic
- `agent/grpc_server/` - 2 files, 350 lines: Transport layer
- `agent/services/` - 4 files, 600 lines: Business logic
- `agent/docker_client/` - 2 files, 100 lines: Infrastructure
- `agent/utils/` - 2 files, 120 lines: Common utilities

**CLI**: 17 files organized by concern:
- `cli/main.py` - 150 lines: Application entry point
- `cli/config.py` - 80 lines: Configuration management
- `cli/auth/` - 2 files, 120 lines: Authentication logic
- `cli/client/` - 1 file, 80 lines: Transport layer
- `cli/commands/` - 5 files, 500 lines: Command implementations
- `cli/formatters/` - 2 files, 150 lines: Output formatting
- `cli/utils/` - 1 file, 50 lines: Common utilities

### Benefits of Refactoring

1. **Maintainability**: Each file has a single, clear responsibility. Finding and fixing bugs is much easier.

2. **Testability**: Services can be unit tested with mock dependencies. Before, testing required a running Docker daemon.

3. **Reusability**: Service layer can be reused with different transports (HTTP, message queue, etc.).

4. **Extensibility**: Adding new operations means creating new service methods, not modifying 900-line files.

5. **Security**: Centralized authentication in interceptors ensures every endpoint is protected.

6. **Team Development**: Multiple developers can work on different modules without conflicts.

7. **Code Quality**: Smaller files are easier to review and understand.

## Key Takeaways

1. **Separation of Concerns**: Different aspects (business logic, transport, authentication) belong in different modules.

2. **Service Layer Pattern**: Isolating business logic from infrastructure makes code testable and reusable.

3. **Dependency Injection**: Passing dependencies to constructors enables mocking for tests.

4. **gRPC Interceptors**: Centralized cross-cutting concerns (authentication, logging) without duplicating code.

5. **Configuration Management**: Environment variables override file config, enabling flexible deployment.

6. **Security by Design**: Authentication built into the architecture from the start, not bolted on later.

7. **Clean Architecture**: Inner layers (services) don't depend on outer layers (transport), maintaining flexibility.

## Conclusion

Lab 06 transforms Dockyard from a working prototype into a production-ready system. The refactored architecture provides a solid foundation for future growth, while the authentication system protects your infrastructure. The modular design makes the codebase maintainable and testable, setting the stage for scaling to a larger team and more complex requirements.

You've now completed the journey from a basic gRPC service (Lab 01) through feature additions (Labs 02-05) to a professionally architected system (Lab 06). Congratulations!
