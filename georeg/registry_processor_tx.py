""" Processes industrial registries from Texas."""

import re

import numpy as np

import registry_processor as reg
import business_geocoder as geo


def generate_contour(x1, x2, y1, y2):
    """Generate rectangular Contour object from four corners."""

    # Set coordinates of rectangle.
    coords = np.array([
        [[x1, y1]],
        [[x1, y2]],
        [[x2, y2]],
        [[x2, y1]]
    ])

    return reg.Contour(coords)


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
                try:
                    geo.geocode_business(business, self.state)
                except:
                    print("Unable to geocode: %s" % business.address)

            self.businesses.append(business)

        elif city_match:
            self.current_city = city_match.group(1)


class RegistryProcessorOldTX(RegistryProcessorTX):
    """Base class for parsing TX registries from 1975 and earlier."""

    def __init__(self, *args, **kwargs):
        super(RegistryProcessorOldTX, self).__init__(*args, **kwargs)
         
        self._expand_bb = lambda x,y,w,h: (x - int(round(self._image_width() * self.bb_expansion_percent / 2.0)), \
                                           y - int(round(self._image_height() * self.bb_expansion_percent / 2.0)), \
                                           w + int(round(self._image_width() * self.bb_expansion_percent / 2.0)), \
                                           h + int(round(self._image_height() * self.bb_expansion_percent / 2.0)))
                                               

    def _assemble_contour_columns(self, contours, column_locations):
        """Separate contours that fit into columns from those that don't,
        splitting column contours based on hanging indents."""

        column_contours, non_column_contours = super(
                RegistryProcessorOldTX, self)._assemble_contour_columns(contours, 
                                                                        column_locations)

        split_contours = []

        for i, column in enumerate(column_contours):
            split_contours.append([])

            for contour in column:
                left_aligned = True # Assume contour starts unindented.
                y_top = contour.y # Top of the contour split.
                y_bottom = contour.y + contour.h # Bottom of the contour split.

                for [[x, y]] in contour.data:
                    if left_aligned:
                        if x > contour.x + contour.w * self.indent_width:
                            # Mark that coordinates are indented.
                            left_aligned = False
                    else:
                        if x <= contour.x + contour.w * self.indent_width:
                            # Mark that coordinates no longer indented.
                            left_aligned = True
                            # Set y as bottom of block.
                            y_bottom = y
                            # Create rect from last block to this one.
                            c = generate_contour(contour.x, 
                                                 contour.x + contour.w,
                                                 y_top,
                                                 y_bottom)
                            # Append to contours.
                            split_contours[i].append(c)
                            # Set y as top of next block.
                            y_top = y

                # Add a contour split from the last top coord to the bottom of
                # the contour.
                c = generate_contour(contour.x, 
                                     contour.x + contour.w,
                                     y_top,
                                     contour.y + contour.h)
                split_contours[i].append(c)

        return split_contours, non_column_contours


class RegistryProcessor1975(RegistryProcessorOldTX):
    """1975 TX registry parser."""

    def __init__(self, *args, **kwargs):
        super(RegistryProcessor1975, self).__init__(*args, **kwargs)
         
        self.current_city = ""

        self.city_pattern = re.compile(r'([^0-9])')
        self.registry_pattern = re.compile(r'[0-9]+')
        self.name_pattern_1 = re.compile(r'.*(Inc|Co|Corp|Ltd|Mfg)\s*\.\s*(?=,)')
        self.name_pattern_2 = re.compile(r'.*(?=,\s*[0-9])')
        self.address_pattern = re.compile(r'(\d.*?)(\(.*?\))')
        self.city_pattern = re.compile(r'([^0-9])')
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
            registry_txt = re.sub(re.escape(address_match.group(0)), '', registry_txt)

        # Find SIC matches.
        sic_matches = self.sic_pattern.findall(registry_txt)
        for desc, num in sic_matches:
            business.category = num
            business.cat_desc = desc

        return business


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
