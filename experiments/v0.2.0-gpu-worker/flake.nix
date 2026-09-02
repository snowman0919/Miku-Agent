{
  description = "Miku Agent V0.2.0 isolated GPU data worker environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = {nixpkgs, ...}: let
    system = "x86_64-linux";
    pkgs = import nixpkgs {inherit system;};
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = with pkgs; [ffmpeg_8 git python312 uv];
      UV_PYTHON = "${pkgs.python312}/bin/python3.12";
      UV_PROJECT_ENVIRONMENT = ".venv";
      shellHook = ''
        echo "GPU data worker shell; this does not modify the VoiceChat environment."
      '';
    };
  };
}

