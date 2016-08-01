""" Processes industrial registries from Rhode Island."""

import cv2
import itertools
import os.path
import re
import numpy as np
import registry_processor as reg
import business_geocoder as geo
from operator import itemgetter, attrgetter

class RegistryProcessorNew(reg.RegistryProcessor):
    """1975-present RI registry parser."""
    
    def __init__(self):
        super(RegistryProcessorNew, self).__init__()
         
        self.current_sic = ""

        self.city_pattern = re.compile(r'[A-Za-z ]+(?=[,.][ ]+[A-Z]{2}[ ]+[0-9]{5})')
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
            return business
        elif sic_match:
            self.current_sic = sic_match.group(0)
        return None


    def _parse_registry_block(self, registry_txt):
        """works for registries from 1975-onward"""
        business = reg.Business()

        lines = registry_txt.split("\n")

        business.name = lines[0]
        business.address = lines[1]

        match = self.city_pattern.search(registry_txt)
        if match:
            city = match.group(0)
            match_city = self._city_detector.match_to_cities(city) # perform spell check and confirm this is a city
            if match_city:
                if match_city != city:
                    print("Imperfect city match: %s matched to %s" % (city, match_city))
                business.city = match_city

        match = self.emp_pattern.search(registry_txt)
        if match:
            match = re.search(r"\d+",match.group(0))
            if match:
                business.emp = match.group(0)

        return business

class RegistryRecorder(RegistryProcessorNew):
    def __init__(self):
        super(RegistryRecorder, self).__init__()

        self.bus_start_token = "<BUS_START>"
        self.bus_end_token = "<BUS_END>"

        self.name_start_token = "<NAME_START>"
        self.bus_type_start_token = "<BUS_TYPE_START>"
        self.address_start_token = "<ADDRESS_START>"

        self.end_token = "<FIELD_END>"

        self.registry_txt = ""

    def _process_contour(self, contour_txt):
        """works for registries from 1975-onward"""

        registry_match = self.registry_pattern.match(contour_txt)
        sic_match = self.sic_pattern.match(contour_txt)

        if registry_match and not sic_match:
            lines = contour_txt.split("\n")

            if len(lines) < 2:
                return None

            lines[0] = self.name_start_token + " " + lines[0] + " " + self.end_token
            lines[1] = self.address_start_token + " " + lines[1] + " " + self.end_token

            self.registry_txt += "\n" + self.bus_start_token + "\n"
            self.registry_txt += " ".join(lines)
            self.registry_txt += "\n" + self.bus_end_token + "\n"

        return None
    def record_to_tsv(self, path, mode='w'):
        with open(path, mode) as file:
            file.write(self.registry_txt)

class RegistryProcessorOld(reg.RegistryProcessor):
    """Pre-1975 RI registry parser."""

    def __init__(self):
        super(RegistryProcessorOld, self).__init__()

        self.zip_pattern = re.compile(r'(?P<address>^.*)[\s]+(?P<zip>\d{5})[\s-]*')
        self.emp_pattern = re.compile(r'[Ee]mp.*([A-Z])')

        self.current_city = ""
        self.current_zip = ""

        self.line_color = (130,130,130)

    def _process_contour(self, contour_txt, header_str):
        if contour_txt.count("\n") > 0:  # if the contour's text has 2 or more lines consider it a registry
            business = self._parse_registry_block(contour_txt)
            business.category = header_str
            if len(self.current_city) > 0:
                business.city = self.current_city
            if len(self.current_zip) > 0:
                business.zip = self.current_zip

            geo.geocode_business(business)
            return business
        else:  # check if city header
            segments = contour_txt.rpartition(" ")
            zip = ""

            # check if zip is in header
            if segments[2].isdigit() and len(segments[2]) == 5:
                zip = segments[2]
                contour_txt = segments[0]

            match_city = self._city_detector.match_to_cities(contour_txt)

            if match_city:
                self.current_city = match_city
                self.current_zip = zip
        return None

    def _parse_registry_block(self, registry_txt):
        """works for registries from 1953-1975"""

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

    def _get_noncolumn_contours_of_interest(self, noncolumn_contours):
        """Here we tell the base class which non-column contours are important,
           in our case it is the business description headers (headers get sorted by position)"""

        # remove noise from headers
        highest_width = reduce(lambda h_w, hdr: max([h_w, hdr.w]), noncolumn_contours, 0)

        # all headers that are not atleast 1/5 the width of the widest header are removed
        header_contours = [h for h in noncolumn_contours if h.w / (highest_width * 1.0) >= 0.2]

        if len(header_contours) == 0:
            raise reg.RegistryProcessorException("unable to detect business category headers")

        # sort headers by position
        header_contours = sorted([h for h in header_contours if h.x < self.page_boundary or self.page_boundary == -1],
                                    key=attrgetter('y')) + \
                          sorted([h for h in header_contours if h.x >= self.page_boundary and self.page_boundary != -1],
                                    key=attrgetter('y'))

        if self.draw_debug_images:
            canvas = self._thresh.copy()
            for c in header_contours:
                cv2.circle(canvas, (c.x_mid, c.y_mid), 20, self.line_color, 35)
            reg.cv2_imwrite_safe("headers.tiff", canvas)

        return header_contours

    def _define_contour_call_args(self, column_contours, noncolumn_contours):
        business_groups = self._get_sorted_business_groups(column_contours, noncolumn_contours)

        if len(business_groups) == 0:
            raise reg.RegistryProcessorException("error finding business groups in the document")

        call_args = []

        for header, business_group in business_groups:
            # remove surrounding quotes and newline chars
            header.text = re.sub(r'^"|\n|"$', ' ', header.text).strip()

            for business in business_group:
                call_args.append((business.text,header.text))

        return call_args

    def _get_sorted_business_groups(self, column_contours, header_contours):
        """sort all registry contours in the image based on their business group and position"""

        on_first_page = lambda c: self.page_boundary == -1 or c.x < self.page_boundary
        on_same_page = lambda c1,c2: on_first_page(c1) == on_first_page(c2)

        business_groups = []

        # put non-headers (business registries) into business groups
        for i, header in enumerate(header_contours):
            next_header = None

            # if there is a next header give next_header a value
            if i + 1 < len(header_contours):
                next_header = header_contours[i+1]

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