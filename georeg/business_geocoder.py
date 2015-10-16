import urllib
import urllib2
from registry_processor import RegistryProcessorException # we'll use this here too

api_key = "de15a680b76f43efbc9d59c7f4e1f7b2"

def get_remaining_credits():
    credit_check_url = "https://geoservices.tamu.edu/UserServices/Payments/Balance/AccountBalanceWebServiceHttp.aspx"

    # parameters for request
    data = {
        'apikey': api_key,
        'format': 'tsv',
        'version': '1.2'
    }

    # encode parameters
    url_values = urllib.urlencode(data)
    credit_check_url += '?' + url_values

    try:
        response = urllib2.urlopen(credit_check_url)
    except urllib2.URLError as ex:
        if type(ex.reason) is str:
            print "URL error: %s" % ex.reason
        else:
            print "URL error"
        return None

    the_page = response.read()
    values = the_page.split('\t')

    assert(len(values) == 2)

    return int(values[1])


def geocode_business(business, state = 'RI'):
    """geocode a business object and store the results inside it,
    return confidence score"""

    geocoder_url = "https://geoservices.tamu.edu/Services/Geocode/WebService/GeocoderWebServiceHttpNonParsed_V04_01.aspx"

    # parameters for request
    data = {
        'apikey': api_key,
        'version': '4.01',
        'streetAddress': business.address,
        'city': business.city,
        'state': state,
        'zip': business.zip,
        'format': 'tsv',
        'allowTies' : 'false',
        'tieBreakingStrategy' : 'flipACoin'
    }

    # encode parameters
    url_values = urllib.urlencode(data)
    geocoder_url += '?' + url_values

    # this loop is here in case we ran out of credits and need to re-send the url request (under normal circumstance it will only execute once)
    while True:
        try:
            response = urllib2.urlopen(geocoder_url)
        except urllib2.URLError as ex:
            if type(ex.reason) is str:
                print "URL error: %s" % ex.reason
            else:
                print "URL error"
            return

        the_page = response.read()
        values = the_page.split('\t')

        if len(values) < 8 and get_remaining_credits() == 0:
            while True:
                raw_input("Out of TAMU geocoding credits, please refill then press enter to try again.")
                if get_remaining_credits() > 0:
                    break
            continue # re-send url request because we have credits again

        if len(values) >= 8 and values[2] == '200':
            business.confidence_score = float(values[7])

            business.lat = values[3]
            business.long = values[4]
        else: print "unsuccessful geo-query"
        break # everything went as planned so break from loop
