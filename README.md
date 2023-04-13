# Lifecycle Engineering Model-Based Analysis System

<img src="https://user-images.githubusercontent.com/11037737/183445259-369dc3a4-ee22-40c8-9aa8-130a58ecedb7.png" style="width: 100%; max-width: 500px;" />

[![Run Tests](https://github.com/lembas-project/lembas-core/actions/workflows/test.yml/badge.svg)](https://github.com/lembas-project/lembas-core/actions/workflows/test.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/lembas-project/lembas-core/main.svg)](https://results.pre-commit.ci/latest/github/lembas-project/lembas-core/main)
[![codecov](https://codecov.io/gh/lembas-project/lembas-core/branch/main/graph/badge.svg?token=AGIQSHEDQU)](https://codecov.io/gh/lembas-project/lembas-core)
[![Documentation Status](https://readthedocs.org/projects/lembas/badge/?version=latest)](https://lembas.readthedocs.io/en/latest/?badge=latest)
[![Version](https://img.shields.io/pypi/v/lembas.svg)](https://pypi.org/project/lembas/)
[![License](https://img.shields.io/pypi/l/lembas.svg)](https://pypi.org/project/lembas/)

`lembas` is an experimental framework for reproducible, versioned, and full-lifecycle analysis
model management.
It has its roots in traditional engineering domains, which requires many types of analysis,
including physics-based simulation and data-driven methods.
The aim is to identify, by building a prototype, the appropriate APIs which make the scientific
and data-science Python ecosystem most accessible to Subject-Matter Experts (SMEs) in
Engineering domains.
By enabling seamless intercommunication between domains, and proper version management of
analysis models, truly interdisciplinary system design and assessment become possible.


## Dev environment setup

Create a new virtual environment, activate it, and install in development mode:

```shell
python -m venv venv
. venv/bin/activate
pip intall -e ".[dev]"
```
