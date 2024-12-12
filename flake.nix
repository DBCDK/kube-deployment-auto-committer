{
  description = "Nix flake for deployversioner";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.05";
  };

  outputs = { self, nixpkgs, ... }: {
    # Define packages for supported systems
    packages.x86_64-linux.default = let
      pkgs = import nixpkgs { system = "x86_64-linux"; };
    in pkgs.python3Packages.buildPythonPackage {
      pname = "deployversioner";
      version = "0.1.0";

      # Path to the source directory
      src = ./.;

      # Dependencies from install_requires in setup.py
      propagatedBuildInputs = with pkgs.python3Packages; [
        pyyaml
        requests
        urllib3
      ];

      # Metadata about the package
      meta = with pkgs.lib; {
        description = "Tool to commit a new image tag into a Kubernetes deployment configuration YAML file.";
        license = pkgs.lib.licenses.gpl3;
        platforms = pkgs.lib.platforms.unix;
      };
    };

    # Development shell with Python and dependencies
    devShells.x86_64-linux.default = let
      pkgs = import nixpkgs { system = "x86_64-linux"; };
    in pkgs.mkShell {
      buildInputs = with pkgs.python3Packages; [
        pyyaml
        requests
        urllib3
      ];
    };
  };
}

