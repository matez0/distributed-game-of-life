[![Python versions](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![license](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

# Distributed Game of Life

The cellular space is distributed across interconnected Game of Life processes.

In the first step, Game of Life processes will be represented by operating system processes.

## Testing

Create the virtual environment:
```
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
```
Run the tests:
```
python -m unittest
```

## References

- [Game of Life player web app](https://playgameoflife.com/)
