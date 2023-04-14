# Contributing guide

## Setting up your dev environment

Create a new virtual environment, activate it, and install in development mode:
```shell
python -m venv venv
. venv/bin/activate
pip intall -e ".[dev]"
```

## Run the tests

Run the following from the project directory:
```shell
pytest
```

## Running the examples

If you would like to run the examples, you will need to run:
```shell
pip install -e ".[examples]"
```
