import registry_processor_new as regnew


class RegistryProcessorNewTX(regnew.RegistryProcessorNew):

    current_city = ""

    emp_pattern = re.compile(r'[0-9]+-[0-9]+/s+employees')
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
            business.city = self.current_city

            geo.geocode_business(business)
            self.businesses.append(business)
        elif city_match:
            self.current_city = city_match.group(1)

    def _parse_registry_block(self, registry_txt):
        """works for registries from 1980 onward"""
        business = Business()

        lines = registry_txt.split("\n")

        business.name = lines[0]

        # search from line 2 up to phone number (full address) for address components
        match = phone_pattern.search(registry_txt)
        if match:
            good_address = re.search(r'.*,[\s]+.*', match.group(1))
            bad_address = re.search(r'.*\(.*\)', match.group(1))
            if good_address:
                # no mailing address in parentheses
                match = re.search(r'(.*),.*(\d{5})', match.group(1))
                    business.address = match.group(1)
                    business.zip = match.group(2)
            elif bad_address:
                # mailing address in parentheses
                match = re.search(r'\d{5}', match.group(1))
                    business.zip = match.group(0)
            
        
       
