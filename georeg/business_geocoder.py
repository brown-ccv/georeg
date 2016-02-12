import os

from brown_geopy.brownarcgis import BrownArcGIS


geolocator = BrownArcGIS(username = os.environ.get("BROWNGIS_USERNAME"),
                         password = os.environ.get("BROWNGIS_PASSWORD"),
                         referer = os.environ.get("BROWNGIS_REFERER"))


def geocode_business(business, state = 'RI'):
    """geocode a business object and store the results inside it,
    return confidence score"""

    location = geolocator.geocode(street=business.address, city=business.city,
            state=state, zip_cd=business.zip, n_matches = 1, timeout = 10)

    if location:
        match = location[0]
        business.confidence_score = float(match[0])
        business.clean_addr(match[1])
        business.lat = match[2]
        business.long = match[3]

    else: 
        print "Unsuccessful geo-query: %s, %s, %s, %s" % (business.address,
                business.city, state, business.zip)
