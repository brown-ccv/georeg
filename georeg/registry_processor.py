# coding=utf-8
import cv2
import numpy as np
import os
import csv
import sys
import ConfigParser
import itertools
import collections
import spell_checker
import business_geocoder as geo
from math import sqrt
from operator import itemgetter, attrgetter
from sklearn.cluster import KMeans

import georeg
from TessBinding import TessBaseAPI

class CityDetector(spell_checker.SpellChecker):
    """loads a file of cities for comparison against strings"""
    def __init__(self, similarity_thresh = 50):
        super(CityDetector, self).__init__(similarity_thresh)
        
    def load_cities_txt_file(self, file_name):
        with open(file_name) as file:
            for line in file:
                line = line.strip()
                self.add_token(line, 1)

    def match_to_cities(self, line, cutoff=60):
        line = line.lower().strip()

        # if the end of the string matches "—continued" then remove it
        if spell_checker.ratio(line[-12:], "-continued") > cutoff:
            line = line[:-12]

        match, ratio = self.get_best_spelling_correction(line)

        if ratio >= cutoff:
            return match
        else:
            return None

class Business:

    def __init__(self):
        self.name = ""
        self.city = ""
        self.zip = ""
        self.address = ""
        self.category = [] # business category or sic code depending on year
        self.emp = "" # employment
        self.sales = ""
        self.cat_desc = []
        self.bracket = ""

        # coordinates
        self.lat = ""
        self.long = ""
        self.confidence_score = 0.0


class Contour:
    def __init__(self, contour_data=None):
        self.data = contour_data
        self.text = ""
        self.font_attrs = []

        if contour_data is not None:
            [self.x, self.y, self.w, self.h] = cv2.boundingRect(contour_data)
            self.x_mid = self.x + self.w / 2
            self.y_mid = self.y + self.h / 2
        else:
            self.x = 0
            self.y = 0
            self.w = 0
            self.h = 0

            self.x_mid = 0
            self.y_mid = 0

class RegistryProcessor(object):

    # lambdas were no longer sufficient with multiple threads for some reason
    @property
    def _image_height(self):
        return self.__image.shape[0]

    @property
    def _image_width(self):
        return self.__image.shape[1]

    @property
    def _geoquery_log_fn(self):
        assert (self.state != "" and self.year != -1)
        return os.path.join(self.outdir, "unsucessful_geo-queries_%s_%d.log" % (self.state, self.year))

    def _expand_bb(self, x, y, w, h):
        return \
        (x - int(self._image_width * self.bb_expansion_percent / 2), \
         y - int(self._image_height * self.bb_expansion_percent / 2), \
         w + int(self._image_width * self.bb_expansion_percent / 2), \
         h + int(self._image_height * self.bb_expansion_percent / 2))

    def _spellcheck_callback(self, word, conf):
        if len(word) > 3:
            return self._spell_checker.get_best_spelling_correction(word.encode('ascii'))[0]
        else: return word

    # when RegistryProcessor object is copied into a new subprocess
    # our tess api object needs to be recreated so we made a function to do it
    def make_tess_api(self):
        self._tess_api = TessBaseAPI()

        # set some tesseract parameters
        if not self._tess_api.SetVariable("tessedit_pageseg_mode", "6"):
            raise RuntimeError("error setting tesseract psm")
        if not self._tess_api.SetVariable("tessedit_char_whitelist", "\"#%&'()*+,-./\\0123456789:;ABCDEFGHIJKLMNOPQRSTUVWXYZ[]_abcdefghijklmnopqrstuvwxyz"):
            raise RuntimeError("error setting tesseract character whitelist")

        # uncomment this to register the generalized spellchecker with the tesseract api
        #self._tess_api.RegisterSpellCheckCallback(lambda str, conf: RegistryProcessor._spellcheck_callback(self, str, conf))

    def initialize_spell_checkers(self):
        """initialize both the general spell checker and city detector"""

        basepath = georeg.__path__[0]

        self._spell_checker.load_dictionary_from_tsv(os.path.abspath(os.path.join(basepath, "data", self.state + "_vocab.tsv")))
        self._city_detector.load_cities_txt_file(os.path.join(basepath, "data", "%s-cities.txt" % self.state))

    def uninitialize_spell_checkers(self):
        """
        uninitialize both spell checkers,
        this needs to be called before a RegistryProcessor object is copied to another subprocess
        otherwise python will crash attempting to copy spellchecker's complicated innards
        """
        self._spell_checker.remove_all_tokens()
        self._city_detector.remove_all_tokens()

    # constructor no longer takes state & year args, use initialize_state_year() instead
    def __init__(self):
        self._tess_api = None

        # initialize self._tess_api
        self.make_tess_api()

        self.businesses = []

        # these will automatically be initialized when initialize_state_year() is called
        # they both look in the data directory for their vocab files (see initialize_state_year)
        self._spell_checker = spell_checker.SpellChecker()
        self._city_detector = CityDetector()

        self.__image = None
        self.__thresh_image = None

        # image processing parameters (these are example values)
        self.kernel_shape = (10, 3) # wider (i.e. higher x value) will cause more collisions along the x axis and visa versa for the y value
        self.thresh_value = 60  # higher = more exposure (max = 255)
        self.iterations = 8 # iterations of closing operation, higher values will help fill contours where text is farther apart but can cause contour collisions
        self.indent_width = 0.025 # indent width as % of contour width used for separating texas contours

        # percent of image width and height to add to bounding box width and height of contours (can improve ocr accuracy)
        # values that are too high will cause excess text to be ocred with each contour
        self.bb_expansion_percent = 0.012

        self.columns_per_page = 2
        self.pages_per_image = 1
        self.page_boundary = -1 # coordinates of page boundary on current image (only used if self.pages_per_image == 2)

        self.std_thresh = 1  # number of standard deviations beyond which contour is no longer considered part of column

        # performance & accuracy stats
        self.__ocr_confidence_sum = 0
        self.__num_words = 0
        self.__num_geo_successes = 0
        self.__num_geo_attempts = 0
        self.__per_image_business_counts = []

        self.draw_debug_images = False  # turning this on can help with debugging
        self.assume_pre_processed = False  # assume images are preprocessed so to not waste extra computational power

        self.line_color = (130, 130, 130)  # NOTE: line color for debug images, must be visible in grayscale
        self.outdir = "."  # dir to write debug images, logs and tsv results

        self.state = ""
        self.year = -1

    #initialize this object for the specified state and year (if not done already)
    def initialize_state_year(self, state, year, init_city_detector = True, init_spellchecker = True):

        # initialize city lookup for this state
        self.state = state
        self.year = year

        basepath = georeg.__path__[0]

        if init_city_detector:
            self._city_detector.load_cities_txt_file(os.path.join(basepath, "data", "%s-cities.txt" % self.state))
        if init_spellchecker:
            self._spell_checker.load_dictionary_from_tsv(os.path.abspath(os.path.join(basepath, "data", state + "_vocab.tsv")))

        # load config file from this state & year
        self.load_settings_from_cfg(os.path.join(basepath, "configs", state, str(year) + ".cfg"))

    # this function should not need to be overriden
    def process_image(self, path):
        """process a registry image and store results in the businesses member"""

        self.businesses = [] # reset businesses list

        self.__image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)

        contours = self._get_contours(make_new_thresh = True)
        contours = [Contour(c) for c in contours]

        #remove noise from edge of image
        if not self.assume_pre_processed:
            contours = self._remove_edge_contours(contours)

        if self.draw_debug_images:
            canvas = np.zeros(self.__image.shape, self.__image.dtype)
            cv2.drawContours(canvas,[c.data for c in
                contours],-1,self.line_color,-1)
            cv2.imwrite(os.path.join(self.outdir, "closed.tiff"), canvas)

        clustering = self._find_column_locations(contours)
        column_contours, noncolumn_contours = self._make_contour_columns(contours, clustering)

        noncolumn_contours = self._get_noncolumn_contours_of_interest(noncolumn_contours)

        if self.draw_debug_images:
            contoured = self.__image.copy()
        else: contoured = None

        # set the image tesseract will work with
        self._tess_api.SetImage(self.__thresh_image)

        if self.draw_debug_images:
            draw_rect = lambda contoured, x, y, w, h: cv2.rectangle(contoured, (x, y), (x + w, y + h), self.line_color, 5)
        else:
            draw_rect = lambda contoured, x, y, w, h: None

        # OCR our column contours
        for contour in itertools.chain.from_iterable(column_contours):
            x,y,w,h = self._expand_bb(contour.x,contour.y,contour.w,contour.h)

            draw_rect(contoured, x, y, w, h)

            # specify region tesseract should ocr
            self._tess_api.SetRectangle(x,y,w,h)
            contour.text, contour.font_attrs = self._tess_api.GetTextWithAttrs()

            total_conf, num_words = self._tess_api.TotalConfidence()

            self.__ocr_confidence_sum += total_conf
            self.__num_words += num_words

        # OCR our noncolumn contours of interest
        for contour in noncolumn_contours:
            x, y, w, h = self._expand_bb(contour.x, contour.y, contour.w, contour.h)

            draw_rect(contoured, x, y, w, h)

            # specify region tesseract should ocr
            self._tess_api.SetRectangle(x, y, w, h)

            contour.text, contour.font_attrs = self._tess_api.GetTextWithAttrs()

        if self.draw_debug_images:
            # write original image with added contours to disk
            cv2.imwrite(os.path.join(self.outdir, "contoured.tiff"), contoured)

        # get our custom call args if any
        call_args = self._define_contour_call_args(column_contours, noncolumn_contours)

        num_businesses_found = 0

        if not os.path.exists(self._geoquery_log_fn): # if the log doesn't exist make it
            file = open(self._geoquery_log_fn, "w")
            file.close()

        # if args is indeed multiple arguments then we'll expand them
        if isinstance(call_args[0], collections.Sequence) and not isinstance(call_args[0], basestring):
            def process_with_args(args):
                return self._process_contour(*args), args[0]
        else:  # otherwise we treat it like one argument
            def process_with_args(args):
                return self._process_contour(args), args

        # here we process all of our contours
        for args in call_args:
            business, contour_txt = process_with_args(args)

            num_businesses_found += 1
            self.__num_geo_attempts += 1

            result = None

            try:
                # if address was found attempt to geocode
                if business.address:
                    result = geo.geocode_business(business, self.state)

                    # record business
                    self.businesses.append(business)

                if not result:
                    with open(self._geoquery_log_fn, "a") as file:
                        file.write("Unsuccessful geo-query from %s:\n" % os.path.basename(path))
                        file.write("name: \"%s\" address: \"%s\", city: \"%s\", zip: \"%s\"\n" % (
                            business.name, business.address, business.city, business.zip))
                        file.write("=" * 100 + "\n")
                        file.write("Contour Text:\n")
                        file.write("=" * 100 + "\n")
                        file.write(contour_txt.strip() + "\n")  # write contour text
                        file.write("=" * 100 + "\n\n")
                else:
                    self.__num_geo_successes += 1
            except AttributeError:
                if business is None:
                    raise TypeError("'NoneType' returned by _process_contour for business value, please return empty business objects instead")
                else: raise

        # record the number of businesses found in this image
        self.__per_image_business_counts.append(num_businesses_found)

    def _get_noncolumn_contours_of_interest(self, noncolumn_contours):
        """
        override this if your class is interested in non-column contours (i.e. headers)
        :param noncolumn_contours: noncolumn contours found
        :return: a list of noncolumn contours we are inerested in
        """
        return []

    def _define_contour_call_args(self, column_contours, noncolumn_contours):
        """
        override this if _process_contour() needs to be called with additional arguments (like the text of the header it is under)
        :param column_contours: a 2d list were each column is a column and each row is a contour (of type 'Contour')
        :param noncolumn_contours: a 1d list of all non-column contours in the image (of type 'Contour')
        :return: a list of argument tuples that will each be passed to a _process_contour() call
                (1st arg must be the contour text, and 2nd must be the contour text attributes)
        """
        return [(c.text, c.font_attrs) for c in itertools.chain.from_iterable(column_contours)]

    def _process_contour(self, contour_txt, countor_font_attrs, *args):
        """
        Process the text of a contour to make a business object,
        may also be passed info about non-column contours if
        _get_noncolumn_contours_of_interest() and _define_contour_call_args()
        are overriden
        :param contour_txt: the text in the contour
        :param args: optional additional information
        :return: return value must be a Business() object
                 if the business contour is invalid return an empty business object
        """
        raise NotImplementedError

    def remove_geoquery_log(self):
        """if this isn't called the existing file will simply be appended to"""
        if (os.path.exists(self._geoquery_log_fn)):
            os.remove(self._geoquery_log_fn)

    def total_ocr_confidence(self):
        """returns (total confidence, number of words) for getting an average over multiple runs"""
        return (self.__ocr_confidence_sum, self.__num_words)

    def mean_ocr_confidence(self):
        """returns mean confidence so far or -1 if OCR has not been used yet"""
        return self.__ocr_confidence_sum * 1.0 / self.__num_words if self.__num_words > 0 else -1

    #TODO: reimplement success rate tracking once our geocoder returns results below 75%
    # i.e. return mean ocr confidence instead of success rate
    def geocoder_success_rate(self):
        """returns geocoder success rate or -1 if not valid"""
        return (self.__num_geo_successes * 1.0 / self.__num_geo_attempts) * 100 if self.__num_geo_attempts > 0 else -1

    def business_count_std_and_avg(self):
        """
        gets business count per image standard dev and average
        :return: (standard dev, average) or (-1, -1) if invalid
        """

        if len(self.__per_image_business_counts) == 0:
            return (-1, -1)

        mean_bus_count = sum(self.__per_image_business_counts) * 1.0 / len(self.__per_image_business_counts)
        dists_from_mean = ((mean_bus_count - c) ** 2 for c in self.__per_image_business_counts)
        variance = sum(dists_from_mean) / len(self.__per_image_business_counts)

        return (sqrt(variance), mean_bus_count)

    def reset_stats(self):
        """resets all performance stats being recorded by registry_processor"""
        self.__ocr_confidence_sum = 0
        self.__num_words = 0
        self.__num_geo_successes = 0
        self.__num_geo_attempts = 0
        self.__per_image_business_counts = []

    def load_from_tsv(self, path):
        """load self.businesses from a tsv file where they were previously saved"""

        self.businesses = [] # reset businesses list

        # mini function for loading an individual business file
        def load_businesses(path):
            with open(path, "r") as file:
                file_reader = csv.reader(file, delimiter="\t")
                for row in file_reader:
                    business = Business()

                    [business.category, business.name, business.address,
                     business.city, business.zip, business.emp, business.sales,
                     business.cat_desc, business.bracket, business.lat,
                     business.long, business.confidence_score] = row

                    # cast to float
                    business.confidence_score = float(business.confidence_score)

                    self.businesses.append(business)

        # load normal businesses
        load_businesses(path)

    def record_to_tsv(self, path, mode = 'w'):
        """record business registries to tsv, opened with file access mode: mode"""

        with open(path, mode) as file:
            file_writer = csv.writer(file, delimiter ="\t")

            for business in self.businesses:
                entry = [business.category, business.name, business.address,
                         business.city, business.zip, business.emp, business.sales,
                         business.cat_desc, business.bracket, business.lat, business.long,
                         business.confidence_score]

                file_writer.writerow(entry)

    def load_settings_from_cfg(self, path):
        # Set default values.
        cp = ConfigParser.ConfigParser({
                'kernel_shape_x': str(self.kernel_shape[0]),
                'kernel_shape_y': str(self.kernel_shape[1]),
                'thresh_value': str(self.thresh_value),
                'iterations': str(self.iterations),
                'columns_per_page': str(self.columns_per_page),
                'pages_per_image': str(self.pages_per_image),
                'bb_expansion_percent': str(self.bb_expansion_percent), 
                'indent_width': str(self.indent_width),
                'std_thresh': str(self.std_thresh),
            })
        cp.read(path)

        # Get values from config file.
        self.kernel_shape = (int(cp.get('RegistryProcessor','kernel_shape_x')),int(cp.get('RegistryProcessor','kernel_shape_y')))
        self.thresh_value = cp.getint('RegistryProcessor','thresh_value')
        self.iterations = cp.getint('RegistryProcessor','iterations')
        self.columns_per_page = cp.getint('RegistryProcessor','columns_per_page')
        self.pages_per_image = cp.getint('RegistryProcessor','pages_per_image')
        self.bb_expansion_percent = cp.getfloat('RegistryProcessor','bb_expansion_percent')
        self.indent_width = cp.getfloat('RegistryProcessor','indent_width')
        self.std_thresh = cp.getfloat('RegistryProcessor','std_thresh')

    def save_settings_to_cfg(self, path):
        cp = ConfigParser.SafeConfigParser()

        cp.add_section('RegistryProcessor')
        cp.set('RegistryProcessor','kernel_shape_x',str(self.kernel_shape[0]))
        cp.set('RegistryProcessor','kernel_shape_y',str(self.kernel_shape[1]))
        cp.set('RegistryProcessor','thresh_value',str(self.thresh_value))
        cp.set('RegistryProcessor','iterations',str(self.iterations))
        cp.set('RegistryProcessor','columns_per_page',str(self.columns_per_page))
        cp.set('RegistryProcessor','pages_per_image',str(self.pages_per_image))
        cp.set('RegistryProcessor','bb_expansion_percent',str(self.bb_expansion_percent))
        cp.set('RegistryProcessor','indent_width',str(self.indent_width))
        cp.set('RegistryProcessor','std_thresh',str(self.std_thresh))

        with open(path,'w') as cfg_file:
            cp.write(cfg_file)

    def _remove_edge_contours(self, contours):
        """remove contours that touch the edge of image
        and crops self._image and self._thresh to an
        appropriate size"""

        filtered_contours = []

        for contour in contours:
            if (contour.x == 1 or contour.x + contour.w == self._image_width - 1) or \
            (contour.y == 1 or contour.y + contour.h == self._image_height - 1):
                continue

            filtered_contours.append(contour)

        if len(filtered_contours) == 0:
            raise RuntimeError("No non-background contours found, check debug images")

        # create cropped version of image
        super_contour = np.concatenate([c.data for c in filtered_contours])
        [x,y,w,h] = cv2.boundingRect(super_contour)

        # make bounding box bigger
        x,y,w,h = self._expand_bb(x,y,w,h)

        self.__image = self.__image[y:y + h, x:x + w]
        self.__thresh_image = self.__thresh_image[y:y + h, x:x + w]

        # apply cropping offset to contours
        for c in contours:
            c.x -= x
            c.x_mid -= x
            c.y -= y
            c.y_mid -= y
            # apply cropping offset to each point in contours
            for p in c.data:
                p[0][0] -= x
                p[0][1] -= y

        return filtered_contours

    def _get_contours(self, make_new_thresh = True):
        """
        Performs a close operation to close gaps between letters to make solid contours,
        then performs an open operation to remove stray noise contours and returns the result
        :param make_new_thresh: if true this function will make a new thresh_image rather than using the existing self.__thresh_image
        :return: returns cv2 contour data (not wrapped in Contour() class)
        """

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, self.kernel_shape)

        if make_new_thresh: # if asked then we make a new thresh image
            if not self.assume_pre_processed:
                _,self.__thresh_image = cv2.threshold(self.__image, self.thresh_value, 255, cv2.THRESH_BINARY_INV) # threshold
            else:
                _,self.__thresh_image = cv2.threshold(self.__image, 0, 255, cv2.THRESH_BINARY_INV) # threshold with 0 threshold value

        # close operation to fill contours
        closed = cv2.morphologyEx(self.__thresh_image, cv2.MORPH_CLOSE, kernel, iterations = self.iterations)

        # perform an open operation to remove noise
        closed = cv2.morphologyEx(closed,cv2.MORPH_OPEN,kernel,iterations = self.iterations / 3)

        return cv2.findContours(closed,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[1] # actual contour data is the second element

    def _find_column_locations(self, contours):
        """find column column locations, and page boundary if two pages
        (returns column locations)"""

        # create array of coords for left and right edges of contours
        coords = [[contour.x, contour.x + contour.w] for contour in contours]
        coords_arr = np.array(coords)

        # use k-means clustering to get column boundaries for expected # of cols
        num_cols = self.columns_per_page * self.pages_per_image
        k_means = KMeans(n_clusters=num_cols)

        if len(coords_arr) < num_cols:
            raise RuntimeError("Number of contours detected fewer than number of expected columns")

        clustering = k_means.fit(coords_arr)

        self.page_boundary = -1
        if self.pages_per_image == 2:  # if there are two pages find the page boundary
            sorted_cols = sorted(clustering)
            self.page_boundary = (sorted_cols[self.columns_per_page - 1][0] +
                                  sorted_cols[self.columns_per_page][0]) / (2 * 1.0)

        # draw columns lines and clusters
        if self.draw_debug_images:
            # generate a different color for each cluster
            cluster_colors = [[x]*3 for x in np.linspace(0,255,num=num_cols+2)[1:-1]]

            # use left and right coords of clusters to draw columns
            canvas = self.__thresh_image.copy()
            for ix, column_l in enumerate(clustering.cluster_centers_):
                left, right = int(column_l[0]), int(column_l[1])
                cv2.line(canvas,(left, 0),(left,
                    self._image_height),cluster_colors[ix],20)
                cv2.line(canvas,(right, 0),(right,
                    self._image_height),cluster_colors[ix],20)

            # draw column lines to file
            cv2.imwrite(os.path.join(self.outdir, "column_lines.tiff"), canvas)

            # draw contour widths in color of assigned cluster
            canvas = self.__thresh_image.copy()
            for ix, contour in enumerate(contours):
                col = cluster_colors[clustering.labels_[ix]]
                left, right, y = contour.x, contour.x + contour.w, contour.y_mid
                cv2.circle(canvas,(left, y),20,col,35)
                cv2.circle(canvas,(right, y),20,col,35)
                cv2.line(canvas,(left, y),(right, y),col,10)

            # draw clustered column widths to file
            cv2.imwrite(os.path.join(self.outdir, "clusters.tiff"), canvas)

        return clustering

    def _make_contour_columns(self, contours, clustering):
        """makes contour columns based on column locations
           return: contour_columns, noncolumn_contours
           (column contours are sorted by column and position)"""

        column_contours = []
        non_column_contours = []

        # sort contours by clusters
        cluster_groups = sorted(zip(clustering.labels_, contours))

        # iterate through column groups, deciding which contours are valid
        for col_ix, cluster_group in itertools.groupby(cluster_groups, lambda x: x[0]):

            # coords of column
            col_loc = clustering.cluster_centers_[col_ix]

            cluster_contours = [c for _, c in cluster_group]

            # x-coords of contours
            contour_locs = [[c.x, c.x + c.w] for c in cluster_contours]
            # calculate standard deviation of contour x-coords
            col_std = np.std(contour_locs)

            # only keep contours if less than threshold std devs from column
            keep_contours = []
            for contour_ix, contour in enumerate(cluster_contours):
                dist = abs(np.linalg.norm(contour_locs[contour_ix] - col_loc))
                if dist < self.std_thresh * col_std:
                    keep_contours.append(contour)
                else:
                    non_column_contours.append(contour)

            column_contours.append(keep_contours)

        # sort column and contour by position
        sorted_column_contours = []
        sorted_columns = sorted(enumerate(column_contours),key=lambda x: 
                                 clustering.cluster_centers_[x[0]][0])
        for i, column in sorted_columns:
            sorted_column_contours.append(sorted(column,key=attrgetter('y')))

        return sorted_column_contours, non_column_contours