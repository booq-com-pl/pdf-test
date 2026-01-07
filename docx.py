"""Compatibility shim for the `docx` package.

This repository used to ship a local ``docx.py`` which shadowed the
installed ``python-docx`` package. That caused imports like
``from docx.oxml import ...`` (used by ``docxtpl``) to fail with
``ModuleNotFoundError: No module named 'docx.oxml'; 'docx' is not a package``.

To avoid requiring an immediate file deletion (which could be disruptive),
this shim attempts to locate and load the real ``docx`` package from
site-packages and re-export its symbols. If the real package cannot be
found, an ImportError is raised with a clear instruction to either install
``python-docx`` or remove this file.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys


def _load_real_docx():
	# Try to import the real `docx` package from site-packages. Using
	# importlib.import_module ensures the package is loaded as intended
	# and provides a proper __path__ for submodule imports (e.g. docx.oxml).
	try:
		real_docx = importlib.import_module("docx")
	except ModuleNotFoundError:
		raise ImportError(
			"Could not find installed 'docx' package (python-docx). "
			"Install it (pip install python-docx) or remove the local 'docx.py' file."
		)

	# Install the real package into sys.modules under the 'docx' name and
	# expose its public attributes from this shim module for compatibility.
	sys.modules["docx"] = real_docx
	for name, val in real_docx.__dict__.items():
		if not name.startswith("__"):
			globals()[name] = val

	# Make this module behave as a package so imports like 'docx.oxml' work.
	try:
		__path__ = list(real_docx.__path__)
	except Exception:
		# If the real package doesn't provide __path__, we can't support submodules,
		# but that is unlikely for python-docx.
		pass


_load_real_docx()
