import registry_processor_new as regnew
:

class RegistryProcessorNewTX(regnew.RegistryProcessorNew):

    current_city = ""

    emp_pattern = re.compile(r'[0-9]+-[0-9]+/s+employees')
    registry_pattern = re.compile(r'[A-Za-z]+.*\n.*[0-9]')
    sic_pattern = re.compile(r'(\d{4}):\s+(.*)')
    sales_pattern = re.compile(r'Sales\s+(.*)')
    city_pattern = re.compile(r'(.*)\n')

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

