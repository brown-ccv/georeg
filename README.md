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
and number of employees as tabular data, which are then geocoded to provide
latitude and longitude.

## License

**georeg** is freely available for non-commercial use. Please see the included
file `LICENSE.txt` for more details.

## Installation

### Quick start with Docker

If you would like to try **georeg** with minimal installation and you already
have [Docker](https://www.docker.com) installed, you can pull the latest Docker
image with:

    docker pull browndatascience/georeg

### Quick start with conda

We have also packaged and distributed binary versions of **georeg** for 64-bit
Linux using the conda package manager from [Anaconda Python](https://www.continuum.io/anaconda-overview). The packages are available in the
[brown-data-science](https://anaconda.org/brown-data-science) channel. You
can create a new conda environment for **georeg** using:

    conda create -n georeg -c brown-data-science georeg

Then to activate the environment and run **georeg**, use:

    source activate georeg
    georeg -h

### Manual installation

It is also possible to install **georeg** directly from the git repo or from a
downloaded [release](https://github.com/brown-data-science/georeg/releases)
using:

    python setup.py install

The prerequisites are:

* OpenCV 3 with python package (ironically still called `cv2`)
* [tessapi](https://bitbucket.org/brown-data-science/tessapi) package: python bindings for the Tesseract C API
* Additional python packages:
    * fuzzywuzzy>=0.11.1
    * geopy>=1.11.0
    * nltk>=3.2.1
    * numpy>=1.10.0
    * python-Levenshtein>=0.12.0
    * scikit-learn>=0.17.1

## Testing

To validate that your installation is working, you can download a scanned page
from the 1979 RI manufacturing directory here:

    curl -LO https://github.com/brown-data-science/georeg/raw/master/test/img.png

To test using the Docker image on OS X, Linux, or in Windows PowerShell, run:

    docker run -v ${PWD}:/work -w /work --rm browndatascience/georeg --year 1979 --state RI --images img.png --outdir . --pre-processed

To test using the Docker image in Windows Command Line, run:

    docker run -v %cd%:/work -w /work --rm browndatascience/georeg --year 1979 --state RI --images img.png --outdir . --pre-processed

To test using a conda installation on Linux, run:

    georeg --year 1979 --state RI --images img.png --outdir . --pre-processed

The test will create the following files and output:

    1979-compiled.tsv
    performance_stats.txt
    unsuccessful_geo-queries_RI_1979.log

    processing: img.png (1/1)
    Mean OCR confidence: 85.274869%
    Geocoder success rate: 0.000000%
    Businesses per image deviation: 0.000000
    Businesses per image mean: 22.000000
    Elapsed time: 0 hours, 0 minutes and 11 seconds
    done

As discussed below in the "Geocoding" section, you will receive a 0.0%
geocoding rate using the default settings if you do not have access to Brown
University's ArcGIS server.

## Geocoding

By default, **georeg** is configured to access an ArcGIS server at Brown
University for geocoding. Users not at Brown will need to modify the file
`georeg/brownarcgis.py` to provide an alternative URL to an ArcGIS server,
or modify `georeg/business_geocoder.py` to provide an alternative
geocoding service that is compatible with geopy.

## Configuration files

A configuration file sets parameters for each state-year combination. The
configuration files are found in `georeg/configs`.

The following parameters may be set in a configuration file:

| **kernel\_shape\_x** | x-value (in pixels) of kernel to use in contour erosion/dilation |
| **kernel\_shape\_y** | y-value (in pixels) of kernel to use in contour erosion/dilation |
| **thresh\_value** | intensity threshold for image binarization |
| **iterations** | number of close operations to perform per contour |
| **columns\_per\_page** | number of text columns on each book page |
| **pages\_per\_image** | number of pages within each image file |
| **bb\_expansion\_percent** | percent by which to expand the bounding box around each contour |

## Development

To develop **georeg** for new registries from different states and years:

* Create a subclass of `georeg.registry_processor.RegistryProcessor` 
* Add argument parsing logic to `scripts/georeg` to point to the correct
  `RegistryProcessor` class
* Add a list of all cities in the state as `georeg/data/XX-cities.txt`,
  where XX is the two-digit state abbreviation
* Add a configuration file as `georeg/configs/XX/YYYY.cfg`, where XX is
  the two-digit state abbreviation and YYYY is the four-digit year
