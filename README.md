# admix-kit
![python package](https://github.com/KangchengHou/admix-tools/actions/workflows/workflow.yml/badge.svg)
[![](https://img.shields.io/badge/docs-latest-blue.svg)](https://kangchenghou.github.io/admix-kit)

`admix-kit` is a Python library to faciliate analyses and methods development of genetics data from admixed populations. Jump to [Quick start (CLI)](https://kangchenghou.github.io/admix-kit/quickstart-cli.html) or [Quick start (Python)](https://kangchenghou.github.io/admix-kit/notebooks/quickstart.html).

> `admix-kit` is still in beta version, we welcome any [feedbacks](https://github.com/KangchengHou/admix-kit/pulls) and [bug reports](https://github.com/KangchengHou/admix-kit/issues).   

## Install
```bash
# Install admix-kit with Python 3.7, 3.8, 3.9
git clone https://github.com/KangchengHou/admix-kit
cd admix-kit
pip install -r requirements.txt; pip install -e .
```

> Installation requires cmake version > 3.12. Use `cmake --version` to check your cmake version. Use `pip install cmake` to install the latest version.

To update to the latest version, run the following
```bash
# reinstalling these dependencies because these are constantly being updated
pip uninstall -y pgenlib
pip install -U git+https://github.com/bogdanlab/tinygwas.git#egg=tinygwas
pip install -U git+https://github.com/KangchengHou/dask-pgen.git#egg=dask-pgen
git clone https://github.com/KangchengHou/admix-kit
cd admix-kit & pip install -e .
```

## Quick start and documentation
- [Prepare the data set for analysis](https://kangchenghou.github.io/admix-kit/prepare-dataset.html)
- [Quick start (Python)](https://kangchenghou.github.io/admix-kit/notebooks/quickstart.html)
- [Quick start (CLI)](https://kangchenghou.github.io/admix-kit/quickstart-cli.html)
- [Introduction of `admix.Dataset`](https://kangchenghou.github.io/admix-kit/notebooks/dataset.html)
- [Full documentation](https://kangchenghou.github.io/admix-kit/index.html) 



