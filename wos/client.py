#!/usr/bin/env python

__all__ = ['WosClient']

import suds as _suds
import functools as _functools
from base64 import b64encode as _b64encode
from collections import OrderedDict as _OrderedDict


class WosClient():
    """Query the Web of Science.
       You must provide user and password only to user premium WWS service.

       with WosClient() as wos:
           results = wos.search(...)"""

    base_url = 'http://search.webofknowledge.com'
    auth_url = base_url + '/esti/wokmws/ws/WOKMWSAuthenticate?wsdl'
    search_url = base_url + '/esti/wokmws/ws/WokSearch?wsdl'
    searchlite_url = base_url + '/esti/wokmws/ws/WokSearchLite?wsdl'

    def __init__(self, user=None, password=None, SID=None, close_on_exit=True,
                 lite=False, proxy=None):
        """Create the SOAP clients. user and password for premium access."""

        self._SID = SID
        self._lite = lite
        self._close_on_exit = close_on_exit
        proxy = {'http': proxy} if proxy else None
        search_wsdl = self.searchlite_url if lite else self.search_url
        self._auth = _suds.client.Client(self.auth_url, proxy=proxy)
        self._search = _suds.client.Client(search_wsdl, proxy=proxy)

        if user and password:
            auth = '%s:%s' % (user, password)
            auth = _b64encode(auth.encode('utf-8')).decode('utf-8')
            headers = {'Authorization': ('Basic %s' % auth).strip()}
            self._auth.set_options(headers=headers)

    def __enter__(self):
        """Automatically connect when used with 'with' statements."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Close connection after closing the 'with' statement."""
        if self._close_on_exit:
            self.close()

    def __del__(self):
        """Close connection when deleting the object."""
        if self._close_on_exit:
            self.close()

    def _api(fn):
        """API decorator for common tests (sessions open, etc.)."""
        @_functools.wraps(fn)
        def _fn(self, *args, **kwargs):
            if not self._SID:
                raise RuntimeError('Session not open. Invoke connect() before.')
            return fn(self, *args, **kwargs)
        return _fn

    def _premium(fn):
        """Premium decorator for APIs that require premium access level."""
        @_functools.wraps(fn)
        def _fn(self, *args, **kwargs):
            if self._lite:
                raise RuntimeError('Premium API, not available in lite access.')
            return fn(self, *args, **kwargs)
        return _fn

    @staticmethod
    def make_retrieveParameters(offset=1, count=100, name='RS', sort='D'):
        """Create retrieve parameters dictionary to be used with APIs.

        :count: Number of records to display in the result. Cannot be less than
                0 and cannot be greater than 100. If count is 0 then only the
                summary information will be returned.

        :offset: First record in results to return. Must be greater than zero

        :name: Name of the field to order by. Use a two-character abbreviation
               to specify the field ('AU': Author, 'CF': Conference Title,
               'CG': Page, 'CW': Source, 'CV': Volume, 'LC': Local Times Cited,
               'LD': Load Date, 'PG': Page, 'PY': Publication Year, 'RS':
               Relevance, 'SO': Source, 'TC': Times Cited, 'VL': Volume)

        :sort: Must be A (ascending) or D (descending). The sort parameter can
               only be D for Relevance and TimesCited.
        """
        return _OrderedDict([
            ('firstRecord', offset),
            ('count', count),
            ('sortField', _OrderedDict([('name', name), ('sort', sort)]))
        ])

    def connect(self):
        """Authenticate to WOS and set the SID cookie."""
        if not self._SID:
            self._SID = self._auth.service.authenticate()
            print('Authenticated (SID: %s)' % self._SID)

        self._search.set_options(headers={'Cookie': 'SID="%s"' % self._SID})
        self._auth.options.headers.update({'Cookie': 'SID="%s"' % self._SID})
        return self._SID

    def close(self):
        """The close operation loads the session if it is valid and then closes
        it and releases the session seat. All the session data are deleted and
        become invalid after the request is processed. The session ID can no
        longer be used in subsequent requests."""
        if self._SID:
            self._auth.service.closeSession()
            self._SID = None

    @_api
    def search(self, query, count=5, offset=1, retrieveParameters=None):
        """The search operation submits a search query to the specified
        database edition and retrieves data. This operation returns a query ID
        that can be used in subsequent operations to retrieve more records."""
        return self._search.service.search(
            queryParameters=_OrderedDict([
                ('databaseId', 'WOS'),
                ('userQuery', query),
                ('queryLanguage', 'en')
            ]),
            retrieveParameters=(retrieveParameters or
                                self.make_retrieveParameters(offset, count))
        )

    @_api
    def retrieveById(self, uid, count=100, offset=1, retrieveParameters=None):
        """The retrieveById operation returns records identified by unique
        identifiers. The identifiers are specific to each database."""
        return self._search.service.retrieveById(
            databaseId='WOS',
            uid=uid,
            queryLanguage='en',
            retrieveParameters=(retrieveParameters or
                                self.make_retrieveParameters(offset, count))
        )

    @_api
    @_premium
    def citedReferences(self, uid, count=100, offset=1,
                        retrieveParameters=None):
        """The citedReferences operation returns references cited by an article
        identified by a unique identifier. You may specify only one identifier
        per request.

        :uid: Thomson Reuters unique record identifier
        """
        return self._search.service.citedReferences(
            databaseId='WOS',
            uid=uid,
            queryLanguage='en',
            retrieveParameters=(retrieveParameters or
                                self.make_retrieveParameters(offset, count))
        )

    @_api
    @_premium
    def citingArticles(self, uid, editions=None, timeSpan=None,
                       count=100, offset=1, retrieveParameters=None):
        """The citingArticles operation finds citing articles for the article
        specified by unique identifier. You may specify only one identifier per
        request. Web of Science Core Collection (WOS) is the only valid
        database for this operation.

        :uid: A unique item identifier. It cannot be None or empty string.

        :editions: List of editions to be searched. If None, user permissions
                   will be substituted.

                   Fields:
                   collection - Name of the collection
                   edition - Name of the edition

        :timeSpan: This element defines specifies a range of publication dates.
                   If timeSpan is null, then the maximum time span will be
                   inferred from the editions data.

                   Fields:
                   begin - Beginning date for this search. Format is: YYYY-MM-DD
                   end - Ending date for this search. Format is: YYYY-MM-DD
        """
        return self._search.service.citingArticles(
            databaseId='WOS',
            uid=uid,
            editions=editions,
            timeSpan=timeSpan,
            queryLanguage='en',
            retrieveParameters=(retrieveParameters or
                                self.make_retrieveParameters(offset, count))
        )

    @_api
    @_premium
    def relatedRecords(self, uid, editions=None, timeSpan=None,
                       count=100, offset=1, retrieveParameters=None):
        """The relatedRecords operation finds Related Records for the article
        specified by unique identifier. Related Records share cited references
        with the specified record. The operation returns the parent record
        along with the Related Records. The total number of Related Records for
        the parent record is shown at the end of the response. Use the retrieve
        parameter count to limit the number of Related Records returned.

        :uid: A unique item identifier. It cannot be None or empty string.

        :editions: List of editions to be searched. If None, user permissions
                   will be substituted.

                   Fields:
                   collection - Name of the collection
                   edition - Name of the edition

        :timeSpan: This element defines specifies a range of publication dates.
                   If timeSpan is null, then the maximum time span will be
                   inferred from the editions data.

                   Fields:
                   begin - Beginning date for this search. Format is: YYYY-MM-DD
                   end - Ending date for this search. Format is: YYYY-MM-DD
        """
        return self._search.service.relatedRecords(
            databaseId='WOS',
            uid=uid,
            editions=editions,
            timeSpan=timeSpan,
            queryLanguage='en',
            retrieveParameters=(retrieveParameters or
                                self.make_retrieveParameters(offset, count))
        )
