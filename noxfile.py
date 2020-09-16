import nox
import tempfile
from pathlib import Path
import os
from distutils.dir_util import copy_tree

python_versions = [
    "3.8",
]

sphinx_versions = [
    "^3.0",
]

@nox.session(python=python_versions, reuse_venv=True)
@nox.parametrize("sphinx", sphinx_versions)
def tests(session, sphinx):
    # see https://github.com/python-poetry/poetry/issues/2920#issuecomment-693147409
    with tempfile.TemporaryDirectory() as tmp_dir:
        copy_tree(
            Path.cwd(), tmp_dir
        )
        os.chdir(tmp_dir)
        
        session.run('poetry', 'add', f'sphinx@{sphinx}', external=True)
        session.run('poetry', 'install', external=True)
        session.run('nosetests', '-w', 'tests')

@nox.session(python=None)
def lint(session):
    session.run('flake8', 'sphinxcontrib', external=True)