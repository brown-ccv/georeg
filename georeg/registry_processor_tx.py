""" Processes industrial registries from Texas."""

import re

import numpy as np

import registry_processor as reg
import business_geocoder as geo


def generate_rect(x1, x2, y1, y2):
    """Generate rectangular coords from four corners."""

    return np.array([
        [[x1, y1]],
        [[x1, y2]],
        [[x2, y2]],
        [[x2, y1]]
    ])


class RegistryProcessorTX(reg.RegistryProcessor):
    """Base class for parsing TX registries."""

    def __init__(self):
        super(RegistryProcessorTX, self).__init__()

        self.current_city = ""

    def _process_contour(self, contour_txt):
        registry_match = self.registry_pattern.search(contour_txt)
        city_match = self.city_pattern.search(contour_txt)

        if registry_match:
            business = self._parse_registry_block(contour_txt)
            
            if business.address:
                try:
                    geo.geocode_business(business, self.state)
                except:
                    print("Unable to geocode: %s" % business.address)

            self.businesses.append(business)

        elif city_match:
            self.current_city = city_match.group(1)


class RegistryProcessorOldTX(RegistryProcessorTX):
    """Base class for parsing TX registries from 1985 and earlier."""

    def _get_contours(self, *args, **kwargs):
        """Extract contours from the image, then split contours based on 
        hanging indents."""

        image, contours, hierarchy = super(RegistryProcessorOldTX,
                                           self)._get_contours(*args, **kwargs)

        split_contours = []

        for c in contours:
            contour = reg.Contour(c)
            left_aligned = False
            y_top = contour.y # Top of the contour split.
            y_bottom = contour.y + contour.h # Bottom of the contour split.
            y_max = y_bottom - 1
            x_indent = contour.x + (contour.w * self.indent_width) # indent x coord
            x_max = contour.x + contour.w
            start_splits = False # don't start contour splits until hitting a left indent

            # assumes counter-clockwise movement from top-left
            for [[x, y]] in contour.data:
                if y == y_max:
                    # add contour from the last top coord to bottom of contour
                    rect = generate_rect(contour.x, x_max, y_top, y_max)
                    split_contours.append(rect)
                    break
                if left_aligned:
                    start_splits = True
                    if x > x_indent:
                        # Mark that coordinates are indented.
                        left_aligned = False
                elif x <= x_indent:
                    # Mark that coordinates no longer indented.
                    left_aligned = True
                    if start_splits:
                        # Set y as bottom of block.
                        y_bottom = y
                        # Create rect from last block to this one.
                        rect = generate_rect(contour.x, x_max, y_top, y_bottom)
                        # Append to contours.
                        split_contours.append(rect)
                        # Set y as top of next block.
                        y_top = y

        return image, split_contours, hierarchy

class RegistryProcessor1950s(RegistryProcessorOldTX):
    """1950s TX registry parser."""

    def __init__(self):
        super(RegistryProcessor1950s, self).__init__()
         
        self.city_pattern = re.compile(r'([^a-z]+)[0-9]+[A-Za-z ]+County')
        self.registry_pattern = re.compile(r'[()]+')
        self.name_pattern_1 = re.compile(r'.*(Inc|Co|Corp|Ltd|Mfg)\s*\.\s*(?=,)')
        self.name_pattern_2 = re.compile(r'(.*),')
        self.address_pattern = re.compile(r'(.*?)(\(.*?\))')
        self.sic_pattern = re.compile(r'([A-Za-z,\s]+)\((\d{4})\)')
        self.bracket_pattern = re.compile(r'\[(.*)\]')

    def _parse_registry_block(self, registry_txt):
        business = reg.Business()

        lines = registry_txt.split('\n')
        registry_txt = registry_txt.replace('\n', '')

        # Look for name match in first line.
        name_match = re.match(self.name_pattern_1, lines[0])
        if not name_match:
            name_match = re.match(self.name_pattern_2, lines[0])
        if name_match:
            business.name = name_match.group(0)
            registry_txt = re.sub(re.escape(business.name), '', registry_txt)
        else:
            # Set to entire first line if no match found.
            business.name = lines[0]

        # Find address match.
        address_match = re.search(self.address_pattern, registry_txt)
        if address_match:
            business.address = address_match.group(1)
            registry_txt = re.sub(re.escape(address_match.group(0)), '', registry_txt)

        # Find SIC matches.
        sic_matches = self.sic_pattern.findall(registry_txt)
        for desc, num in sic_matches:
            business.category.append(num)
            business.cat_desc.append(desc)
        
        # Find bracket matches.
        bracket_match = re.search(self.bracket_pattern, registry_txt)
        if bracket_match:
            business.bracket = bracket_match.group(1)

        # Append the current city. Strip the last character because the regex 
        # matches to the start of the following word.
        business.city = self.current_city[:-1] 

        return business


class RegistryProcessor1960(RegistryProcessorOldTX):
    """1960 TX registry parser."""

    def __init__(self):
        super(RegistryProcessor1960, self).__init__()
         
        self.city_pattern = re.compile(r'^([A-Z\s]+),?\s*([A-Za-z\s]+Metropolitan\s*Area)?\.?$')
        self.registry_pattern = re.compile(r'[\[\]()]')
        self.name_pattern_1 = re.compile(r'.+(Inc|Co|Corp|Ltd|Mfg)\s*\.?\s*,\s*')
        self.name_pattern_2 = re.compile(r'(.+?),')
        self.address_pattern = re.compile(r'(.+?)\[(.*)\]')
        self.sic_pattern = re.compile(r'([A-Za-z,\s]+)\((\d{4})\)')

    def _parse_registry_block(self, registry_txt):
        business = reg.Business()

        lines = registry_txt.split('\n')
        registry_txt = registry_txt.replace('\n', '')

        # Look for name match in first line.
        name_match = re.match(self.name_pattern_1, lines[0])
        if not name_match:
            name_match = re.match(self.name_pattern_2, lines[0])
        if name_match:
            business.name = name_match.group(0)
            registry_txt = re.sub(re.escape(business.name), '', registry_txt)
        else:
            # Set to entire first line if no match found.
            business.name = lines[0]

        # Find address and bracket matches.
        address_match = re.search(self.address_pattern, registry_txt)
        if address_match:
            business.address = address_match.group(1)
            business.bracket = address_match.group(2)
            registry_txt = re.sub(re.escape(address_match.group(0)), '', registry_txt)

        # Find SIC matches.
        sic_matches = self.sic_pattern.findall(registry_txt)
        for desc, num in sic_matches:
            business.category.append(num)
            business.cat_desc.append(desc)
        
        # Append the current city.
        business.city = self.current_city

        return business


class RegistryProcessor1965(RegistryProcessorOldTX):
    """1965 and 1970 TX registry parser."""

    def __init__(self):
        super(RegistryProcessor1965, self).__init__()
         
        self.current_zip = ""
        self.city_pattern = re.compile(r'(^[A-Z\s]+)(\d{5})\s+[A-Za-z\s]+County$')
        self.registry_pattern = re.compile(r'[\[\]()]')
        self.name_pattern_1 = re.compile(r'.+(Inc|Co|Corp|Ltd|Mfg)\s*\.?\s*,\s*')
        self.name_pattern_2 = re.compile(r'(.+?),')
        self.address_pattern = re.compile(r'(.+?)\[(.*)\]')
        self.sic_pattern = re.compile(r'([A-Za-z,\s]+)\((\d{4})\)')

    def _process_contour(self, contour_txt):
        super(RegistryProcessor1965, self)._process_contour(contour_txt)

        city_match = self.city_pattern.search(contour_txt)
        if city_match:
            self.current_zip = city_match.group(2)


    def _parse_registry_block(self, registry_txt):
        business = reg.Business()

        lines = registry_txt.split('\n')
        registry_txt = registry_txt.replace('\n', '')

        # Look for name match in first line.
        name_match = re.match(self.name_pattern_1, lines[0])
        if not name_match:
            name_match = re.match(self.name_pattern_2, lines[0])
        if name_match:
            business.name = name_match.group(0)
            registry_txt = re.sub(re.escape(business.name), '', registry_txt)
        else:
            # Set to entire first line if no match found.
            business.name = lines[0]

        # Find address and bracket matches.
        address_match = re.search(self.address_pattern, registry_txt)
        if address_match:
            business.address = address_match.group(1)
            business.bracket = address_match.group(2)
            registry_txt = re.sub(re.escape(address_match.group(0)), '', registry_txt)

        # Find SIC matches.
        sic_matches = self.sic_pattern.findall(registry_txt)
        for desc, num in sic_matches:
            business.category.append(num)
            business.cat_desc.append(desc)
        
        # Append the current city and zip.
        business.city = self.current_city
        business.zip = self.current_zip

        return business



class RegistryProcessor1975(RegistryProcessorOldTX):
    """1975 TX registry parser."""

    def __init__(self):
        super(RegistryProcessor1975, self).__init__()
         
        self.city_pattern = re.compile(r'(^[A-Z\s]+)(\d{5})\s+[A-Za-z\s]+County$')
        self.registry_pattern = re.compile(r'[\[\]()]')
        self.name_pattern_1 = re.compile(r'.+(Inc|Co|Corp|Ltd|Mfg)\s*\.?\s*,\s*')
        self.name_pattern_2 = re.compile(r'(.+?),')
        self.address_pattern = re.compile(r'(.+?)\(.*(\d{5})\)\s*\[(.*)\]')
        self.sic_pattern = re.compile(r'([A-Za-z,\s]+)\((\d{4})\)')


    def _parse_registry_block(self, registry_txt):
        business = reg.Business()

        lines = registry_txt.split('\n')
        registry_txt = registry_txt.replace('\n', '')

        # Look for name match in first line.
        name_match = re.match(self.name_pattern_1, lines[0])
        if not name_match:
            name_match = re.match(self.name_pattern_2, lines[0])
        if name_match:
            business.name = name_match.group(0)
            registry_txt = re.sub(re.escape(business.name), '', registry_txt)
        else:
            # Set to entire first line if no match found.
            business.name = lines[0]

        # Find address match.
        address_match = re.search(self.address_pattern, registry_txt)
        if address_match:
            business.address = address_match.group(1)
            business.zip = address_match.group(2)
            business.bracket = address_match.group(3)
            registry_txt = re.sub(re.escape(address_match.group(0)), '', registry_txt)

        # Find SIC matches.
        sic_matches = self.sic_pattern.findall(registry_txt)
        for desc, num in sic_matches:
            business.category.append(num)
            business.cat_desc.append(desc)

        # Append the current city.
        business.city = self.current_city

        return business


class RegistryProcessor1980s(RegistryProcessorOldTX):
    """1980s TX registry parser."""

    def __init__(self):
        super(RegistryProcessor1980s, self).__init__()
        
        self.city_pattern = re.compile(r'(.*)(\s[A-Za-z]+\s)County') 
        self.registry_pattern = re.compile(r'[0-9]+')
        self.address_pattern = re.compile(r'(.+)\([A-Za-z]+') 
        self.zip_pattern = re.compile(r'(\d{5})\)')
        self.sic_pattern = re.compile(r'([A-Za-z\&,\s]+)\(([0-9A-Za-z\s]{4})\)')
        self.bracket_pattern = re.compile(r'\[(.*)\]')
       
    def _parse_registry_block(self, registry_txt):
        business = reg.Business()

        lines = registry_txt.split('\n')
       
        # Set first line as business name.
        business.name = lines[0]
        
        # Delete lines that list managers/presidents/administrators.
        man_pattern = re.compile(r':\s([A-Za-z \t\r\f\v]+)')
        man_matches = man_pattern.findall(registry_txt)
        for match in man_matches:
            registry_txt = registry_txt.replace(match, '')
        
        # Find address match.
        address_match = re.search(self.address_pattern, registry_txt)
        if address_match:
            business.address = address_match.group(1)
        zip_match = re.search(self.zip_pattern, registry_txt)
        if zip_match:
            business.zip = zip_match.group(1)

        # Delete newline markers.
        registry_txt = registry_txt.replace('\n', '')
        
        # Find SIC matches.
        sic_matches = self.sic_pattern.findall(registry_txt)
        for desc, num in sic_matches:
            business.category.append(num)
            business.cat_desc.append(desc)

        # Find bracket match.
        bracket_match = re.search(self.bracket_pattern, registry_txt)
        if bracket_match:
            business.bracket = bracket_match.group(1)

        # Set business.city
        business.city = self.current_city 

        return business


class RegistryProcessor1990(RegistryProcessorTX):
    """1990 TX registry parser."""

    def __init__(self):
        super(RegistryProcessor1990, self).__init__()
         
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

    def __init__(self):
        super(RegistryProcessor1995, self).__init__()
         
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

    def __init__(self):
        super(RegistryProcessor1999, self).__init__()
         
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
    """2000s TX registry parser."""

    def __init__(self):
        super(RegistryProcessor2000s, self).__init__()
        
        # regex patterns to parse blocks
        self.city_pattern = re.compile(r'([A-Za-z\s]+)')
        self.registry_pattern = re.compile(r'Phone')
        self.sic_pattern = re.compile(r'SIC-(.*)NAICS')
        self.emp_pattern = re.compile(r'Employs-(\d+)')
        self.sales_pattern = re.compile(r'Sales-(.*)')
        self.address_pattern = re.compile(r'(.*?)\((.*?)\)')
        self.cat_desc_pattern = re.compile(r'NAICS-[\d:;\s]+(.*)')
        
    def _parse_registry_block(self, registry_txt):
        """works for registries from 2005"""

        business = reg.Business()

        lines = registry_txt.split('\n')
        
        business.name = lines[0]
        
        # Get address lines
        full_address = ""
        for line in lines:
            start = re.search(r'[0-9]+', line)
            end = re.search(r'Phone', line)
            if start:
                if end:
                    break
                full_address += line

        # Get category description lines
        cat_desc = ""
        for line in lines:
            end = re.search(r'Employs', line)
            if end:
                break
            else:
                cat_desc += line
        
        # Search for regex pattern
        address_match = self.address_pattern.search(full_address)
        if address_match:
            business.address = address_match.group(1)
            business.zip = address_match.group(2)

        cat_desc_match = self.cat_desc_pattern.search(cat_desc)
        if cat_desc_match:
            business.cat_desc = cat_desc_match.group(1)

        sic_match = self.sic_pattern.search(registry_txt)
        if sic_match:
            business.category = sic_match.group(1)

        emp_match = self.emp_pattern.search(registry_txt)
        if emp_match:
            business.emp = emp_match.group(1)

        sales_match = self.sales_pattern.search(registry_txt)
        if sales_match:
            business.sales = sales_match.group(1)

        return business
