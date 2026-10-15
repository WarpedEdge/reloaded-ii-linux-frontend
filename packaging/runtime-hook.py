"""Resolve bundled libarchive even on hosts without a system libarchive."""
import os
import sys
from pathlib import Path

os.environ['LIBARCHIVE'] = str(Path(sys._MEIPASS) / 'libarchive.so.13')
