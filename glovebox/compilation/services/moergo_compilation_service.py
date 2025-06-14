"""Moergo compilation service for ZMK firmware builds."""

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.compilation.services.base_compilation_service import (
    BaseCompilationService,
)
from glovebox.config.compile_methods import MoergoCompilationConfig
from glovebox.config.models.keyboard import CompileMethodConfigUnion
from glovebox.core.errors import BuildError


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class MoergoCompilationService(BaseCompilationService):
    """Moergo compilation service for ZMK firmware builds.

    Implements a simplified Docker-based build strategy that mounts
    config and keymap files to a temporary Docker volume without caching.
    """

    def __init__(
        self,
        config: CompileMethodConfigUnion | None = None,
        **base_kwargs: Any,
    ) -> None:
        """Initialize Moergo compilation service.

        Args:
            config: Moergo compilation configuration
            **base_kwargs: Arguments passed to BaseCompilationService
        """
        super().__init__("moergo_compilation", "1.0.0", **base_kwargs)

    def _setup_workspace(
        self,
        keymap_file: Path,
        config_file: Path,
        config: CompileMethodConfigUnion,
        keyboard_profile: "KeyboardProfile",
    ) -> Path | None:
        """Setup temporary workspace for Moergo compilation.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            config: Moergo compilation configuration
            keyboard_profile: Keyboard profile (unused in Moergo strategy)

        Returns:
            Path | None: Temporary workspace path if successful, None if failed
        """
        try:
            if not isinstance(config, MoergoCompilationConfig):
                raise BuildError("Invalid compilation configuration")

            # Create temporary directory for build files
            temp_dir = Path(tempfile.mkdtemp(prefix="moergo-build-"))
            self.logger.debug("Created temporary workspace: %s", temp_dir)

            # Create nested config directory structure as expected by Moergo container
            # Container expects: /workspace/config/ (where our files go)
            workspace_path = temp_dir / "config"
            config_path = workspace_path
            config_path.mkdir(parents=True, exist_ok=True)

            # Copy keymap and config files to the nested config directory
            temp_keymap = config_path / "glove80.keymap"
            temp_config = config_path / "glove80.conf"

            temp_keymap.write_text(keymap_file.read_text())
            temp_config.write_text(config_file.read_text())

            # Create the required default.nix file for Nix build in the nested config directory
            #             default_nix_content = """{ pkgs ?  import <nixpkgs> {}
            # , firmware ? import /src {}
            # }:
            #
            # let
            #   config = ./.;
            #
            #   glove80_left  = firmware.zmk.override { board = "glove80_lh"; keymap = "${config}/glove80.keymap"; kconfig = "${config}/glove80.conf"; };
            #   glove80_right = firmware.zmk.override { board = "glove80_rh"; keymap = "${config}/glove80.keymap"; kconfig = "${config}/glove80.conf"; };
            #
            # in firmware.combine_uf2 glove80_left glove80_right"""

            default_nix_content = """{
              pkgs ? (import <moergo-zmk/nix/pinned-nixpkgs.nix> { }),
              moergo ? (import <moergo-zmk> { }),
              zmk ? moergo.zmk,
            }:
            let
              config = ./.;
              keymap = "${config}/glove80.keymap";
              kconfig = "${config}/glove80.conf";
              outputName = "glove80";

              customZmk = zmk.overrideAttrs (oldAttrs: {
                installPhase = ''
                  ${oldAttrs.installPhase}

                  cp  zephyr/include/generated/devicetree_generated.h "$out/";
                '';
              });

              combine =
                a: b: name:
                pkgs.runCommandNoCC "combined_firmware" { } ''
                  mkdir -p $out
                    echo "cat ${a}/zmk.uf2 ${b}/zmk.uf2 > $out/${name}.uf2"
                    cat ${a}/zmk.uf2 ${b}/zmk.uf2 > $out/${name}.uf2
                '';

              collect_build_artifact =
                board_type: artifact:
                let
                  result = pkgs.runCommandNoCC "collect_build_artifact_${board_type}" { } ''
                    # Copy build files
                    echo "Copying build files from ${artifact} to $out"
                    cp -rT ${artifact} $out
                  '';
                in
                result;

              glove80_left = customZmk.override {
                board = "glove80_lh";
                keymap = "${keymap}";
                kconfig = "${kconfig}";
              };
              left_processed = collect_build_artifact "lh" glove80_left;
              glove80_right = customZmk.override {
                board = "glove80_rh";
                keymap = "${keymap}";
                kconfig = "${kconfig}";
              };
              right_processed = collect_build_artifact "rh" glove80_right;

              # combined = moergo.combine_uf2 glove80_left glove80_right ${outputName};
              combined = combine left_processed right_processed "${outputName}";

            in
            pkgs.runCommand "${outputName}-firmware" { } ''
                  set +x
                echo "finishing $out"
                mkdir -p $out

                # Copy firmware directories
                cp -r ${left_processed} $out/lf
                cp -r ${right_processed} $out/rh

                cp ${combined}/${outputName}.uf2 $out/${outputName}.uf2

                # mkdir -p $artifactDir
                # cp -rT $out $artifactDir
                # Add build metadata
                # "buildId": "{buildId}",
              cat > $out/build-info.json <<EOF
                  {
                    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
                    "keymap": "${keymap}",
                    "kconfig": "${kconfig}",
                    "outputFile": "${outputName}.uf2"
                  }
              EOF
            ''
            """
            default_nix_file = config_path / "default.nix"
            default_nix_file.write_text(default_nix_content)

            # Update the build_root in config to point to our temp directory
            config.workspace_path.host_path = temp_dir

            self.logger.debug(
                "Copied files to temp workspace: %s, %s", temp_keymap, temp_config
            )

            return temp_dir

        except Exception as e:
            self._handle_workspace_setup_error("Moergo", e)
            return None

    def _build_compilation_command(
        self, workspace_path: Path, config: CompileMethodConfigUnion
    ) -> list[str]:
        """Build compilation command for Moergo strategy.

        The Moergo Docker container runs the build automatically when started.
        We just need to wait for it to complete and show the results.

        Args:
            workspace_path: Path to temporary workspace directory
            config: Moergo compilation configuration

        Returns:
            list[str]: Command array to wait for build completion and show results
        """
        if not isinstance(config, MoergoCompilationConfig):
            raise BuildError("Invalid compilation configuration")

        # nix_build = f'nix-build "//default.nix" \
        # --argstr keymap "${config.c}/$KEYMAP" \
        # --argstr kconfig "${BUILD_DIR}/$KCONFIG" \
        # --argstr outputName "$OUTPUT_NAME" \
        # --argstr buildId "$BUILD_ID" \
        # "$NIX_ARGS" -j"$NPROC" -o result 2>&1 | tee -a "$BUILD_LOG"i'

        # The Moergo container runs build automatically on startup
        # First create git config to fix ownership issue, then run the entrypoint
        # Return as list for proper argument handling with entrypoint
        return [
            "-c",
            # "chown -R 0:0 /workspace && /bin/entrypoint.shl",
            # "chowm -R $UID:$GID /workspace",
            """chown -R 0:0 /workspace
/bin/entrypoint.sh
chown -R $UID:$GID /workspace""",
        ]

    def _validate_strategy_specific(self, config: CompileMethodConfigUnion) -> bool:
        """Validate Moergo strategy-specific configuration requirements.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if strategy-specific requirements are met
        """
        if not isinstance(config, MoergoCompilationConfig):
            self.logger.error("Invalid configuration type for Moergo strategy")
            return False

        # Moergo strategy specific validation
        if not config.branch:
            self.logger.error("Branch is required for Moergo compilation")
            return False

        return True

    def _prepare_build_volumes(
        self,
        workspace_path: Path,
        config: CompileMethodConfigUnion,
    ) -> list[tuple[str, str]]:
        """Prepare Docker volumes for Moergo compilation.

        Args:
            workspace_path: Path to workspace directory
            config: Compilation configuration

        Returns:
            list[tuple[str, str]]: Docker volumes for compilation
        """
        if not isinstance(config, MoergoCompilationConfig):
            raise BuildError("Invalid compilation configuration")

        volumes = []

        if config.workspace_path.host_path:
            volumes.append(config.workspace_path.vol())

        self.logger.debug("Prepared %d Docker volumes for Moergo build", len(volumes))
        return volumes

    def _prepare_build_environment(
        self, config: CompileMethodConfigUnion
    ) -> dict[str, str]:
        """Prepare build environment variables for Moergo compilation.

        Args:
            config: Moergo compilation configuration

        Returns:
            dict[str, str]: Environment variables for build
        """
        if not isinstance(config, MoergoCompilationConfig):
            raise BuildError("Invalid compilation configuration")

        # Start with base environment
        build_env = super()._prepare_build_environment(config)

        # Add Moergo-specific environment variables
        if config.branch:
            build_env["BRANCH"] = config.branch
        if config.repository:
            build_env["REPO"] = config.repository

        # Set user context for file ownership (Moergo container expects UID/GID)
        # Note: The container needs to run as root to access git repos, but uses UID/GID for output file ownership
        import os

        build_env["UID"] = str(os.getuid())
        build_env["GID"] = str(os.getgid())

        self.logger.debug("Prepared Moergo build environment: %s", build_env)
        return build_env

    # def _cleanup_workspace(self, workspace_path: Path) -> None:
    #     """Clean up temporary workspace after compilation.
    #
    #     Args:
    #         workspace_path: Path to temporary workspace to clean up
    #     """
    #     if not isinstance(config, MoergoCompilationConfig):
    #         raise BuildError("Invalid compilation configuration")
    #
    #     if self.moergo_config.cleanup_workspace and workspace_path.exists():
    #         try:
    #             import shutil
    #
    #             shutil.rmtree(workspace_path)
    #             self.logger.debug("Cleaned up temporary workspace: %s", workspace_path)
    #         except Exception as e:
    #             self.logger.warning(
    #                 "Failed to clean up workspace %s: %s", workspace_path, e
    #             )


def create_moergo_service(
    config: CompileMethodConfigUnion | None = None,
    **base_kwargs: Any,
) -> MoergoCompilationService:
    """Create Moergo compilation service.

    Args:
        config: Moergo compilation configuration
        **base_kwargs: Arguments passed to BaseCompilationService

    Returns:
        MoergoCompilationService: Configured service instance
    """
    return MoergoCompilationService(
        config=config,
        **base_kwargs,
    )
