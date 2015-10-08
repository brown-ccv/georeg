# coding=utf-8
import cv2
import numpy as np
import tempfile
import difflib
import re
import os
import csv
import sys
import subprocess
import ConfigParser
from operator import itemgetter, attrgetter

import georeg

_datadir = os.path.join(georeg.__path__[0], "data")

class CityDetector:
    """loads a file of cities for comparison against strings"""
    def __init__(self):
        self.city_list = []
    def load_cities(self, file_name):
        self.city_list = [] # clear old values

        with open(file_name) as file:
            for line in file:
                line = line.strip()
                self.city_list.append(line)

    def match_to_cities(self, line, cutoff = 0.6):
        line = line.lower().strip()

        # '—' not easily expressed in ascii
        em_dash = '\xe2\x80\x94'

        # if the end of the string matches "—continued" then remove it
        if len(difflib.get_close_matches(line[-12:], [em_dash + "continued"], cutoff=cutoff)) > 0:
            line = line[:-12]

        match_list = difflib.get_close_matches(line, self.city_list, cutoff = cutoff)
        return match_list

class Business:
    def __init__(self):
        self.name = ""
        self.city = ""
        self.zip = ""
        self.address = ""
        self.category = "" # business category or sic code depending on year
        self.emp = "" # employment

        # coordinates
        self.lat = ""
        self.long = ""
        self.confidence_score = 0.0

        self.manual_inspection = False

class Contour:
    def __init__(self, contour = None):
        self.data = contour
        
        if contour is not None:
            [self.x,self.y,self.w,self.h] = cv2.boundingRect(contour)
            self.x_mid = self.x + self.w / 2
            self.y_mid = self.y + self.h / 2
        else:
            self.x = 0
            self.y = 0
            self.w = 0
            self.h = 0
    
            self.x_mid = 0
            self.y_mid = 0

class Column_Location:
    def __init__(self):
        self.x = 0
        self.w = 0
    def match_ratio(self, contour):
        clamp = lambda n, minn, maxn: min(max(n, minn), maxn)

        # find out how far the contours stretches to the left and right relative to the column
        left_side_weight = ((self.x - self.w / 2) - contour.x) / (contour.w * 1.0)
        right_side_weight = ((contour.x + contour.w) - (self.x + self.w / 2)) / (contour.w * 1.0)

        # clamp the weights between 0 and 1
        left_side_weight = clamp(left_side_weight, 0, 1)
        right_side_weight = clamp(right_side_weight, 0, 1)

        # the penalty is the percent of the contour that is unevenly distributed to one side of the column
        return 1.0 - abs(left_side_weight - right_side_weight)

# a special exception class for exceptions generated by registry processor and child classes
class RegistryProcessorException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value

class RegistryProcessor:
    def __init__(self):
        self._image = None
        self._image_height = lambda: self._image.shape[0]
        self._image_width = lambda: self._image.shape[1]
        self._thresh = None

        # image processing parameters (these are example values)
        self.kernel_shape = (10,3)
        self.thresh_value = 60 # higher = more exposure (max = 255)
        self.iterations = 8
        self.match_rate = 0.7 # lower = more lenient

        # percent of image width and height to add to bounding box width and height of contours (improves ocr accuracy)
        # higher = bigger bounding box
        self.bb_expansion_percent = 0.012

        self._expand_bb = lambda x,y,w,h: (x - int(round(self._image_width() * self.bb_expansion_percent / 2.0)), \
                                           y - int(round(self._image_height() * self.bb_expansion_percent / 2.0)), \
                                           w + int(round(self._image_width() * self.bb_expansion_percent)), \
                                           h + int(round(self._image_height() * self.bb_expansion_percent)))

        self.columns_per_page = 2
        self.pages_per_image = 1

        # 0 = discard least likely candidates,
        # 1 = first discard leftmost extra candidate then act like 0,
        # 2 = first discard rightmost extra candidate then act like 0
        self.discard_extra_column_behavior = 0

        self.draw_debug_images = False # turning this on can help with debugging
        self.assume_pre_processed = False # assume images are preprocessed so to not waste extra computational power

        self.businesses = []
        self.__tmp_path = tempfile.mktemp(suffix=".tiff")

        # city lookup
        self._city_detector = CityDetector()
        self._city_detector.load_cities(os.path.join(_datadir, "RI-cities.txt"))


    def __del__(self):
        # clean up our temp files
        if os.path.isfile(self.__tmp_path):
            os.remove(self.__tmp_path)
        if os.path.isfile(self.__tmp_path + ".txt"):
            os.remove(self.__tmp_path + ".txt")

    def process_image(self, path):
        """this is a wrapper for _process_image() which catches exceptions and reports them"""
        try:
            self._process_image(path)
        except RegistryProcessorException as e:
            print >>sys.stderr, "error: %s, skipping" % e

    # NOTE: this needs to be implemented in child classes
    def _process_image(self, path):
        """process a registry image and store results in the businesses member,
        don't call this directly call process_image() instead"""

    def load_from_tsv(self, path):
        """load self.businesses from a tsv file where they were previously saved"""

        manual_inspec_path = os.path.splitext(path)[0] + "_manual_inspection.tsv"

        self.businesses = []

        # mini function for loading an individual business file (normal or manual inspection)
        def load_businesses(path, manual_inspection):
            with open(path, "r") as file:
                file_reader = csv.reader(file, delimiter="\t")
                for row in file_reader:
                    business = Business()
                    business.manual_inspection = manual_inspection

                    [business.category, business.name, business.city,
                     business.address, business.zip, business.emp,
                     business.lat, business.long, business.confidence_score] = row

                    # cast to float
                    business.confidence_score = float(business.confidence_score)

                    self.businesses.append(business)

        # load normal businesses
        load_businesses(path, False)

        # load manual inspection businesses
        if os.path.isfile(manual_inspec_path):
            load_businesses(manual_inspec_path, True)

    def record_to_tsv(self, path, mode = 'w'):
        """record business registries to tsv, opened with file access mode: mode"""

        with open(path, mode) as file:
            file_writer = csv.writer(file, delimiter ="\t")

            # open a file for dumping registries that require manual inspection
            manual_inspec_path = os.path.splitext(path)[0] + "_manual_inspection.tsv"
            manual_inspection_file = None
            manual_inspection_writer = None

            for business in self.businesses:
                entry = [business.category, business.name, business.city,
                         business.address, business.zip, business.emp,
                         business.lat, business.long, business.confidence_score]

                if business.manual_inspection:
                    # if manual inspection file not opened yet open now
                    if not manual_inspection_file:
                        manual_inspection_file = open(manual_inspec_path, mode)
                        manual_inspection_writer = csv.writer(manual_inspection_file, delimiter="\t")

                    manual_inspection_writer.writerow(entry)
                else: file_writer.writerow(entry)

            if manual_inspection_file:
                manual_inspection_file.close()

    def load_settings_from_cfg(self, path):
        # remove exenstion
        path = os.path.splitext(path)[0]

        cp = ConfigParser.ConfigParser()
        cp.read(path + '.cfg')

        self.kernel = (int(cp.get('RegistryProcessor','kernel_shape_x')),int(cp.get('RegistryProcessor','kernel_shape_y')))
        self.thresh_value = int(cp.get('RegistryProcessor','thresh_value'))
        self.iterations = int(cp.get('RegistryProcessor','iterations'))
        self.match_rate = float(cp.get('RegistryProcessor','match_rate'))
        self.columns_per_page = int(cp.get('RegistryProcessor','columns_per_page'))
        self.pages_per_image = int(cp.get('RegistryProcessor','pages_per_image'))
        self.discard_extra_column_behavior = int(cp.get('RegistryProcessor','discard_extra_column_behavior'))
        self.bb_expansion_percent = float(cp.get('RegistryProcessor','bb_expansion_percent'))

    def save_settings_to_cfg(self, path):
        # remove exenstion
        path = os.path.splitext(path)[0]

        cp = ConfigParser.SafeConfigParser()

        cp.add_section('RegistryProcessor')
        cp.set('RegistryProcessor','kernel_shape_x',str(self.kernel_shape[0]))
        cp.set('RegistryProcessor','kernel_shape_y',str(self.kernel_shape[1]))
        cp.set('RegistryProcessor','thresh_value',str(self.thresh_value))
        cp.set('RegistryProcessor','iterations',str(self.iterations))
        cp.set('RegistryProcessor','match_rate',str(self.match_rate))
        cp.set('RegistryProcessor','columns_per_page',str(self.columns_per_page))
        cp.set('RegistryProcessor','pages_per_image',str(self.pages_per_image))
        cp.set('RegistryProcessor','discard_extra_column_behavior',str(self.discard_extra_column_behavior))
        cp.set('RegistryProcessor','bb_expansion_percent',str(self.bb_expansion_percent))

        with open(path + '.cfg','w') as cfg_file:
            cp.write(cfg_file)

    def _remove_edge_contours(self, contours):
        """remove contours that touch the edge of image
        and crops self._image and self._thresh to an
        appropriate size"""

        filtered_contours = []

        for contour in contours:
            if (contour.x == 1 or contour.x + contour.w == self._image_width() - 1) or \
            (contour.y == 1 or contour.y + contour.h == self._image_height() - 1):
                continue

            filtered_contours.append(contour)

        if len(filtered_contours) == 0:
            raise RegistryProcessorException("No non-background contours found, check debug images")

        # create cropped version of
        super_contour = np.concatenate([c.data for c in filtered_contours])
        [x,y,w,h] = cv2.boundingRect(super_contour)

        # make bounding box bigger
        x,y,w,h = self._expand_bb(x,y,w,h)

        self._image = self._image[y:y+h,x:x+w]
        self._thresh = self._thresh[y:y+h,x:x+w]

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

    def _get_contours(self, kernel_shape, iter, make_new_thresh = True):
        """performs a close operation on self._image then extracts the contours"""

        if make_new_thresh: # if thresh_value is provided then we make a new thresh image
            if not self.assume_pre_processed:
                _,self._thresh = cv2.threshold(self._image,self.thresh_value,255,cv2.THRESH_BINARY_INV) # threshold
            else:
                _,self._thresh = cv2.threshold(self._image,0,255,cv2.THRESH_BINARY_INV) # threshold with 0 threshold value

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT,kernel_shape)
        closed = cv2.morphologyEx(self._thresh,cv2.MORPH_CLOSE,kernel,iterations = iter) # close

        # perform a small open operation to remove noise
        closed = cv2.morphologyEx(closed,cv2.MORPH_OPEN,kernel,iterations = iter / 3)

        return cv2.findContours(closed,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE) # get contours

    #TODO: make this function call tesseract directly through python api to reduce overhead
    def _ocr_image(self, image):
        """use tesseract to ocr a black and white image and return the text"""
        # write image to file
        cv2.imwrite(self.__tmp_path, image)

        # call tesseract on image
        # (Popen with piped streams hides tesseract output)
        p = subprocess.Popen(["tesseract", self.__tmp_path, self.__tmp_path, "-psm", "6"], stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        p.wait()

        contour_txt = ""

        for line in open(self.__tmp_path + ".txt"):
            if not re.match(r'^\s*$', line):
                contour_txt = contour_txt + line

        return contour_txt.strip()

    def _find_column_locations(self, contours):
        """find column column locations sorted by position, and page boundary if two pages
        (returns column locations sorted by position)"""

        # helper class for a column candidate
        class Candidate:
            def __init__(self, contour = Contour()):
                self.count = 1
                self.x_total = contour.x_mid
                self.w_total = contour.w
                self.col = Column_Location() # contains an actual column location class for easy returning
                self.col.x = contour.x_mid
                self.col.w = contour.w

        column_candidate_pool = []

        # find column positions
        for contour in contours:
            match_found = False
            # incorporate this registry in the candidate pool
            for candidate in column_candidate_pool:
                match_rate = candidate.col.match_ratio(contour)
                if  match_rate >= self.match_rate: # this does match a candidate and will be averaged in
                    candidate.count += 1
                    match_found = True

                    # update totals
                    candidate.x_total += contour.x_mid
                    candidate.w_total += contour.w

                    # update running averages
                    candidate.col.x = candidate.x_total / candidate.count
                    candidate.col.w = candidate.w_total / candidate.count
                    break

            if not match_found: # this does not fit any other candidate and will become its own
                column_candidate_pool.append(Candidate(contour))

        # there should be atleast enough candidates to constitute the required number of pages
        if len(column_candidate_pool) < self.columns_per_page * self.pages_per_image:
            raise RegistryProcessorException("not enough column candidates to constitute a page")

        # remove blatant noise columns
        highest_count = reduce(lambda h_c,i: max(h_c,i.count),column_candidate_pool,0)
        column_candidate_pool = [c for c in column_candidate_pool if c.count / (highest_count * 1.0) >= 0.4]

        num_extra_columns = len(column_candidate_pool) - self.columns_per_page * self.pages_per_image

        # if there are extra columns in the image remove them
        if num_extra_columns > 0:

            if self.discard_extra_column_behavior == 1:
                # sort candidates based on position
                column_candidate_pool = sorted(column_candidate_pool, key=attrgetter('col.x'))
                column_candidate_pool = column_candidate_pool[1:] # remove leftmost candidate

                num_extra_columns -= 1
            elif self.discard_extra_column_behavior == 2:
                # sort candidates based on position
                column_candidate_pool = sorted(column_candidate_pool, key=attrgetter('col.x'))
                column_candidate_pool = column_candidate_pool[:-1] # remove rightmost candidate

                num_extra_columns -= 1

            if num_extra_columns > 0: # if there are more extra columns, remove least likely (lowest count)
                # sort columns by count ascending
                column_candidate_pool = sorted(column_candidate_pool,key=attrgetter('count'))
                column_candidate_pool = column_candidate_pool[num_extra_columns:] # remove remaining extra columns from lowest count

        # extract column locations from candidate pool, and sort by position
        column_locations = [c.col for c in column_candidate_pool]
        column_locations = sorted(column_locations,key=attrgetter('x'))

        page_boundary = -1
        if self.pages_per_image == 2: # if there are two pages find the page boundary
            page_boundary = (column_locations[self.columns_per_page - 1].x + column_locations[self.columns_per_page].x) / (2 * 1.0)

        # draw columns lines
        if self.draw_debug_images:
            canvas = self._thresh.copy()
            grey = (150,150,150)

            # draw column lines
            for column_l in column_locations:
                cv2.line(canvas,(column_l.x - column_l.w / 2, 0),(column_l.x - column_l.w / 2, self._image_height()),grey,20)
                cv2.line(canvas,(column_l.x + column_l.w / 2, 0),(column_l.x + column_l.w / 2, self._image_height()),grey,20)

            # draw column lines to file
            cv2.imwrite("column_lines.tiff", canvas)

        return column_locations, page_boundary

    def _assemble_contour_columns(self, contours, column_locations):
        """assemble contours into columns and seperate those that
        dont belong to a column (returns contours sorted by position)"""

        column_contours = []
        non_column_contours = []

        for i in range(0,len(column_locations)):
            column_contours.append([])

        # assign contours to columns (or designate as headers)
        for c in contours:
            match_found = False

            # match to a column
            for i, column_l in enumerate(column_locations):
                if column_l.match_ratio(c) >= self.match_rate: # check if part of the column
                    column_contours[i].append(c)
                    match_found = True
                    break

            if not match_found:
                non_column_contours.append(c)

        # sort by position
        for i, column in enumerate(column_contours):
            column_contours[i] = sorted(column,key=attrgetter('y'))

        return column_contours, non_column_contours
