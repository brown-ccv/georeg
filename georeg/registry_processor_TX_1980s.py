import registry_processor as reg
import re
import business_geocoder as geo

class RegistryProcessorNewTX(reg.RegistryProcessor):

    def __init__(self):
        super(RegistryProcessorNewTX, self).__init__(state="TX")
         
        self.current_city = ""

        self.city_pattern = re.compile(r'([/w]{1,2}(/w[/s]+County)')
        self.registry_pattern = re.compile(r'[A-Za-z]+.*[0-9]')
