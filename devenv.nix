{
  pkgs,
  lib,
  config,
  ...
}:
let
  gdk = pkgs.google-cloud-sdk.withExtraComponents (
    with pkgs.google-cloud-sdk.components;
    [
      gke-gcloud-auth-plugin
    ]
  );
in
{
  cachix.enable = false;

  packages = [
    pkgs.pandoc
    gdk
    pkgs.tcl
    pkgs.tclx
  ];

  env.LD_LIBRARY_PATH = lib.makeLibraryPath [
    pkgs.stdenv.cc.cc.lib
    pkgs.libGL
    pkgs.file
    pkgs.libz
    pkgs.gcc-unwrapped
    pkgs.stdenv
  ];

  # https://devenv.sh/languages/python/
  languages.python = {
    enable = true;
    uv.enable = true;
  };

  languages.javascript = {
    enable = true;
    pnpm = {
      enable = true;
      install.enable = true;
    };
  };

  languages.rust = {
    enable = true;
  };

  enterShell = '''';
  # git-hooks.hooks = {
  #   ruff.enable = true;
  #   rustfmt.enable = true;
  # };
  #
  # See full reference at https://devenv.sh/reference/options/
}
