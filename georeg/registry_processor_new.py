import cv2
import re
import numpy as np
import registry_processor as reg
import business_geocoder as geo

class RegistryProcessorNew(reg.RegistryProcessor):
    
    def __init__(self):
        super(RegistryProcessorNew, self).__init__(state="RI")
         
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
