{
  description = "Glovebox flake using uv2nix";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;

      # Load workspace from repository root
      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      # === Overlays ===
      # Package overlay from workspace (for regular builds)
      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel"; # Or "sdist"
      };

      # Editable package overlay (for development shells)
      editableOverlay = workspace.mkEditablePyprojectOverlay {
        # Assuming your project root is the repo root
        root = "$REPO_ROOT";
      };

      # === Python Sets per System ===
      pythonSets = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          inherit (pkgs) stdenv;

          # Base Python package set from pyproject.nix
          baseSet = pkgs.callPackage pyproject-nix.build.packages {
            # Using python312 like the example, adjust if needed
            python = pkgs.python312;
          };

          # Overrides for build fixups, test additions, platform specifics
          pyprojectOverrides = final: prev: {

            # --- Platform Specific Package Handling ---
            # Provide empty derivations for platform-specific packages
            # when building on an incompatible platform.
            # Adjust package names as needed based on your pyproject.toml

            wmi = prev.wmi.overrideAttrs (old: {
              # Skip build if not Windows
              dontBuild = !stdenv.isWindows;
              # Provide empty outputs if skipped
              installPhase = lib.optionalString (!stdenv.isWindows) ''
                mkdir -p $out/lib/python${final.python.pythonVersion}/site-packages
              '';
            });

            pyobjc = prev.pyobjc.overrideAttrs (old: {
              # Skip build if not Darwin (macOS)
              dontBuild = !stdenv.isDarwin;
              # Provide empty outputs if skipped
              installPhase = lib.optionalString (!stdenv.isDarwin) ''
                mkdir -p $out/lib/python${final.python.pythonVersion}/site-packages
              '';
            });
            # Add other platform-specific overrides here...

            # --- Project Specific Overrides (glovebox) ---
            # Replace 'glovebox' with the actual package name from pyproject.toml
            glovebox = prev.glovebox.overrideAttrs (old: {
              # Add tests to passthru.tests for `nix flake check`
              passthru = old.passthru // {
                tests =
                  (old.tests or { })
                  // {
                    # Run pytest with coverage
                    pytest =
                      let
                        # Create a dedicated venv for testing
                        testDeps = workspace.deps.default // (workspace.deps.optional.dev or { });
                        venv = final.mkVirtualEnv "glovebox-pytest-env" testDeps;
                      in
                      stdenv.mkDerivation {
                        name = "${final.glovebox.name}-pytest";
                        inherit (final.glovebox) src;
                        nativeBuildInputs = [
                          venv
                          pkgs.git
                        ]; # Added git

                        dontConfigure = true;

                        buildPhase = ''
                          runHook preBuild
                          # Copy source to avoid modifying flake source
                          cp -r ${final.glovebox.src} ./source
                          cd ./source
                          # Run tests if tests directory exists
                          if [ -d "tests" ]; then
                            echo "Running pytest..."
                            pytest --cov . --cov-report html --cov-report term tests/
                          else
                            echo "No 'tests' directory found, skipping pytest run."
                            mkdir -p $out # Create dummy output if no tests run
                          fi
                          runHook postBuild
                        '';

                        installPhase = ''
                          runHook preInstall
                          # Install coverage report if it exists
                          if [ -d "htmlcov" ]; then
                            mv htmlcov $out
                          else
                            # Ensure $out exists even if no report generated
                            mkdir -p $out
                            echo "No coverage report generated." > $out/README.txt
                          fi
                          runHook postInstall
                        '';
                      };

                    # Simple import test (optional, pytest usually covers this)
                    import-test =
                      let
                        venv = final.mkVirtualEnv "glovebox-import-test-env" workspace.deps.default;
                      in
                      pkgs.runCommand "glovebox-import-test"
                        {
                          nativeBuildInputs = [ venv ];
                          meta.description = "Test importing glovebox package";
                        }
                        ''
                          # Try importing your module
                          python -c "import glovebox; print('Import successful')"

                          # Create empty output file to indicate success
                          touch $out
                        '';

                    # Add mypy check like the example if needed
                    # mypy = ... ;

                  }
                  # Add NixOS test if applicable (and if module exists)
                  // lib.optionalAttrs stdenv.isLinux {
                    # Ensure self.nixosModules.glovebox is defined below
                    nixos = self.checks.${system}.glovebox.passthru.tests.nixos;
                  };
              };
            });
          }; # End of pyprojectOverrides

        in
        # Apply overlays to the base Python set
        baseSet.overrideScope (
          lib.composeManyExtensions [
            pyproject-build-systems.overlays.default
            overlay # uv2nix overlay
            pyprojectOverrides # Custom overrides
          ]
        )
      ); # End of pythonSets

    in
    {
      # === Flake Checks ===
      checks = forAllSystems (
        system:
        let
          # Get the python set for the current system
          pythonSet = pythonSets.${system};
        in
        # Inherit tests from passthru.tests into flake checks
        # Replace 'glovebox' if your package name is different
        pythonSet.glovebox.passthru.tests or { }
      );

      # === Packages ===
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pythonSet = pythonSets.${system};
        in
        {
          # Expose the main package (replace 'glovebox' if needed)
          default = pythonSet.glovebox;

          # Expose the redistributable wheel/sdist package
          wheel = pythonSet.glovebox.override {
            # Use the appropriate hook for building distributions
            pyprojectHook = pythonSet.pyprojectDistHook;
          };

          # Expose a virtual environment package if useful
          venv = pythonSet.mkVirtualEnv "glovebox-env" workspace.deps.default;

          # Add Docker image build if desired (similar to example)
          # docker = ... ;

        }
      );

      # === Runnable Apps ===
      apps = forAllSystems (
        system:
        let
          venv = self.packages.${system}.venv; # Use the venv package
        in
        {
          # Run glovebox using the virtual environment
          default = {
            type = "app";
            # Adjust the command path if needed
            program = "${venv}/bin/glovebox";
            meta.description = "Run glovebox application";
          };
        }
      );

      # === Development Shells ===
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};

          # Base python set for the current system
          basePythonSet = pythonSets.${system};

          # --- Create an *editable* Python set for development ---
          editablePythonSet = basePythonSet.overrideScope (
            lib.composeManyExtensions [
              editableOverlay # Apply the editable overlay first

              # Override the specific project package ('glovebox') for editability
              (final: prev: {
                # Replace 'glovebox' with your actual package name
                glovebox = prev.glovebox.overrideAttrs (old: {
                  # Crucially, override the source to use fileset for HMR
                  src = lib.fileset.toSource {
                    root = old.src; # Use the original source path as root
                    # Define the set of files/dirs needed for an editable install
                    fileset = lib.fileset.unions [
                      (old.src + "/pyproject.toml")
                      (old.src + "/README.md") # Include if it exists/is needed
                      (old.src + "/glovebox") # Main source directory
                      (old.src + "/tests") # Include tests directory if needed in shell
                      (old.src + "/keyboards") # Include tests directory if needed in shell
                    ];
                  };
                  # Add build system dependencies needed for editable installs
                  nativeBuildInputs =
                    old.nativeBuildInputs
                    ++ final.resolveBuildSystem {
                      # List packages that should be installed as editable
                      editables = [ "glovebox" ]; # Match your package name
                    };
                });
              })
            ]
          );

          # Define dependencies for the development environment
          # Include base dependencies + 'dev' optional dependencies
          devDeps = workspace.deps.default // (workspace.deps.optional.dev or { });

          # Create the virtual environment using the *editable* set
          devVenv = editablePythonSet.mkVirtualEnv "glovebox-dev-env" devDeps;

        in
        {
          # Default development shell using the editable setup
          default = pkgs.mkShell {
            packages = [
              devVenv # The virtual env with editable package(s)
              pkgs.uv # Include uv for potential manual operations
              # Add other dev tools: git, editor plugins, linters etc.
              pkgs.git
            ];

            # Environment variables for uv integration
            env = {
              # Tell uv not to try and sync deps on activation
              UV_NO_SYNC = "1";
              # Point uv to the Python interpreter within our Nix-managed venv
              UV_PYTHON = "${devVenv}/bin/python";
              # Prevent uv from downloading Python itself
              UV_PYTHON_DOWNLOADS = "never";
            };

            shellHook = ''
              # Unset PYTHONPATH to avoid conflicts with Nix environment
              unset PYTHONPATH

              # Set REPO_ROOT for the editable overlay to find the source
              export REPO_ROOT=$(git rev-parse --show-toplevel)

              # Optional: Print a welcome message or instructions
              echo "--- Glovebox Editable Development Shell ---"
              echo "Project 'glovebox' is installed in editable mode."
              echo "Virtual environment managed by Nix at: ${devVenv}"
              echo "You can use 'pytest' to run tests."
              # Add any other useful messages or commands
            '';
          };

          # You could add other specialized shells here if needed
          # e.g., a shell specifically for documentation building
        }
      );
    };
}
