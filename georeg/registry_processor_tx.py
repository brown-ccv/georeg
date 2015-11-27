""" Processes industrial registries from Texas."""

import registry_processor as reg
import re
import business_geocoder as geo

class RegistryProcessorTX(reg.RegistryProcessor):
    """Base class for parsing TX registries."""

    def __init__(self, *args, **kwargs):
        super(RegistryProcessorTX, self).__init__(*args, **kwargs)
         
        self.current_city = ""

    def _process_contour(self, contour_txt):
        registry_match = self.registry_pattern.search(contour_txt)
        city_match = self.city_pattern.search(contour_txt)

        if registry_match:
            business = self._parse_registry_block(contour_txt)
            
            if business.address:
                geo.geocode_business(business, self.state)

            self.businesses.append(business)
        elif city_match:
            self.current_city = city_match.group(1)


class RegistryProcessor1980s(RegistryProcessorTX):
    """1980-1989 TX registry parser."""

    def __init__(self, *args, **kwargs):
        super(RegistryProcessor1980s, self).__init__(*args, **kwargs)
         
        self.city_pattern = re.compile(r'([/w]{1,2}(/w[/s]+County)')
        self.registry_pattern = re.compile(r'[A-Za-z]+.*[0-9]')


class RegistryProcessor1990(RegistryProcessorTX):
    """1990 TX registry parser."""

    def __init__(self, *args, **kwargs):
        super(RegistryProcessor1990, self).__init__(*args, **kwargs)
         
        self.current_city = ""

        self.city_pattern = re.compile(r'([^0-9])')
        self.registry_pattern = re.compile(r'[0-9]+')
        self.sales_pattern = re.compile(r'Sales[\:\s]+(.*million)')
        self.emp_pattern = re.compile(r'([0-9]+-[0-9]+)[\s]+employees')
        self.sic_pattern = re.compile(r'\d{4}:[\s]+.*$', re.DOTALL)
        self.phone_pattern = re.compile(r'\(\d{3}\).*[[\s]+\[(.*)\]]*', re.DOTALL)
        self.paren_pattern = re.compile(r'([^\(]+)\(')
        self.address_pattern = re.compile(r'([^0-9\(]+)\s+TX\s+(\d{5}).*\)')

    def _parse_registry_block(self, registry_txt):
        """works for registries from 1990"""

        business = reg.Business()

        lines = registry_txt.split('\n')

        business.name = lines[0]

        full_address = ""
        for line in lines:
            start = re.search(r'[0-9]{2,}', line)
            end = self.phone_pattern.search(line)
            if start:
                if end:
                    break
                full_address += ' '+line

        match = self.paren_pattern.search(full_address)
        if match:
            business.address = match.group(1)
        
        match = self.address_pattern.search(full_address)
        if match:
            business.city = match.group(1)
            business.zip = match.group(2)

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

        match = self.phone_pattern.search(registry_txt)
        if match:
            business.bracket = match.group(1)

        return business


class RegistryProcessor1995(RegistryProcessorTX):
    """1995 TX registry parser."""

    def __init__(self, *args, **kwargs):
        super(RegistryProcessor1995, self).__init__(*args, **kwargs)
         
        self.current_city = ""

        self.city_pattern = re.compile(r'([^0-9])')
        self.registry_pattern = re.compile(r'[0-9]+')
        self.sales_pattern = re.compile(r'Sales[\:\s]+(.*million)')
        self.emp_pattern = re.compile(r'([0-9]+-[0-9]+)[\s]+employees')
        self.sic_pattern = re.compile(r'\d{4}:[\s]+.*$', re.DOTALL)
        self.phone_pattern = re.compile(r'\d{3}/.*[[\s]+\[(.*)\]]*', re.DOTALL)
        self.no_paren_pattern = re.compile(r'[^\(]+')
        self.paren_pattern = re.compile(r'([^\(]+)\(')
        self.good_address_pattern = re.compile(r'(.*)[,.](.*)(\d{5})')
        self.PO_box_pattern = re.compile(r'Box[\s]+[\d]+')
        self.good_address_PO_pattern = re.compile(r'(.*)[,.].*[,.](.*)(\d{5})')
        self.bad_address_pattern = re.compile(r'\(mail:.*[,.](.*)[,.].*(\d{5}).*\)')

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


class RegistryProcessor1999(RegistryProcessorTX):
    """1999 TX registry parser."""

    def __init__(self, *args, **kwargs):
        super(RegistryProcessor1999, self).__init__(*args, **kwargs)
         
        self.current_city = ""

        self.city_pattern = re.compile(r'([^0-9])')
        self.registry_pattern = re.compile(r'[0-9]+')
        self.sales_pattern = re.compile(r'Sales[\:\s]+(.*million)')
        self.emp_pattern = re.compile(r'([0-9]+-[0-9]+)[\s]+employees')
        self.sic_pattern = re.compile(r'\d{4}:[\s]+.*$', re.DOTALL)
        self.phone_pattern = re.compile(r'\d{3}/.*')
        self.no_paren_pattern = re.compile(r'[^\(]+')
        self.paren_pattern = re.compile(r'([^\(]+)\(')
        self.bad_address_pattern = re.compile(r'\(mail:.*[,.](.*)[,.].*(\d{5})-\d{4}\)')
        self.good_address_pattern = re.compile(r'(.*)[,.](.*)(\d{5})')

    def _parse_registry_block(self, registry_txt):
        business = reg.Business()

        lines = registry_txt.split('\n')

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

        return business
                                                 

class RegistryProcessor2000s(RegistryProcessorTX):
    """2000-2009 TX registry parser."""

    def __init__(self, *args, **kwargs):
        super(RegistryProcessor200s, self).__init__(*args, **kwargs)
         
        # regex patterns to parse blocks
        self.city_pattern = re.compile(r'{A-Za-z\s]+\n\(.*\)')
        self.registry_pattern = re.compile(r'.*\n.*[0-9]')
        self.sic_pattern = re.compile(r'SIC-([/d]{4}\;)+')
        self.naics_pattern = re.compile(r'NAICS-([/d]{6}\;)+')
        self.emp_pattern = re.compile(r'Employs-([/d]+),')
        self.sales_pattern = re.compile(r'Sales-(.*)')
        self.address_pattern = re.compile(r'(.*)\((.*)\)')
        self.cat_desc_pattern = re.compile(r'[/d]{6}\;(.*)')

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

        match = self.cat_desc_pattern.search(cat_desc)
        if match:
            business.cat_desc = match.group(1)

        match = self.sic_pattern.search(registry_txt)
        if match:
            business.category = match.group(1)

        match = self.naics_pattern.search(registry_txt)
        if match:
            business.new_cat = match.group(1)
    
        match = self.emp_pattern.search(registry_txt)
        if match:
            business.emp = match.group(1)

        match = self.sales_pattern.search(registry_txt)
        if match:
            business.sales = match.group(1)

        return business
