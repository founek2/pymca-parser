# pymca-parser

Parse export files from [PyMca](https://www.silx.org/doc/PyMca/dev/index.html) for analyses.

## Getting started

```bash
# By default iterate over html folder in CWD
uv run main.py --elements Ar:K,Fe:K.KL2

# Specify path to folder containg .fit files
uv run main.py --elements Ar:K,Fe:K.KL2 path/to/folder

uv run main.py --help
```