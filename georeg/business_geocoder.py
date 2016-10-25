import os
import re
from brownarcgis import BrownArcGIS

geolocator = BrownArcGIS(username = os.environ.get("BROWNGIS_USERNAME"),
                         password = os.environ.get("BROWNGIS_PASSWORD"),
                         referer = os.environ.get("BROWNGIS_REFERER"))

def geocode_business(business, state = 'RI', timeout=60):
    """geocode a business object and store the results inside it,
    return confidence score"""

    # Sub "I" with "1" for numeric values.
    business.zip = business.zip.replace("I", "1").replace("l", "1").replace(" ", "")
    pattern = re.compile("(^|\s)([Il0-9]+)(\s|$)")
    matches = re.findall(pattern, business.address)
    for _, match, _ in matches:
        business.address = re.sub(match, match.replace("I", "1").replace("l", "1"),
                                  business.address)

    try:
        location = geolocator.geocode(street=business.address, city=business.city,
                state=state, zip_cd=business.zip, n_matches = 1, timeout = timeout)
    except:
        location = None

    if location:
        match = location["candidates"][0]["attributes"]
        business.confidence_score = float(match["score"])
        business.lat = match["location"]["y"]
        business.long = match["location"]["x"]
        return True
    else:
        return False
