# Lab 02: Container Stop Examples

This directory contains examples and test scripts for Lab 02's container stop functionality.

## Files

- `app.yaml` - Sample YAML configuration for testing
- `test-stop-commands.sh` - Comprehensive test script demonstrating all stop features
- `README.md` - This documentation

## Features Tested

### Basic Stop Commands
```bash
# Stop single container by name
dockyard stop web-server

# Stop single container by ID
dockyard stop 1234567890ab

# Stop multiple containers
dockyard stop web-server cache nginx-app
```

### Force Stop
```bash
# Force kill container (immediate termination)
dockyard stop --force web-server
dockyard stop -f web-server
```

### Custom Timeout
```bash
# Set custom graceful stop timeout (default: 10s)
dockyard stop --timeout 30 web-server
dockyard stop -t 5 web-server
```

### Batch Operations
```bash
# Stop all containers (conceptual - requires ps command)
# dockyard stop $(dockyard ps -q)

# Stop specific set of containers
dockyard stop nginx redis mongodb
```

## Error Handling

The implementation handles these error cases:

1. **Container not found** - Clear error message
2. **Already stopped container** - Success with informative message
3. **Network/connection errors** - Connection failure messages
4. **Docker daemon errors** - API error handling

## Usage Examples

### Launch and Stop Workflow
```bash
# 1. Launch containers
dockyard launch nginx:alpine --name web-server
dockyard launch redis:alpine --name cache

# 2. Stop gracefully
dockyard stop web-server

# 3. Force stop if needed
dockyard stop --force cache
```

### Testing Script
```bash
# Run comprehensive tests
chmod +x labs/lab2-stop/test-stop-commands.sh
./labs/lab2-stop/test-stop-commands.sh
```

## Command Reference

```
Usage: dockyard stop [OPTIONS] CONTAINERS...

  Stop one or more containers

Options:
  -f, --force     Force stop (kill instead of graceful stop)
  -t, --timeout   Timeout in seconds for graceful stop (default: 10)
  --help          Show this message and exit.
```

## Learning Objectives

- **Container Lifecycle Management**: Understanding stop vs kill operations
- **Batch Operations**: Handling multiple containers efficiently
- **Error Recovery**: Proper error handling and user feedback
- **State Management**: Dealing with container state transitions
- **User Experience**: Clear command syntax and helpful error messages