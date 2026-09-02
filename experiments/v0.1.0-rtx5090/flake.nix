{
  description = "Miku Agent V0.1.0 RTX 5090 VoiceChat feasibility environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = {nixpkgs, ...}: let
    system = "x86_64-linux";
    pkgs = import nixpkgs {
      inherit system;
      config.allowUnfree = true;
    };
    runtimeLibraries = with pkgs; [
      ffmpeg_8
      libsndfile
      stdenv.cc.cc.lib
      zlib
    ];
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = with pkgs; [
        bash
        cacert
        cmake
        ffmpeg_8
        gcc
        git
        git-lfs
        ninja
        pkg-config
        python312
        uv
      ];

      UV_PYTHON = "${pkgs.python312}/bin/python3.12";
      UV_PROJECT_ENVIRONMENT = ".venv";
      LD_LIBRARY_PATH = "/usr/lib/wsl/lib:${pkgs.lib.makeLibraryPath runtimeLibraries}";

      shellHook = ''
        export NIX_CC_WRAPPER_TARGET_HOST_x86_64_unknown_linux_gnu=1
        echo "VoiceChat feasibility shell: Python 3.12 + uv + FFmpeg + GCC"
        echo "Run ./sync-env.sh once, then use .venv/bin/python."
      '';
    };

    formatter.${system} = pkgs.alejandra;
  };
}
