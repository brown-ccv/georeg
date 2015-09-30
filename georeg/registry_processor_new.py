import cv2
import re
import itertools
import numpy as np
import registry_processor as reg
import business_geocoder as geo

class RegistryProcessorNew(reg.RegistryProcessor):
    def __init__(self):
        # init parent class
        reg.RegistryProcessor.__init__(self)
        self.__city_pattern = re.compile(r'[A-Za-z]+[ \t]{0,2}[A-Za-z]*(?=[,.][ \t]+(RI|AI))')
        self.__emp_pattern = re.compile(r'[Ee]mp.*\d+')

    def _process_image(self, path):
        """process a registry image from 1971-onward"""

        self._image = cv2.imread(path)

        _,contours,_ = self._get_contours(self.kernel_shape, self.iterations, True)
        contours = [reg.Contour(c) for c in contours]

        # remove noise from edge of image
        if not self.assume_pre_processed:
            contours = self._remove_edge_contours(contours)

        if self.draw_debug_images:
            canvas = np.zeros(self._image.shape,self._image.dtype)
            cv2.drawContours(canvas,[c.data for c in contours],-1,(255,255,255),-1)
            cv2.imwrite("./testdata/closed.tiff",canvas)

        column_locations, page_boundary = self._find_column_locations(contours)
        columns, _ = self._assemble_contour_columns(contours, column_locations)
        contours = list(itertools.chain.from_iterable(columns))

        self.businesses = []

        contoured = None

        if self.draw_debug_images:
            contoured = self._image.copy()

        current_sic = ""

        registry_pattern = re.compile(r'[A-Za-z]+.*\n',)
        sic_pattern = re.compile(r'\d{4}')

        for contour in contours:
            x,y,w,h = self._expand_bb(contour.x,contour.y,contour.w,contour.h)

            if self.draw_debug_images:
                # draw bounding box on original image
                cv2.rectangle(contoured,(x,y),(x+w,y+h),(255,0,255),5)

            cropped = self._thresh[y:y+h, x:x+w]
            contour_txt = self._ocr_image(cropped)

            registry_match = registry_pattern.match(contour_txt)
            sic_match = sic_pattern.match(contour_txt)

            if registry_match:
                business = self._parse_registry_block(contour_txt)
                business.category = current_sic

                geo.geocode_business(business)
                self.businesses.append(business)
            elif sic_match:
                current_sic = sic_match.group(0)

        if self.draw_debug_images:
            # write original image with added contours to disk
            cv2.imwrite("./testdata/contoured.tiff", contoured)

    def _parse_registry_block(self, registry_txt):
        """works for registries from 1979-onward"""
        business = reg.Business()

        lines = registry_txt.split("\n")

        business.name = lines[0]
        business.address = lines[1]

        match = self.__city_pattern.search(registry_txt)
        if match:
            city = match.group(0)
            matches = self._city_detector.match_to_cities(city) # perform spell check and confirm this is a city
            if len(matches) > 0:
                business.city = matches[0]

        match = self.__emp_pattern.search(registry_txt)
        if match:
            match = re.search(r"\d+",match.group(0))
            if match:
                business.emp = match.group(0)

        # if the city is an empty string or employment is unkown mark for manual inspection
        if len(business.city) == 0 or len(business.emp) == 0:
            business.manual_inspection = True

        return business
