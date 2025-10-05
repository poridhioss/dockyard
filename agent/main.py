#!/usr/bin/env python3
"""
Dockyard Agent - Main entry point
Refactored version with modular architecture
"""
import signal
import sys

from agent.config import AgentConfig
from agent.utils.logger import setup_logger
from agent.docker_client.client import DockerClientWrapper
from agent.grpc_server.server import DockyardServer


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    """Main entry point"""
    global logger

    try:
        # Load configuration
        config = AgentConfig()

        # Setup logging
        logger = setup_logger(
            name='dockyard',
            log_file=config.log_file,
            log_level=config.log_level,
            max_bytes=config.log_max_size,
            backup_count=config.log_backup_count
        )

        logger.info("="*60)
        logger.info("Dockyard Agent Starting...")
        logger.info("="*60)

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Initialize Docker client
        docker_client = DockerClientWrapper(
            socket=config.docker_socket,
            timeout=config.docker_timeout
        )

        # Initialize and start gRPC server
        server = DockyardServer(docker_client, config)
        server.start()

        logger.info("Agent is ready to accept requests")
        logger.info(f"Listening on {config.server_host}:{config.server_port}")

        # Wait for termination
        server.wait_for_termination()

    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Agent shutdown complete")


if __name__ == '__main__':
    main()
