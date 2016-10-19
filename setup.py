#!/usr/bin/env python

from setuptools import setup

# get __version__
execfile("georeg/__init__.py")

setup(
    name="georeg",
    version=__version__,
    url="https://bitbucket.org/brown-data-science/georeg",
    description="""
        Processes and geocodes digitized registry documents.""",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7"],
    provides=["georeg"],
    packages=["georeg"],
    package_data={"georeg": ['data/*.txt', 'configs/**/*.cfg']},
    scripts=["scripts/georeg", "scripts/georeg-sweep"],
    install_requires=[
        "fuzzywuzzy>=0.11.1",
        "geopy>=1.11.0",
        "nltk>=3.2.1",
        "numpy>=1.10.0",
        "python-Levenshtein>=0.12.0",
        "scikit-learn>=0.17.1",
        "tessapi>=0.0.1"]
)
