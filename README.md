# Installation

    python setup.py install

    Prereqs:

    * OpenCV 3 with python package (ironically still called `cv2`)
    * `tesseract` api modules (.so files)
    * Python packages:
        * fuzzywuzzy
        * numpy
        * scikit-learn

# For use on CCV
	make sure to run 
"export LD_LIBRARY_PATH=/gpfs/runtime/opt/gcc/4.8.2/lib64:$LD_LIBRARY_PATH" before using this on ccv (or simply make LD_LIBRARY_PATH contains that path)

# Test

        georeg_script.py --year 1979 --state RI --images test/img.png --outdir . --pre-processed
