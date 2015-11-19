import registry_processor as reg
import registry_processor_new as regnew
import re
import business_geocoder as geo

class RegistryProcessorNewTX(regnew.RegistryProcessorNew):

    current_city = ""

    city_pattern = re.compile(r'(.*)\n')
    registry_pattern = re.compile(r'[A-Za-z]+.*[\n].*[0-9]')
    sales_pattern = re.compile(r'Sales[\s]+(.*[\s]+million)')
    emp_pattern = re.compile(r'([0-9]+-[0-9]+)[\s]+employees')
    sic_pattern = re.compile(r'\d{4}:[\s]+.*$', re.DOTALL)
    phone_pattern = re.compile(r'\d{3}/.*[[\s]+\[(.*)\]]*', re.DOTALL)
    no_paren_pattern = re.compile(r'[^\(]+')
    paren_pattern = re.compile(r'([^\(]+)\(')
    good_address_pattern = re.compile(r'(.*)[,.](.*)(\d{5})')
    good_address_PO_pattern = re.compile(r'(.*)[,.].*[,.](.*)(\d{5})')
    bad_address_pattern = re.compile(r'\(mail:.*[,.]([\w]{1,2})[,.].*?[,.]?[/s]?(\d{5})-\)') #TOFIX: also, do we even need this info?
    PO_box_pattern = re.compile(r'Box[\s]+[\d]+')

    def _process_contour(self, contour_txt):
        registry_match = self.registry_pattern.match(contour_txt)
        city_match = self.city_pattern.match(contour_txt)

        if registry_match:
            business = self._parse_registry_block(contour_txt)
            #business.city = self.current_city
            
            if business.address:
                geo.geocode_business(business, 'TX')
            
            self.businesses.append(business)
        elif city_match:
            self.current_city = city_match.group(1)

    def _parse_registry_block(self, registry_txt):
        """works for registries from 1995-1999"""

        business = reg.Business()

        lines = registry_txt.split("\n")

        business.name = lines[0]

        full_address = ""
        for line in lines:
            start = re.search('[0-9]{2,}', line)
            end = re.search('\d{3}/', line)
            if start:
                if end:
                    break
                full_address += line
                
        match = self.phone_pattern.search(registry_txt)
        if match:    
            business.bracket = match.group(1)
            
        match = self.no_paren_pattern.search(full_address)
        if match:
            match = self.good_address_pattern.search(full_address)
            if match:
                business.address = match.group(1)
                business.zip = match.group(3)
                business.city = match.group(2)
                #matches = self._city_detector.match_to_cities(city)
                #if len(matches) > 0:
                #    business.city = matches[0]
            mailing_address = self.PO_box_pattern.search(full_address)
            if mailing_address: 
                match = self.good_address_PO_pattern.search(full_address)
                if match:
                    business.address = match.group(1)
                    business.city = match.group(2)
                    business.zip = match.group(3)
        
        match = self.paren_pattern.search(full_address)
        if match:
            business.address = match.group(1)
            match = self.bad_address_pattern.search(full_address)
            if match: 
                business.zip = match.group(2)
                #business.city = match.group(1)
                #matches = self._city_detector.match_to_cities(city)
                #if len(matches) > 0:
                #    business.city = matches[0]
            
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

        match = self.sales_pattern.search(registry_txt)
        if match:
            business.sales = match.group(1)

        # if the geocoder is less than 80% confident or there is no SIC code, mark for manual inspection
        if business.confidence_score < 80 or len(business.category) == 0:
            business.manual_inspection = True

        return business
       
