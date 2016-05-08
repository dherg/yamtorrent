#!/usr/bin/env python3
import bencodepy
import struct
import socket
import sys
from urllib.parse import urlencode

from twisted.internet.defer import Deferred
from twisted.web.client import getPage
from . import PeerInfo


class TrackerError(Exception):
    pass


class TrackerConnection(object):

    def __init__(self, metadata, port, peer_id):
        self._metadata = metadata
        self._port = port
        self._peer_id = peer_id
        self.tracker_id = ''
        self.started = False

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
        tracker_addr = url + '?' + urlencode(p)
        print('Connecting to tracker:', url)
        d = getPage(tracker_addr.encode())
        return d.addCallbacks(self._decode, self._page_connect_error)

    def _decode(self, content):
        try:
            response = bencodepy.decode(content)
            # print(response)
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
