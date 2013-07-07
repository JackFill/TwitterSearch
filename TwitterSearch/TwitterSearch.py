import requests
from requests_oauthlib import OAuth1
from .TwitterSearchException import TwitterSearchException
from .TwitterSearchOrder import TwitterSearchOrder
from .utils import py3k

try: from urllib.parse import parse_qs as parse # python3
except ImportError: from urlparse import parse_qs as parse # python2

# determine max int value
try: from sys import maxint # python2
except ImportError: from sys import maxsize as maxint # python3

class TwitterSearch(object):
    _base_url = 'https://api.twitter.com/1.1/'
    _verify_url = 'account/verify_credentials.json'
    _search_url = 'search/tweets.json'

    # see https://dev.twitter.com/docs/error-codes-responses
    exceptions = {
                     400 : 'Bad Request: The request was invalid',
                     401 : 'Unauthorized: Authentication credentials were missing or incorrect',
                     403 : 'Forbidden: The request is understood, but it has been refused or access is not allowed',
                     404 : 'Not Found: The URI requested is invalid or the resource requested does not exists',
                     406 : 'Not Acceptable: Invalid format is specified in the request',
                     410 : 'Gone: This resource is gone',
                     420 : 'Enhance Your Calm:  You are being rate limited',
                     422 : 'Unprocessable Entity: Image unable to be processed',
                     429 : 'Too Many Requests: Request cannot be served due to the application\'s rate limit having been exhausted for the resource',
                     500 : 'Internal Server Error: Something is broken',
                     502 : 'Bad Gateway: Twitter is down or being upgraded',
                     503 : 'Service Unavailable: The Twitter servers are up, but overloaded with requests',
                     504 : 'Gateway timeout: The request couldn\'t be serviced due to some failure within our stack',
                 }

    def __init__(self, consumer_key, consumer_secret, access_token, access_token_secret, verify=True):
        # app
        self.__consumer_key = consumer_key
        self.__consumer_secret = consumer_secret

        # user
        self.__access_token = access_token
        self.__access_token_secret = access_token_secret

        # init internal variables
        self.__response = {}
        self.__nextMaxID = maxint
        self.__proxy = {}

        # statistics
        self.__statistics = { 'queries' : 0, 'tweets' : 0 }

        # verify
        self.authenticate(verify)

    def setProxy(self, proxy):
        if isinstance(proxy, dict) and 'https' in proxy:
            self.__proxy = proxy
        else:
            raise TwitterSearchException(1016)

    def isNextpage(self):
        if nextpage:
            return True
        return False


    def authenticate(self, verify=True):
        self.__oauth = OAuth1(self.__consumer_key,
            client_secret = self.__consumer_secret,
            resource_owner_key = self.__access_token,
            resource_owner_secret = self.__access_token_secret )
        

        if verify:
            r = requests.get(self._base_url + self._verify_url, auth=self.__oauth, proxies=self.__proxy)
            self.checkHTTPStatus(r.status_code)

    def checkHTTPStatus(self, http_status):
        if http_status in self.exceptions:
            raise TwitterSearchException(http_status, self.exceptions[http_status])

    def searchTweetsIterable(self, order):
        self.searchTweets(order)
        return self

    def sentSearch(self, url):
        if py3k:
            if not isinstance(url, str):
                raise TwitterSearchException(1009)
        else:
            if not isinstance(url, basestring):
                raise TwitterSearchException(1009)
        r = requests.get(self._base_url + self._search_url + url, auth=self.__oauth, proxies=self.__proxy)
        self.__response['meta'] = r.headers

        self.checkHTTPStatus(r.status_code)

        # using IDs to request more results - former versions used page parameter
        # see https://dev.twitter.com/docs/working-with-timelines
        given_count = int(parse(url)['count'][0])
        self.__response['content'] = r.json()

        self.__statistics['queries'] += 1
        self.__statistics['tweets'] += len(self.__response['content']['statuses'])

        if int(self.__response['content']['search_metadata']['count']) == given_count:
            # have a look for the lowest ID
            for tweet in self.__response['content']['statuses']:
              if tweet['id'] < self.__nextMaxID:
                  self.__nextMaxID = tweet['id']
            self.__nextMaxID -= 1
        else:
            self.__nextMaxID = None

        return self.__response['meta'], self.__response['content']

    def searchTweets(self, order):
        if not isinstance(order, TwitterSearchOrder):
            raise TwitterSearchException(1010)

        self._startURL = order.createSearchURL()
        self.sentSearch(self._startURL)
        return self.__response

    def searchNextResults(self):
        if not self.__nextMaxID:
            raise TwitterSearchException(1011)

        self.sentSearch("%s&max_id=%i" % (self._startURL, self.__nextMaxID))
        return self.__response

    def getMetadata(self):
        if not self.__response:
            raise TwitterSearchException(1012)
        return self.__response['meta']

    def getTweets(self):
        if not self.__response:
           raise TwitterSearchException(1013)
        return self.__response['content']

    def getStatistics(self):
        return self.__statistics

    # Iteration
    def __iter__(self):
        if not self.__response:
            raise TwitterSearchException(1014)
        self._nextTweet = 0
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        if self._nextTweet < len(self.__response['content']['statuses']):
            self._nextTweet += 1
            return self.__response['content']['statuses'][self._nextTweet-1]

        try:
            self.searchNextResults()
        except TwitterSearchException:
            raise StopIteration

        if len(self.__response['content']['statuses']) != 0:
            self._nextTweet = 1
            return self.__response['content']['statuses'][self._nextTweet-1]
        raise StopIteration
