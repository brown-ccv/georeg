import registry_processor_new as regnew


class RegistryProcessorNewTX(regnew.RegistryProcessorNew):

    current_city = ""

    emp_pattern = re.compile(r'([0-9]+-[0-9]+)/s+employees')
    registry_pattern = re.compile(r'[A-Za-z]+.*\n.*[0-9]')
    sales_pattern = re.compile(r'Sales\s+(.*)')
    phone_pattern = re.compile(r'\n(.*)[0-9]{3}/')
    city_pattern = re.compile(r'(.*)\n')
    sic_pattern = re.compile(r'(\d{4}):\s+(.*)')
    
    def _process_contour(self, contour_txt):
        registry_match = self.registry_pattern.match(contour_txt)
        city_match = self.city_pattern.match(contour_txt)

        if registry_match:
            business = self._parse_registry_block(contour_txt)
            matches = self._city_detector.match_to_cities(self.current_city)
            if len(matches) > 0:
                business.city = matches[0]
            business.city = self.current_city

            geo.geocode_business(business)
            self.businesses.append(business)
        elif city_match:
            self.current_city = city_match.group(1)

    def _parse_registry_block(self, registry_txt):
        """works for registries from 1985-1999"""
        business = Business()

        lines = registry_txt.split("\n")

        business.name = lines[0]

        # get full address from line 2 up to area code of phone number and parse for address components
        match = phone_pattern.search(registry_txt)
        if match:
            good_address = re.search(r'.*,[\s]+.*', match.group(1))
            bad_address = re.search(r'.*\(.*\)', match.group(1))
            if good_address: # no mailing address in parentheses
                match = re.search(r'(.*),.*(\d{5})', match.group(1))
                    if match:
                        business.address = match.group(1)
                        business.zip = match.group(2)
            elif bad_address: # mailing address in parentheses
                match = re.search(r'\d{5}', match.group(1))
                    if match:
                        business.zip = match.group(0)
        
        match = sic_pattern.search(registry_txt)
        if match:
            business.category = match.group(1)
            business.cat_desc = match.group(2)
        
        match = emp_pattern.search(registry_txt)
        if match:
            business.emp = match.group(1)

        match = sales_pattern.search(registry_txt)
        if match:
            business.sales = match.group(1)

        # if the city is an empty string or employment is unknown mark for manual inspection
        if len(business.city) == 0 or len(business.emp) == 0:
            business.manual_inspection = True

           return business
       
