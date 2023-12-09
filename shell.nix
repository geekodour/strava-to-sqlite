let
  pkgs = import <nixpkgs> { };
  pyPackages = pkgs.python311Packages;
in pkgs.mkShell {
  name = "py";
  venvDir = "./.venv";
  buildInputs = [
    pyPackages.pip
    pyPackages.venvShellHook
    pkgs.ruff # linter
    pkgs.python311
  ];

  postShellHook = ''
    pip install poetry
    unset SOURCE_DATE_EPOCH
  '';
}
