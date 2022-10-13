#!/bin/bash
project="gapps"

# Setup virtual environment
pip install virtualenv
python3 -m venv $project
source $project/bin/activate

pip install -r requirments.txt