# disable __pycache__

export PYTHONDONTWRITEBYTECODE=y

#
# Static Analysis
#

check-flake8:
# From the suggested workflow

# stop the build if there are Python syntax errors or undefined names
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# exit-zero treats all errors as warnings.
	flake8 . --count --exit-zero --statistics

check: check-flake8

#
# Usual boring stuff
#

.PHONY: check check-flake8 test image clean

# EOF
