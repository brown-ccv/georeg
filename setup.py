#!/usr/bin/env python

from setuptools import setup

# get __version__
execfile("georeg_script.py/__init__.py")

setup(
    name="georeg_script.py",
    version=__version__,
    url="https://bitbucket.org/brown-data-science/georeg_script.py",
    description="""
        Processes and geocodes digitized registry documents.""",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7"],
    provides=["georeg_script.py"],
    packages=["georeg_script.py", "brown_geopy"],
    package_data={"georeg_script.py": ['data/*.txt', 'configs/**/*.cfg']},
    scripts=["scripts/georeg_script.py"],
    install_requires=['fuzzywuzzy', 'numpy', 'scikit-learn'],
)
