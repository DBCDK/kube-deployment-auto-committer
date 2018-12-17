kube-deployment-auto-committer
==============================

program to commit a new image tag into a kubernetes deployment configuration
yaml file.

### development ###
pipenv is used for dependency resolution
```bash
python3 -m venv ENV
source ENV/bin/activate
pip3 install -U pip pipenv
pipenv install --dev
pip3 install .
# type checking:
mypy src/deployversioner
# testing:
python3 -m unittest discover -s tests
```

### examples ###
```bash
set-new-version app-deployment.yml $private_token $project_id master-9 -b staging
```
