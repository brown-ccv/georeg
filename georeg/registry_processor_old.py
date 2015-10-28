import cv2
import re
import itertools
import os.path
import numpy as np
from operator import itemgetter, attrgetter

import registry_processor as reg
import business_geocoder as geo

class RegistryProcessorOld(reg.RegistryProcessor):

    def __init__(self):
        # init parent class
        reg.RegistryProcessor.__init__(self)
        self.__zip_pattern = re.compile(r'(?P<address>^.*)[\s]+(?P<zip>\d{5})[\s-]*')
        self.__emp_pattern = re.compile(r'[Ee]mp.*([A-Z])')

    def _process_image(self, path):
        """process a registry image from 1953-1975"""

        self._image = cv2.imread(path)

        _,contours,_ = self._get_contours(self.kernel_shape, self.iterations, True)
        contours = [reg.Contour(c) for c in contours]

        # remove noise from edge of image
        if not self.assume_pre_processed:
            contours = self._remove_edge_contours(contours)

        if self.draw_debug_images:
            canvas = np.zeros(self._image.shape,self._image.dtype)
            cv2.drawContours(canvas,[c.data for c in contours],-1,(255,255,255),-1)
            cv2.imwrite("closed.tiff",canvas)

        business_groups = self._sort_business_group_contours(contours)
        self.businesses = []

        current_city = ""
        current_zip = ""

        if len(business_groups) == 0:
            raise reg.RegistryProcessorException("error finding business groups in the document")

        contoured = None

        if self.draw_debug_images:
            contoured = self._image.copy()

        for header, business_group in business_groups:
            # make bounding box bigger
            x,y,w,h = self._expand_bb(header.x,header.y,header.w,header.h)

            if self.draw_debug_images:
                # draw bounding box on original image
                cv2.rectangle(contoured,(x,y),(x+w,y+h),(255,0,255),5)

            header_crop = self._thresh[y:y+h, x:x+w]
            header_str = self._ocr_image(header_crop)
            # remove surrounding quotes and newline chars
            header_str = re.sub(r'^"|\n|"$', ' ', header_str).strip()

            for business in business_group:
                # make bounding box bigger
                x,y,w,h = self._expand_bb(business.x,business.y,business.w,business.h)

                if self.draw_debug_images:
                    # draw bounding box on original image
                    cv2.rectangle(contoured,(x,y),(x+w,y+h),(255,0,255),5)

                # ocr the contour
                cropped = self._thresh[y:y+h, x:x+w]
                contour_txt = self._ocr_image(cropped)

                if contour_txt.count("\n") > 0: # if the contour's text has 2 or more lines consider it a registry
                    business = self._parse_registry_block(contour_txt)
                    business.category = header_str
                    if len(current_city) > 0:
                        business.city = current_city
                    else:
                        business.manual_inspection = True
                    if len(current_zip) > 0:
                        business.zip = current_zip

                    geo.geocode_business(business)
                    self.businesses.append(business)
                else: # check if city header
                    segments = contour_txt.rpartition(" ")
                    zip = ""

                    # check if zip is in header
                    if segments[2].isdigit() and len(segments[2]) == 5:
                        zip = segments[2]
                        contour_txt = segments[0]

                    matches = self._city_detector.match_to_cities(contour_txt)

                    if len(matches) > 0:
                        current_city = matches[0]
                        current_zip = zip

        if self.draw_debug_images:
            # write original image with added contours to disk
            cv2.imwrite("contoured.tiff", contoured)

            # save a second copy that won't be overriden
            cv2.imwrite(os.path.splitext(path)[0] + "-contoured.tiff", contoured)

    def _parse_registry_block(self, registry_txt):
        """works for registries from 1953-1975"""
        # NOTE: this function was made before
        # I knew how to take advantage of regular expressions

        business = reg.Business()

        lines = registry_txt.split("\n")

        # get name
        business.name = lines[0]
        address_line = lines[1]

        match = self.__zip_pattern.search(address_line)
        if match:
            business.zip = match.group("zip")
            address_line = match.group("address")

        business.address = address_line

        match = self.__emp_pattern.search(registry_txt)
        if match:
            business.emp = match.group(0)[-1]

        # if the city is an empty string or employment is unkown mark for manual inspection
        if len(business.emp) == 0: # or not words[0].isdigit():
            business.manual_inspection = True

        return business

    # IMPORTANT NOTE: this function will need to be reworked if it needs to be used on registry formats
    # that have more than 2 columns per page
    def _find_headers(self, contours, column_locations, page_boundary):
        """find business description headers in non-column contours
        (returns headers sorted by position)"""

        header_contours = []
        non_header_contours = []

        # column locations used for finding headers
        header_columns = []

        # iterate through column pairs (mostly likely only one pair per page)
        for i in range(0, len(column_locations) / 2):
            left_column = column_locations[i*2]
            right_column = column_locations[i*2+1]

            # create an intermediate column representing the whitespace
            # between the left and right columns of this page
            header_columns.append(reg.Column_Location())
            header_columns[-1].x = ((left_column.x + left_column.w / 2) + (right_column.x - right_column.w / 2)) / 2
            header_columns[-1].w = (right_column.x - right_column.w / 2) - (left_column.x + left_column.w / 2)

        # sometimes there are no header columns when the image is too blurry
        # and very little text makes it through the threshold operation
        if len(header_columns) == 0:
            raise reg.RegistryProcessorException("unable to detect business category headers")

        # assign contours to columns (or designate as headers)
        for c in contours:
            # check if it matches either header column
            if header_columns[0].match_ratio(c) >= self.match_rate or \
            (len(header_columns) > 1 and header_columns[1].match_ratio(c) >= self.match_rate):
                header_contours.append(c)
            else:
                non_header_contours.append(c)

        # remove noise from headers
        highest_width = reduce(lambda h_w, hdr: max([h_w, hdr.w]), header_contours, 0)
        header_contours = [h for h in header_contours if h.w / (highest_width * 1.0) >= 0.2] # all headers that are not atleast 1/5 the width of the widest header are removed

        if len(header_contours) == 0:
            raise reg.RegistryProcessorException("unable to detect business category headers")

        # sort headers by position
        header_contours = sorted([h for h in header_contours if h.x < page_boundary or page_boundary == -1],key=attrgetter('y')) + \
                          sorted([h for h in header_contours if h.x >= page_boundary and page_boundary != -1],key=attrgetter('y'))


        if self.draw_debug_images:
            canvas = self._thresh.copy()
            for c in header_contours:
                cv2.circle(canvas,(c.x_mid,c.y_mid),20,(255,255,255),35)
            cv2.imwrite("headers.tiff", canvas)

        return header_contours, non_header_contours

    def _sort_business_group_contours(self, contours):
        """sort all registry contours in the image based on their business group and position"""

        column_locations, page_boundary = self._find_column_locations(contours)

        on_first_page = lambda c: page_boundary == -1 or c.x < page_boundary
        on_same_page = lambda c1,c2: on_first_page(c1) == on_first_page(c2)

        # seperate headers from columns
        header_contours, non_header_contours = self._find_headers(contours, column_locations, page_boundary)
        column_contours, _ = self._assemble_contour_columns(non_header_contours, column_locations)

        business_groups = []

        # # number of header segments encountered in a row
        # num_header_segments = 0

        # put non-headers (business registries) into business groups
        for i, header in enumerate(header_contours):
            next_header = None

            # if there is a next header give next_header a value
            if i + 1 < len(header_contours):
                next_header = header_contours[i+1]

            column_start = None
            column_end = None

            if on_first_page(header):
                column_start = 0
                column_end = self.columns_per_page
            else:
                column_start = self.columns_per_page
                column_end = self.columns_per_page * 2

            # if next header exists and is on same page: True
            nxt_hdr_on_same_page = next_header and on_same_page(header,next_header)

            bus_group_columns = [] # contains registries
            for i in range(0, self.columns_per_page):
                bus_group_columns.append([])

            for i, column in enumerate(column_contours[column_start:column_end]):
                for registry in column:
                    if registry.y > header.y and (not nxt_hdr_on_same_page or registry.y < next_header.y):
                        bus_group_columns[i].append(registry)

            # # if this business group contained no registries it is likely
            # # that we got one piece of a segmented header
            # if len(bus_group_columns[0]) == 0 and len(bus_group_columns[1]) == 0:
            #     num_header_segments += 1
            #     continue
            # elif num_header_segments > 0:
            #     new_header_str = ""
            #
            #     for x in len(-num_header_segments,0):
            #         header_strings

            business_groups.append(itertools.chain.from_iterable(bus_group_columns))

        return zip(header_contours, business_groups)
