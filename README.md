# FreeSteel

FreeSteel is Python library for reading electronic (national) id cards.


## Missing features

PDF report feature is not implemented.


## Requirements

FreeSteel is cross-platform, and should work on Linux, Windows and MacOS X
operating system. You will need to have `pyscard` and `pcscd` installed in order
to access Smart Cards.

Certificate verification (`freesteel.verification`) additionally needs
`cryptography` version 42 or newer. Rest of the library works without it.
