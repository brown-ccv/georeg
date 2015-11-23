import registry_processor as reg
import registry_processor_new as regnew
import re
import business_geocode as geo

class RegistryProcessorNewTX(regnew.RegistryProcessorNew):

    current_city = ""

    # regex patterns to parse blocks
    city_pattern = re.compile(r'{A-Za-z\s]+\n\(.*\)')
    registry_pattern = re.compile(r'.*\n.*[0-9]')
    sic_pattern = re.compile(r'SIC-([/d]{4}\;)+')
    naics_pattern = re.compile(r'NAICS-([/d]{6}\;)+')
    emp_pattern = re.compile(r'Employs-([/d]+),')
    sales_pattern = re.compile(r'Sales-(.*)')

    def _process_contour(self, contour_txt):
        registry_match = self.registry_pattern.match(contour_txt)
        city_match = self.city_pattern.match(contour_txt)

        if registry_match:
            business = self._parse_registry_block(contour_txt)
            business.city = self.current_city

            if business.address:
                geo.geocode_business(business, 'TX')

            self.business.append(business)
        elif city_match:
            self.current_city = city_match.group(1)

    def _parse_registry_block(self, registry_txt):
        """works for registries from 2000-2010"""

        business = reg.Business()

        lines = registry_txt.split('\n')

        business.name = lines[0]
        
        full_address = ""
        for line in lines:
            start = re.search(r'[0-9]+', line)
            end = re.search(r'Phone')
            if start:
                if end:
                    break
                full_address += line

        address_pattern = re.compile(r'(.*)\((.*)\)')
        match = self.address_pattern.search(full_address)
        if match:
            business.address = match.group(1)
            business.zip = match.group(2)

        cat_desc = ""
        for line in lines:
            start = re.search(r'SIC-', line)
            end = re.search(r'Employs')
            if start:
                if end:
                    break
                cat_desc += line

        cat_desc_pattern = re.compile(r'[/d]{6}\;(.*)')
        match = self.cat_desc_pattern.search(cat_desc)
        if match:
            business.cat_desc = match.group(1)

        match = self.sic_pattern.search(registry_txt):
        if match:
            business.category = match.group(1)

        match = self.naics_pattern.search(registry_txt):
        if match:
            business.new_cat = match.group(1)
    
        match = self.emp_pattern.search(registry_txt):
        if match:
            business.emp = match.group(1)

        match = self.sales_pattern.search(registry_txt):
        if match:
            business.sales = match.group(1)

        return business
