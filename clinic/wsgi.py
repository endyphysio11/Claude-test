"""
WSGI entry point for PythonAnywhere deployment.
PythonAnywhere looks for a variable named `application`.
"""
import sys
import os

# Add the clinic directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app as application  # noqa: F401
