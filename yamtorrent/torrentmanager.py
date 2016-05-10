import sys
import requests
import hashlib
import bencodepy
import struct
import socket
import os
from bitstring import BitArray
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
        self.tracker = None  # TrackerConnection
        self.mybitfield = BitArray(int(self.meta.num_pieces()))

        # dict that maps PeerConnection to its bitfield
        self.bitfields = {}

        # dict mapping piece_id to list of PeerConnections with piece
        # self.availability = [0] * int(self.meta.num_pieces())  # availability: 0 if no known peers with, or PeerConnection of peer with (?)

        # dict mapping peer to Boolean connection state
        self._peers = []
        # file that we will write downloaded data to.
        self.file = None

    # create a blank .part file with name coming from torrent metadata
    def create_temp_file(self):
        print('creating blank file', self.meta.name().decode("utf-8") + '.part') # .part to indicate it is an incomplete file
        self.file = open(self.meta.name().decode("utf-8") + '.part', 'wb+')

    def start(self):
        self.tracker = TrackerConnection(self.meta, self.port, self.peer_id)

        self.create_temp_file()

        def peer_did_connect(peer):
            print('peer_did_connect')
            bitfield = peer.get_bitfield()
            if bitfield is not None:
                if peer not in self._peers:
                    self._peers.append(peer)
                # do something else here?
            else:
                peer.stop()
            print(bitfield)

        def connect_to_peer(peer_info):
            print('Connecting to peer:', str(peer_info))
            p = PeerConnection(self.meta, peer_info)
            p.connect(reactor).addCallback(peer_did_connect)

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


