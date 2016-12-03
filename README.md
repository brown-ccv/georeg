# georeg

## Introduction

`georeg` is a research prototype for extracting addresses and other business
information from historical registries, developed by the
[CIS Data Science Practice](https://brown.edu/cis/data-science)
at Brown University, in collaboration with
[https://www.brown.edu/academics/institute-environment-society/people/details/scott-frickel](Scott Frickel)
and Tom Marlow from the
[Institute at Brown for Environment and
Society](https://www.brown.edu/academics/institute-environment-society/).

We have developed and tested it primarily with images we scanned from Rhode
Island manufacturing registries spanning the 1950s through the 1990s. In these
scanned images, `georeg` identifies each heading and the ordering of
manufacturer listings, so that we can extract the name, address, business type,
and number of employees as tabular data, which is then geocoded to provide
latitude and longitude.

## License

`georeg` is freely available for non-commercial use. Please see the included
file `LICENSE.txt` for more details.

## Installation

    python setup.py install

Prereqs:

    * OpenCV 3 with python package (ironically still called `cv2`)
    * [tessapi](https://bitbucket.org/brown-data-science/tessapi) package: python bindings for the Tesseract C API
    * Additional python packages:
        fuzzywuzzy>=0.11.1
        geopy>=1.11.0
        nltk>=3.2.1
        numpy>=1.10.0
        python-Levenshtein>=0.12.0
        scikit-learn>=0.17.1

## Geocoding

By default, `georeg` is configured to access an ArcGIS server at Brown
University for geocoding. Users not at Brown will need to modify the file
`georeg/brownarcgis.py` to provide an alternative URL to an ArcGIS server,
or an alternative geocoding service that is compatible with `geopy`.

## Running a simple test

    georeg --year 1979 --state RI --images test/img.png --outdir . --pre-processed

## Notes for running on Oscar at CCV

    module load georeg/dev
    export LD_LIBRARY_PATH=/gpfs/runtime/opt/gcc/4.8.2/lib64:$LD_LIBRARY_PATH
