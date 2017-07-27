# georeg

## Introduction

**georeg** is a research prototype for extracting addresses and other business
information from historical registries, developed by the
[CIS Data Science Practice](https://brown.edu/cis/data-science)
at Brown University, in collaboration with
[Scott Frickel](https://www.brown.edu/academics/institute-environment-society/people/details/scott-frickel)
and Tom Marlow at the
[Institute at Brown for Environment and
Society](https://www.brown.edu/academics/institute-environment-society/).

We have developed and tested it primarily with images we scanned from Rhode
Island manufacturing registries spanning the 1950s through the 1990s. In these
scanned images, **georeg** identifies each heading and the ordering of
manufacturer listings, so that we can extract the name, address, business type,
and number of employees as tabular data, which is then geocoded to provide
latitude and longitude.

## License

**georeg** is freely available for non-commercial use. Please see the included
file `LICENSE.txt` for more details.

## Installation

    python setup.py install

Prereqs:

* OpenCV 3 with python package (ironically still called `cv2`)
* [tessapi](https://bitbucket.org/brown-data-science/tessapi) package: python bindings for the Tesseract C API
* Additional python packages:
    * fuzzywuzzy>=0.11.1
    * geopy>=1.11.0
    * nltk>=3.2.1
    * numpy>=1.10.0
    * python-Levenshtein>=0.12.0
    * scikit-learn>=0.17.1

## Geocoding

By default, `georeg` is configured to access an ArcGIS server at Brown
University for geocoding. Users not at Brown will need to modify the file
`georeg/brownarcgis.py` to provide an alternative URL to an ArcGIS server,
or modify `georeg/business_geocoder.py` to provide an alternative 
geocoding service that is compatible with `geopy`.

## Running a simple test

    georeg --year 1979 --state RI --images test/img.png --outdir . --pre-processed

## Notes for running on Oscar at CCV

    module load georeg/dev
    export LD_LIBRARY_PATH=/gpfs/runtime/opt/gcc/4.8.2/lib64:$LD_LIBRARY_PATH

## Configuration files

A configuration file sets parameters for each state-year combination. The
configuration files are found in `georeg/configs`. 

The following parameters may be set in a configuration file:

    * kernel\_shape\_x: x-value (in pixels) of kernel to use in contour erosion/dilation
    * kernel\_shape\_y: y-value (in pixels) of kernel to use in contour erosion/dilation
    * thresh\_value: intensity threshold for image binarization
    * iterations: number of close operations to perform per contour
    * columns\_per\_page: number of text columns on each book page
    * pages\_per\_image: number of pages within each image file
    * bb\_expansion\_percent: percent by which to expand the bounding box around each contour

## Development

To develop **georeg** for new registries from different states and years:

    * Create a subclass of `georeg.registry_processor.RegistryProcessor` 
    * Add argument parsing logic to `scripts/georeg` to point to the correct
      `RegistryProcessor` class
    * Add a list of all cities in the state as `georeg/data/XX-cities.txt`,
      where XX is the two-digit state abbreviation
    * Add a configuration file as `georeg/configs/XX/YYYY.cfg`, where XX is
      the two-digit state abbreviation and YYYY is the four-digit year
