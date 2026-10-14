# Dependency environment only: entering it does not build or load the driver.
{
  # Override to reuse an independently verified, already available source tree.
  # The normal path verifies the unpacked archive against the content pin.
  nixpkgsSource ? builtins.fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/a5cc6f2c37bf518436dc8d1c288ccd0c43c2f4c4.tar.gz";
    sha256 = "sha256-r2f1oUwixlgq9zOdYLqJLfS/lWBT60/IITjhTKI59JU=";
  },
}:
let
  pkgs = import nixpkgsSource {
    system = "x86_64-linux";
    config = {};
    overlays = [];
  };
in
pkgs.mkShell {
  name = "goodix-55a4-build";

  # mkShell includes the C/C++ compiler through stdenv.
  nativeBuildInputs = with pkgs; [
    bashInteractive
    coreutils
    git
    binutils
    meson
    ninja
    python3
    pkg-config
    cmake
    glib.dev # glib-mkenums lives in the development output.
  ];

  buildInputs = with pkgs; [
    glib
    gusb
    openssl
    opencv4
    doctest
  ];

  shellHook = "";
}
