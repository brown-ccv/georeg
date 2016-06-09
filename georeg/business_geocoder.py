import os

from brown_geopy.brownarcgis import BrownArcGIS


geolocator = BrownArcGIS(username = os.environ.get("BROWNGIS_USERNAME"),
                         password = os.environ.get("BROWNGIS_PASSWORD"),
                         referer = os.environ.get("BROWNGIS_REFERER"))


def geocode_business(business, state = 'RI', timeout=60):
    """geocode a business object and store the results inside it,
    return confidence score"""

    location = geolocator.geocode(street=business.address, city=business.city,
            state=state, zip_cd=business.zip, n_matches = 1, timeout = timeout)

    if location:
        match = location["candidates"][0]["attributes"]
        business.confidence_score = float(match["score"])
        business.lat = match["location"]["y"]
        business.long = match["location"]["x"]

    else: 
        print "Unsuccessful geo-query: %s, %s, %s, %s" % (business.address,
                business.city, state, business.zip)
