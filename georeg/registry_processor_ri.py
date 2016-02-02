""" Processes industrial registries from Rhode Island."""

import cv2
import itertools
import os.path
import re
import numpy as np
import registry_processor as reg
import business_geocoder as geo
from operator import itemgetter, attrgetter

import registry_processor as reg
import business_geocoder as geo

class RegistryProcessorNew(reg.RegistryProcessor):
    """1975-present RI registry parser."""
    
    def __init__(self, *args, **kwargs):
        super(RegistryProcessorNew, self).__init__(*args, **kwargs)
         
        self.current_sic = ""

        self.city_pattern = re.compile(r'[A-Za-z]+[\s]{0,2}[A-Za-z]*(?=[,.][\s]+[A-Z]{2})')
        self.emp_pattern = re.compile(r'[Ee]mp.*\d+')
        self.registry_pattern = re.compile(r'[A-Za-z]+.*\n',)
        self.sic_pattern = re.compile(r'\d{4}')

    def _process_contour(self, contour_txt):
        registry_match = self.registry_pattern.match(contour_txt)
        sic_match = self.sic_pattern.match(contour_txt)

        if registry_match:
            business = self._parse_registry_block(contour_txt)
            business.category = self.current_sic

            geo.geocode_business(business)
            self.businesses.append(business)
        elif sic_match:
            self.current_sic = sic_match.group(0)


    def _parse_registry_block(self, registry_txt):
        """works for registries from 1975-onward"""
        business = reg.Business()

        lines = registry_txt.split("\n")

        business.name = lines[0]
        business.address = lines[1]

        match = self.city_pattern.search(registry_txt)
        if match:
            city = match.group(0)
            matches = self._city_detector.match_to_cities(city) # perform spell check and confirm this is a city
            if len(matches) > 0:
                business.city = matches[0]

        match = self.emp_pattern.search(registry_txt)
        if match:
            match = re.search(r"\d+",match.group(0))
            if match:
                business.emp = match.group(0)

        return business


class RegistryProcessorOld(reg.RegistryProcessor):
    """Pre-1975 RI registry parser."""

    def __init__(self, *args, **kwargs):
        super(RegistryProcessorOld, self).__init__(*args, **kwargs)

        self.zip_pattern = re.compile(r'(?P<address>^.*)[\s]+(?P<zip>\d{5})[\s-]*')
        self.emp_pattern = re.compile(r'[Ee]mp.*([A-Z])')

        self.current_city = ""
        self.current_zip = ""

        self.line_color = (130,130,130)

    def _process_image(self, path):
        """process a registry image from 1953-1975"""

        self.businesses = [] # reset businesses list

        self._image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)

        _,contours,_ = self._get_contours(self.kernel_shape, self.iterations, True)
        contours = [reg.Contour(c) for c in contours]

        # remove noise from edge of image
        if not self.assume_pre_processed:
            contours = self._remove_edge_contours(contours)

        if self.draw_debug_images:
            canvas = np.zeros(self._image.shape,self._image.dtype)
            cv2.drawContours(canvas,[c.data for c in
                contours],-1,self.line_color,-1)
            cv2.imwrite("closed.tiff",canvas)

        business_groups = self._sort_business_group_contours(contours)

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
                cv2.rectangle(contoured,(x,y),(x+w,y+h),self.line_color,5)

            header_crop = self._thresh[y:y+h, x:x+w]
            header_str = self._ocr_image(header_crop)
            # remove surrounding quotes and newline chars
            header_str = re.sub(r'^"|\n|"$', ' ', header_str).strip()

            for business in business_group:
                # make bounding box bigger
                x,y,w,h = self._expand_bb(business.x,business.y,business.w,business.h)

                if self.draw_debug_images:
                    # draw bounding box on original image
                    cv2.rectangle(contoured,(x,y),(x+w,y+h),self.line_color,5)

                # ocr the contour
                cropped = self._thresh[y:y+h, x:x+w]
                contour_txt = self._ocr_image(cropped)

                if contour_txt.count("\n") > 0: # if the contour's text has 2 or more lines consider it a registry
                    business = self._parse_registry_block(contour_txt)
                    business.category = header_str
                    if len(self.current_city) > 0:
                        business.city = self.current_city
                    if len(self.current_zip) > 0:
                        business.zip = self.current_zip
                    
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
                        self.current_city = matches[0]
                        self.current_zip = zip

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

        match = self.zip_pattern.search(address_line)
        if match:
            business.zip = match.group("zip")
            address_line = match.group("address")

        business.address = address_line

        match = self.emp_pattern.search(registry_txt)
        if match:
            business.emp = match.group(0)[-1]

        return business

    def _find_headers(self, header_contours, column_locations, page_boundary):
        """find business description headers in non-column contours
        (returns headers sorted by position)"""

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
                cv2.circle(canvas,(c.x_mid,c.y_mid),20,self.line_color,35)
            cv2.imwrite("headers.tiff", canvas)

        return header_contours

    def _sort_business_group_contours(self, contours):
        """sort all registry contours in the image based on their business group and position"""

        clustering = self._find_column_locations(contours)
        column_locations = clustering.cluster_centers_

        # calculate page boundary
        page_boundary = -1
        if self.pages_per_image == 2: # if there are two pages find the page boundary
            sorted_cols = sorted(column_locations)
            page_boundary = (sorted_cols[self.columns_per_page - 1][0] +
                             sorted_cols[self.columns_per_page][0]) / (2 * 1.0)

        on_first_page = lambda c: page_boundary == -1 or c.x < page_boundary
        on_same_page = lambda c1,c2: on_first_page(c1) == on_first_page(c2)

        # seperate headers from columns
        column_contours, non_column_contours = self._assemble_contour_columns(contours, clustering)
        header_contours = self._find_headers(non_column_contours, column_locations, page_boundary)

        business_groups = []

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

            business_groups.append(itertools.chain.from_iterable(bus_group_columns))

        return zip(header_contours, business_groups)
