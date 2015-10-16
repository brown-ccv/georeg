import os

import brownarcgis

geolocator = brownarcgis.BrownArcGIS(username = os.environ.get("BROWNGIS_USERNAME"),
                                     password = os.environ.get("BROWNGIS_PASSWORD"),
                                     referer = os.environ.get("BROWNGIS_REFERER"))

def geocode_business(business, state = 'RI'):
    """geocode a business object and store the results inside it,
    return confidence score"""

    location = geolocator.geocode(street=business.address, city=business.city,
            state=business.state, zip_cd=business.zip, n_matches = 1, timeout = 10)

    if location:
        match = location[0]
        business.confidence_score = float(match[0])
        business.lat = match[2]
        business.long = match[3]

    else: print "unsuccessful geo-query"
