import registry_processor as reg
import registry_processor_new as regnew
import re
import business_geocoder as geo

class RegistryProcessorNewTX(regnew.RegistryProcessorNew):

    current_city = ""

    city_pattern = re.compile(r'([^0-9])')
    registry_pattern = re.compile(r'[0-9]+')
    sales_pattern = re.compile(r'Sales[\:\s]+(.*million)')
    emp_pattern = re.compile(r'([0-9]+-[0-9]+)[\s]+employees')
    sic_pattern = re.compile(r'\d{4}:[\s]+.*$', re.DOTALL)
    phone_pattern = re.compile(r'\d{3}/.*[[\s]+\[(.*)\]]*', re.DOTALL)
    no_paren_pattern = re.compile(r'[^\(]+')
    paren_pattern = re.compile(r'([^\(]+)\(')
    good_address_pattern = re.compile(r'(.*)[,.](.*)(\d{5})')
    PO_box_pattern = re.compile(r'Box[\s]+[\d]+')
    good_address_PO_pattern = re.compile(r'(.*)[,.].*[,.](.*)(\d{5})')
    bad_address_pattern = re.compile(r'\(mail:.*[,.](.*)[,.].*(\d{5}).*\)')

    def _process_contour(self, contour_txt):
        registry_match = self.registry_pattern.search(contour_txt)
        city_match = self.city_pattern.search(contour_txt)
        
        if registry_match:
            business = self._parse_registry_block(contour_txt)

            if business.address:
                geo.geocode_business(business, 'TX')

            self.businesses.append(business)
        elif city_match:
            self.current_city = city_match.group(1)

    def _parse_registry_block(self, registry_txt):
        business = reg.Business()

        lines = registry_txt.split("\n")

        business.name = lines[0]

        full_address = ""
        for line in lines:
            start = re.search('[0-9]{2,}', line)
            end = self.phone_pattern.search(line)
            if start:
                if end:
                    break
                full_address += ' '+line

        match = self.paren_pattern.search(full_address)
        if match:
            business.address = match.group(1)
            match = self.bad_address_pattern.search(full_address)
            if match:
                business.city = match.group(1)
                business.zip = match.group(2)
        else:
            match = self.PO_box_pattern.search(full_address)
            if match:
                match = self.good_address_PO_pattern.search(full_address)
                if match:
                    business.address = match.group(1)
                    business.city = match.group(2)
                    business.zip = match.group(3)
            else:
                match = self.good_address_pattern.search(full_address)
                if match:
                    business.address = match.group(1)
                    business.city = match.group(2)
                    business.zip = match.group(3)
                    
        matches = self.sic_pattern.findall(registry_txt)
        category_pattern = re.compile(r'\d{4}')
        cat_desc_pattern = re.compile(r'[^\:0-9\n]+[\n]*[^0-9\:]*')
        one_sic_pattern = re.compile(r'(/d{4}):[/s]+(.*)', re.DOTALL)
        if len(matches) > 0:
            business.category = category_pattern.findall(matches[0])
            business.cat_desc = cat_desc_pattern.findall(matches[0])
        else:
            match = one_sic_pattern.search(registry_txt)
            if match:
                business.category = match.group(1)
                business.cat_desc = match.group(2)
           
        match = self.emp_pattern.search(registry_txt)
        if match:
            business.emp = match.group(1)

        return business
