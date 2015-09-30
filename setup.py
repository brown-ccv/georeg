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
    package_data={"georeg": ["data/*"]},
    scripts=["scripts/georeg"]
)
