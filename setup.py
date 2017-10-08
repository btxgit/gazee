#!/usr/bin/env python3

import os
import re, sys
from setuptools import setup, find_packages
from setuptools import Command
from shutil import rmtree

def build_config(**kw):
    bcfg = {}

    for k in kw:
        bcfg[k] = kw[k]

    return bcfg

class CleanCommand(Command):
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        dpath = os.path.realpath('./dist')
        bpath = os.path.realpath('./build')
        print("Cleaning dist...")
        rmtree(dpath, ignore_errors=True)
        print("Cleaning build...")
        rmtree(bpath, ignore_errors=True)
        
inrel=['CherryPy>=11.0.0', 'Mako>=1.0.7', 'Pillow>=4.2.1', 'rarfile>=3.0', 'GitPython>=2.1.5']

ver = None
with open('gazee/__init__.py', 'rb') as fd:
    for line in fd.readlines():
        line = bytes(line).rstrip()
        if line.startswith(b"__version__ = '"):
            ver = line.rstrip(b"' ").split(b"'")[1].decode('utf-8')
            break

if ver is None:
    print("Unable to locate the version info in __init__.  Exiting.")
    sys.exit(1)
    
print("Found version: v%s" % str)

bcfg = build_config(
    name='gazee',
    version=ver,
    packages=find_packages(),
    py_modules=['gazee'],
    description="A CherryPy WebServer implementation of a comic book reader with management / organizational features.",
    author="hubbcaps",
    license="GPLv3",
    include_package_data=True,
    install_requires=inrel,
    zip_safe=False,
    entry_points={
        'console_scripts': ['Gazee=gazee.__main__:main']
    }
)
setup(cmdclass={ 'distclean': CleanCommand }, **bcfg)
