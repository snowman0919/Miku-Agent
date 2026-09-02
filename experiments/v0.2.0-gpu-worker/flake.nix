{
  description = "Miku Agent V0.2.0 isolated GPU data worker environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = {nixpkgs, ...}: let
    system = "x86_64-linux";
    pkgs = import nixpkgs {inherit system;};
    runtimeLibraries = with pkgs; [ffmpeg_8 libsndfile stdenv.cc.cc.lib zlib];
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = with pkgs; [espeak-ng ffmpeg_8 git gnumake python312 uv];
      UV_PYTHON = "${pkgs.python312}/bin/python3.12";
      UV_PROJECT_ENVIRONMENT = ".venv";
      LD_LIBRARY_PATH = "/usr/lib/wsl/lib:${pkgs.lib.makeLibraryPath runtimeLibraries}";
      shellHook = ''
        echo "GPU data worker shell; this does not modify the VoiceChat environment."
      '';
    };
  };
}
