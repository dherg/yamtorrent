import sys
import requests
import hashlib
import bencodepy
import struct
import socket
import os
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.web.client import getPage

from . import PeerInfo, TorrentMetadata, PeerConnection, TrackerConnection



# manages tracker and peer connections for a single torrent
class TorrentManager(object):

    def __init__(self, meta, port, peer_id):
        self.meta = meta
        self.port = port
        self.peer_id = peer_id
        self.tracker = None # TrackerConnection

    def start(self):
        self.tracker = TrackerConnection(self.meta, self.port, self.peer_id)

        def connect_to_peer(peer_info):
            print('Connecting to peer:', str(peer_info))
            first_peer = PeerConnection(self.meta, peer_info)
            first_peer.connect(reactor)

        def success(result):
            peers = self.tracker.get_peers()
            print('Tracker returned', len(peers), 'peers.')
            # print(list(map(str, peers)))
            print(peers[0])
            connect_to_peer(peers[0])

        def error(result):
            print('error', result)

        self.tracker.start().addCallbacks(success, error)
        reactor.run()







# start n connections, query them for bitfield, aggregate bitfields into
# availability dict (piece:connection), begin downloading based on availability.
# wait before bitfield query to give time for connections to recieve bitfield?
# need different port for each connection?


