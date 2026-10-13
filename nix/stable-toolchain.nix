# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT
{ zaozi, system, lock }:
let
  circt = zaozi.inputs.circt-nix;
  llvmInfo = lock.nodes.llvm-src.locked;
  pkgs = circt.inputs.nixpkgs.legacyPackages.${system};
  llvmArchive = pkgs.fetchzip {
    name = "source";
    url = "https://github.com/${llvmInfo.owner}/${llvmInfo.repo}/archive/${llvmInfo.rev}.tar.gz";
    hash = llvmInfo.narHash;
    # Git archive descriptions change as repository object names grow.
    postFetch = ''
      cat > "$out/clang/bindings/python/.git_archival.txt" <<'EOF'
      node: ${llvmInfo.rev}
      node-date: 2026-07-13T15:08:09+10:00
      describe-name: llvmorg-23-init-22791-gb1c56fb53a9c7
      EOF
    '';
  };
  llvmSource = {
    # Preserve the source context used by cached compiler derivations.
    outPath = builtins.path {
      path = llvmArchive;
      name = "source";
      sha256 = llvmInfo.narHash;
    };
    inherit (llvmInfo) rev lastModified narHash;
  };
  fixedCirct = (import (circt.outPath + "/flake.nix")).outputs (circt.inputs // {
    self = circt;
    llvm-src = llvmSource;
  });
  fixedZaozi = (import (zaozi.outPath + "/flake.nix")).outputs (zaozi.inputs // {
    self = zaozi;
    circt-nix = circt // fixedCirct;
  });
in fixedZaozi.legacyPackages.${system}
