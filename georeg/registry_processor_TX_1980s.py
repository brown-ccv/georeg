import registry_processor as reg
import registry_processor_new as regnew
import re
import business_geocoder as geo

class RegistryProcessorNewTX(regnew.RegistryProcessorNew):

    current_city = ""

    city_pattern = re.compile(r'([/w]{1,2}(/w[/s]+County)')
    registry_pattern = re.compile(r'[A-Za-z]+.*[0-9]')
