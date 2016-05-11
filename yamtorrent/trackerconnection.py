#!/usr/bin/env python3
import bencodepy
import struct
import socket
import sys
from urllib.parse import urlencode
from urllib.parse import urlparse
from twisted.internet.defer import Deferred
from twisted.web.client import getPage
from . import PeerInfo
from pybtracker import TrackerClient
import logging
import asyncio
logger = logging.getLogger('TrackerConnection')


class TrackerError(Exception):
    pass


class TrackerConnection(object):

    def __init__(self, metadata, port, peer_id, reactor=None):
        self._metadata = metadata
        self._port = port
        self._peer_id = peer_id
        self.tracker_id = ''
        self.started = False
        self._reactor = reactor

    def start(self):
        uploaded = b'0'
        downloaded = b'0'

        left = self._metadata.full_length()

        compact = b'1'
        event = b'started'
        p = {'info_hash': self._metadata.info_hash(),
             'peer_id': self._peer_id,
             'port': self._port,
             'uploaded': uploaded,
             'downloaded': downloaded,
             'left': left,
             'compact': compact,
             'event': event}

        url = self._metadata.announce().decode()

        protocol = urlparse(url)[0]
        if protocol == 'udp':
            logger.info('udp tracker')
            return self.get_udp(url, p)
        elif protocol == 'http' or protocol == 'https':
            logger.info('%s tracker', protocol)
            return self.get_http(url, p)
        else:
            logger.info('tracker protocol:', protocol)
            d = Deferred()
            self._reactor.callLater(0.5, d.errback, ValueError('Invalid tracker protocol'))
            return d


    def get_udp(self, url, params):

        # url = url.replace('announce', 'scrape')
        print('\n')
        logger.critical('UDP Trackers are not really supported.')
        print('\n')

        logger.info(url)
        info_hash = params['info_hash'].upper()

        d = Deferred()
        async def announce():
            client = TrackerClient(announce_uri=url)
            await client.start()
            peers = await client.announce(
                b'01234567890123456789',  # infohash
                10000,                    # downloaded
                40000,                    # left
                5000,                     # uploaded
                0,                        # event (0=none)
                120                       # number of peers wanted
            )

            self._peers = list(map(lambda peer_data: PeerInfo(*peer_data), peers))
            d.callback(self)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(announce())

        # self._reactor.callLater(0.5, d.errback, ValueError('Invalid tracker protocol: udp'))
        return d

    def get_http(self, url,  params):
        tracker_addr = url + '?' + urlencode(params)
        logger.info('Connecting to tracker:', url)
        d = getPage(tracker_addr.encode())
        return d.addCallbacks(self._decode, self._page_connect_error)


    def _decode(self, content):
        try:
            response = bencodepy.decode(content)
            self._decode_peers(response[b'peers'])
        except bencodepy.exceptions.DecodingError:
            raise TrackerError('Failed to decode tracker response {}'
                               .format(self._metadata.announce()))


    def _decode_peers(self, raw_peers):
        def make_peer(peer_data):
            return PeerInfo(ip=socket.inet_ntoa(peer_data[0]),
                            port=peer_data[1])
        peers = map(make_peer, struct.iter_unpack('!4sH', raw_peers))
        self._peers = list(peers)

    def _page_connect_error(self, error):
        raise TrackerError("Failed to connect to the tracker {}"
                           .format(self._metadata.announce()))

    def get_peers(self):
        return self._peers
