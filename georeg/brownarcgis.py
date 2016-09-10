"""
:class:`.BrownArcGIS` geocoder.
"""

import json
from time import time
from math import ceil
from geopy.compat import urlencode, urlopen, Request
from geopy.geocoders import ArcGIS
from geopy.geocoders.base import Geocoder, DEFAULT_SCHEME, DEFAULT_TIMEOUT, DEFAULT_WKID
from geopy.exc import GeocoderServiceError, GeocoderAuthenticationFailure
from geopy.exc import ConfigurationError
from geopy.location import Location
from geopy.util import logger

__all__ = ("BrownArcGIS", )

class BrownArcGIS(ArcGIS):
    """
    Extend ArcGIS class from GeoPy 1.11.0
    """

    auth_api = 'http://quidditch.gis.brown.edu:6080/arcgis/tokens/generateToken'

    def __init__(self, **kwargs):

        super(BrownArcGIS, self).__init__(scheme='https', **kwargs)

        self.scheme = 'http' # https not supported

        self.api = (
            '%s://quidditch.gis.brown.edu:6080/arcgis/rest/services/brown_geocoding'
            '/Street_Addresses_US/GeocodeServer/findAddressCandidates' % self.scheme
        )
        self.batch_api = (
            '%s://quidditch.gis.brown.edu:6080/arcgis/rest/services/brown_geocoding'
            '/Street_Addresses_US/GeocodeServer/geocodeAddresses' % self.scheme
        )
        self.reverse_api = (
            '%s://quidditch.gis.brown.edu:6080/arcgis/rest/services/brown_geocoding'
            '/Street_Addresses_US/GeocodeServer/reverseGeocode' % self.scheme
        )

    def geocode(self, query='', street='', city='', state='', zip_cd='',
                n_matches=1, timeout=None):
        """
        Return a ranked list of locations for an address.

        :param string query: The single-line address you wish to geocode.

        :param string street: Optional, Street if not using single-line

        :param string city: Optional, City

        :param string state: Optional, State

        :param string zip_cd: Optional, Zip Code

        :param int n_matches: Return top n matches.

        :param int timeout: Time, in seconds, to wait for the geocoding service
            to respond before raising a :class:`geopy.exc.GeocoderTimedOut`
            exception. Set this only if you wish to override, on this call
            only, the value set during the geocoder's initialization.
        """

        params = {'Single Line Input': query,
                  'Street': street,
                  'City': city,
                  'State': state,
                  'ZIP': zip_cd,
                  'f': 'json',
                  'maxLocations': n_matches}

        if not (len(query) or len(street)):
            raise ConfigurationError(
                "Street or Full Address must be entered."
            )

        url = "?".join((self.api, urlencode(params)))

        logger.debug("%s.geocode: %s", self.__class__.__name__, url)
        response = self._call_geocoder(url, timeout=timeout)

        # Handle any errors; recursing in the case of an expired token
        if 'error' in response:
            if response['error']['code'] == self._TOKEN_EXPIRED:
                self.retry += 1
                self._refresh_authentication_token()
                return self.geocode(query, street, city, state, zip_cd, n_matches, timeout)
            raise GeocoderServiceError(str(response['error']))

        if not len(response['candidates']):
            return None

        geocoded = []
        candidate_cnt = 1
        for candidate in response['candidates']:
            geocoded.append({
                'candidate':candidate_cnt,
                'attributes':{
                    'score':candidate['score'],
                    'match_addr':candidate['address'],
                    'location':{'x':candidate['location']['x'],
                                'y':candidate['location']['y']}}})
            candidate_cnt += 1

        return {'candidates':geocoded}

    def geocode_batch(self, addresses, timeout=None, wkid=DEFAULT_WKID):
        """
        Process address dict returning top match only.

        :param list addresses: List of tuples (uid, address) uid = int, address = sting.

        :param int timeout: Time, in seconds, to wait for the geocoding service
            to respond before raising a :class:`geopy.exc.GeocoderTimedOut`
            exception. Set this only if you wish to override, on this call
            only, the value set during the geocoder's initialization.
        """

        if not len(addresses):
            raise ConfigurationError(
                "Must pass a list of tuples with uid and address."
            )

        geocoded = []
        for i in xrange(0, len(addresses), 300):

            records = []
            for a in addresses[i:i+300]:
                attributes_dict = {"attributes":{"OBJECTID":a[0],"Single Line Input":a[1]}}
                records.append(attributes_dict)

            query = {"records":records}

            params = {'addresses': query,
                      'outSR': wkid,
                      'f': 'json'}

            url = "?".join((self.batch_api, urlencode(params)))

            logger.debug("%s.geocode: %s", self.__class__.__name__, url)
            response = self._call_geocoder(url, timeout=timeout)

            # Handle any errors; recursing in the case of an expired token.
            if 'error' in response:
                if response['error']['code'] == self._TOKEN_EXPIRED:
                    self.retry += 1
                    self._refresh_authentication_token()
                    return self.geocode(timeout=timeout)
                raise GeocoderServiceError(str(response['error']))

            #add code for parsing output here
            for location in response['locations']:
                geocoded.append({
                    'uid':location['attributes']['ResultID'],
                    'attributes':{
                    'score':location['score'],
                    'match_addr':location['attributes']['Match_addr'],
                    'location':{'x':location['location']['x'],
                                'y':location['location']['y']}}})

        return {'geocoded':geocoded}

    def reverse(self, query, timeout=None, distance=100, wkid=DEFAULT_WKID):
        """
        Given a point, find an address.

        :param query: The coordinates for which you wish to obtain the
            closest human-readable addresses.
        :type query: :class:`geopy.point.Point`, list or tuple of (latitude,
            longitude), or string as "%(latitude)s, %(longitude)s".

        :param int timeout: Time, in seconds, to wait for the geocoding service
            to respond before raising a :class:`geopy.exc.GeocoderTimedOut`
            exception. Set this only if you wish to override, on this call
            only, the value set during the geocoder's initialization.

        :param int distance: Search radius from query location, in meters.
            Default 100 meters if not specified.

        :param string wkid: WKID to use for both input and output coordinates.
            Default 4326 matching Brown ArcGIS server.
        """

        # ArcGIS is lon,lat; maintain lat,lon convention of geopy
        point = self._coerce_point_to_string(query).split(",")
        if wkid != DEFAULT_WKID:
            location = {"x": point[1], "y": point[0], "spatialReference": wkid}
        else:
            location = ",".join((point[1], point[0]))

        params = {'location': location,
                  'f': 'json',
                  'distance': distance,
                  'outSR': wkid}

        url = "?".join((self.reverse_api, urlencode(params)))

        logger.debug("%s.reverse: %s", self.__class__.__name__, url)
        response = self._call_geocoder(url, timeout=timeout)

        if not len(response):
            return None

        if 'error' in response:
            if response['error']['code'] == self._TOKEN_EXPIRED:
                self.retry += 1
                self._refresh_authentication_token()
                return self.reverse(query, timeout=timeout, distance=distance, wkid=wkid)
            raise GeocoderServiceError(str(response['error']))

        address = {'match_addr':('%(Street)s, %(City)s, %(State)s, %(ZIP)s' % response['address']),
                   'location':{'x':response['location']['x'],
                               'y':response['location']['y']}}

        return address

    def _refresh_authentication_token(self):
        """
        POST to ArcGIS requesting a new token.
        """
        if self.retry == self._MAX_RETRIES:
            raise GeocoderAuthenticationFailure(
                'Too many retries for auth: %s' % self.retry
            )
        token_request_arguments = {
            'username': self.username,
            'password': self.password,
            'client': 'referer',
            'referer': self.referer,
            'expiration': self.token_lifetime,
            'f': 'json'
        }
        self.token_expiry = int(time()) + self.token_lifetime
        data = urlencode(token_request_arguments)
        req = Request(url=self.auth_api, headers=self.headers)
        page = urlopen(req, data=data, timeout=self.timeout)
        page = page.read()
        response = json.loads(page)
        if not 'token' in response:
            raise GeocoderAuthenticationFailure(
                'Missing token in auth request. '
                'Request URL: %s?%s. '
                'Response JSON: %s. ' %
                (self.auth_api, data, json.dumps(response))
            )
        self.retry = 0
        self.token = response['token']
