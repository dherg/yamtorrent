import sys
import requests
import hashlib
import bencodepy
import struct
import socket
import os
from bitstring import BitArray
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.internet.defer import Deferred
from twisted.web.client import getPage

from . import PeerInfo, TorrentMetadata, PeerConnection, TrackerConnection

TICK_DELAY = 5

# manages tracker and peer connections for a single torrent
class TorrentManager(object):

    def __init__(self, meta, port, peer_id):
        self.meta = meta
        self.port = port
        self.peer_id = peer_id
        self.num_ticks = 0
        self.tracker = None  # TrackerConnection
        self.next_piece = 0
        self.mybitfield = BitArray(int(self.meta.num_pieces()))

        # dict mapping piece_id to a PeerConnection
        self.requests = {}

        # dict mapping peer to Boolean connection state
        self._peers = []
        # file that we will write downloaded data to.
        self.file = None

    # takes a bytearray (piece_array) and writes it to the correct
    # position in file (piece_number * piece_length)
    # piece_length is given in torrent metadata
    def write_piece_to_file(self, piece_number, piece_array):
        self.file.seek(piece_number * self.meta.piece_length())
        self.file.write(piece_array)

    # create a blank .part file with name coming from torrent metadata
    def create_temp_file(self):
        print('creating blank file', self.meta.name().decode("utf-8") + '.part') # .part to indicate it is an incomplete file
        self.file = open(self.meta.name().decode("utf-8") + '.part', 'wb+')

    def start(self):
        self.tracker = TrackerConnection(self.meta, self.port, self.peer_id)

        self.create_temp_file()

        def connect_to_peer(peer_info):
            print('Connecting to peer:', str(peer_info))
            p = PeerConnection(self.meta, peer_info)
            p.connect(reactor).addCallback(self.peer_did_connect)

        def tracker_connect_success(result):
            peers = self.tracker.get_peers()
            print('Tracker returned', len(peers), 'peers.')
            # print(list(map(str, peers)))
            print(peers[0])
            connect_to_peer(peers[0])

        def tracker_connect_error(result):
            print('tracker_connect_error', result)

        self.tracker.start().addCallbacks(tracker_connect_success,
                                          tracker_connect_error)

        LoopingCall(self.timer_tick).start(TICK_DELAY)

        reactor.run()

    def timer_tick(self):
        self.num_ticks += 1

        idle_peers = self.idle_peers()
        if self.next_piece >= self.meta.num_pieces():
            return

        unchoked = filter(lambda p: not p.peer_choking(), idle_peers)
        for p in unchoked:
            self.requests[self.next_piece] = p
            d = p.start_piece_download(self.next_piece)
            d.addCallbacks(self.peer_piece_success, self.peer_piece_error)
        # print('has_piece:', self.has_piece(1))
        # print('tick =', self.num_ticks)

    def busy_peers(self):
        return set([p for k, p in self.requests.items()])

    def idle_peers(self):
        return set(self._peers) - self.busy_peers()

    def has_piece(self, piece_id):
        return self.mybitfield[piece_id]

    ######## PEER CALLBACKS  #################

    def peer_did_connect(self, peer):
        print('peer_did_connect', str(peer.peer_info))
        bitfield = peer.get_bitfield()
        if bitfield is not None:
            self._peers.append(peer)
            # do something else here?
        else:
            peer.stop()
        print(bitfield)

    def peer_piece_success(self, result):
        (peer, piece_id, piece_array) = result
        print('peer_received_piece', str(peer.peer_info))
        print(piece_id)

        # TODO this is not correct
        self.next_piece = piece_id + 1

        # TODO
        # add to availability table to show that we have downloaded this piece

        self.requests.pop(piece_id, None)


    def peer_piece_error(self, peer, piece_id, error):
        print('peer_piece_error', str(peer.peer_info))
        pass




# start n connections, query them for bitfield, aggregate bitfields into
# availability dict (piece:connection), begin downloading based on availability.
# wait before bitfield query to give time for connections to recieve bitfield?
# need different port for each connection?


