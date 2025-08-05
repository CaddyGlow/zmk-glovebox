{
  description = "Simplified Glovebox flake";

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

  outputs = { self, nixpkgs, uv2nix, pyproject-nix, pyproject-build-systems, ... }:
    let
      inherit (nixpkgs) lib;
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;
      
      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
      
      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };
      
      pythonSets = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          baseSet = pkgs.callPackage pyproject-nix.build.packages {
            python = pkgs.python313;
          };
          
          # Override to add git for version detection
          projectOverrides = final: prev: {
            zmk-glovebox = prev.zmk-glovebox.overrideAttrs (old: {
              nativeBuildInputs = (old.nativeBuildInputs or []) ++ [ pkgs.git ];
              # Set version from git tag or fallback
              preBuild = ''
                export SETUPTOOLS_SCM_PRETEND_VERSION="0.1.1"
              '';
            });
          };
        in
        baseSet.overrideScope (
          lib.composeManyExtensions [
            pyproject-build-systems.overlays.default
            overlay
            projectOverrides
          ]
        )
      );
    in
    {
      packages = forAllSystems (system:
        let
          pythonSet = pythonSets.${system};
          venv = pythonSet.mkVirtualEnv "zmk-glovebox-env" workspace.deps.default;
        in
        {
          default = pythonSet.zmk-glovebox;
          venv = venv;
        }
      );
      
      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.venv}/bin/glovebox";
        };
      });
    };
}
