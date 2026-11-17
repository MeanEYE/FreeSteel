# FreeSteel

FreeSteel is Python library for reading electronic (national) id cards.


## Requirements

FreeSteel is cross-platform, and should work on Linux, Windows and MacOS X
operating system. You will need to have `pyscard` and `pcscd` installed in order
to access Smart Cards.

Certificate verification (`freesteel.verification`) additionally needs
`cryptography` version 42 or newer. Rest of the library works without it.


## Graphical application

`python3 -m interface` starts application which shows and prints data from
inserted card. It needs GTK 4, libadwaita, PyGObject with cairo support and
`cryptography`.


## Packaging

- `make dist-deb` creates package for Debian, Mint and Ubuntu;
- `make standalone` creates single-file executable;
- `make help` lists everything else.

Packages are placed in `build` directory.
