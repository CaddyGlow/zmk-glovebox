"""Docker configuration builder for CLI commands."""

import logging
from pathlib import Path

from glovebox.config.compile_methods import DockerUserConfig


logger = logging.getLogger(__name__)


class DockerConfigBuilder:
    """Builder for Docker user configuration."""

    @staticmethod
    def build_from_params(
        strategy: str,
        docker_uid: int | None = None,
        docker_gid: int | None = None,
        docker_username: str | None = None,
        docker_home: str | None = None,
        docker_container_home: str | None = None,
        no_docker_user_mapping: bool = False,
    ) -> DockerUserConfig:
        """Build Docker user configuration from parameters.

        Args:
            strategy: Compilation strategy name
            docker_uid: Manual UID override
            docker_gid: Manual GID override
            docker_username: Manual username override
            docker_home: Host home directory
            docker_container_home: Container home directory
            no_docker_user_mapping: Disable user mapping

        Returns:
            Docker user configuration
        """
        # Start with strategy-specific defaults
        if strategy == "moergo":
            # Moergo disables user mapping by default
            config = DockerUserConfig(enable_user_mapping=False)
            logger.debug("Using Moergo docker defaults: enable_user_mapping=False")
        else:
            # Standard strategies enable user mapping
            config = DockerUserConfig(enable_user_mapping=True)
            logger.debug("Using standard docker defaults: enable_user_mapping=True")

        # Apply overrides
        if docker_uid is not None:
            config.manual_uid = docker_uid
            logger.debug("Override: manual_uid=%s", docker_uid)

        if docker_gid is not None:
            config.manual_gid = docker_gid
            logger.debug("Override: manual_gid=%s", docker_gid)

        if docker_username is not None:
            config.manual_username = docker_username
            logger.debug("Override: manual_username=%s", docker_username)

        if docker_home is not None:
            config.host_home_dir = Path(docker_home)
            logger.debug("Override: host_home_dir=%s", docker_home)

        if docker_container_home is not None:
            config.container_home_dir = docker_container_home
            logger.debug("Override: container_home_dir=%s", docker_container_home)

        if no_docker_user_mapping:
            config.enable_user_mapping = False
            logger.debug(
                "Override: enable_user_mapping=False (--no-docker-user-mapping)"
            )

        logger.debug("Final docker_user_config: %r", config)
        return config
