import sys
import requests
import hashlib
import bencodepy
import struct
import socket
import os
from bitstring import BitArray
from twisted.internet import reactor as treactor
from twisted.internet.task import LoopingCall
from twisted.internet.defer import Deferred
from twisted.web.client import getPage
import logging
from progressbar import ProgressBar
import progressbar
from enum import Enum

from . import PeerInfo, TorrentMetadata, PeerConnection, TrackerConnection

TICK_DELAY = 5
TIMEOUT = 120

logger = logging.getLogger('TorrentManager')

# manages tracker and peer connections for a single torrent
class TorrentManager(object):

    class _States(Enum):
        INITIAL = 0
        TRACKER = 1
        CONNECTING = 2
        DOWNLOADING = 3
        SEEDING = 4
        DONE = 5
        IDLE = 6

    def __init__(self, meta, port, peer_id, reactor=None):
        self.meta = meta
        self.port = port
        self.peer_id = peer_id
        self.num_ticks = 0
        self.tracker = None  # TrackerConnection
        self.next_piece = 0
        self.mybitfield = BitArray(int(self.meta.num_pieces()))
        self._reactor = reactor if reactor else treactor
        self._bar = None
        self.state = self._States.INITIAL

        # self.finished_downloading = False

        # the pieces we desire, in order
        self.desire = list(range(0,int(self.meta.num_pieces())))

        # dict mapping piece_id to a PeerConnection
        self.requests = {}

        # dict mapping peer to Boolean connection state
        self._peers = []

        # file that we will write downloaded data to.
        self.file = None

    def finished_bitfield(self):
        return all(self.mybitfield[0:int(self.meta.num_pieces())])

    # takes a bytearray (piece_array) and writes it to the correct
    # position in file (piece_number * piece_length)
    # piece_length is given in torrent metadata
    def write_piece_to_file(self, piece_number, piece_array):
        self.file.seek(piece_number * self.meta.piece_length())
        self.file.write(piece_array)

    # create a blank .part file with name coming from torrent metadata
    def create_temp_file(self):
        logger.info('creating blank file %s', self.meta.name().decode("utf-8") + '.part') # .part to indicate it is an incomplete file
        self.file = open(self.meta.name().decode("utf-8") + '.part', 'wb+')

    # add a piece number to desire
    # current implementation sticks it in in order
    def add_to_desire(self, piece_id):

        # loop until we find something to put it before
        for i in range(0, len(self.desire)):
            if piece_id < self.desire[i]:
                self.desire.insert(i,piece_id)
                return

        # if we can't find something to put it before, put
        # it at the end
        self.desire.append(piece_id)
        return

    # pick the next piece that we would like to request from a particular peer
    def pick_next_piece(self, peer):

        # loop through the ordered array of pieces we desire until we get
        # to one that this peer has, then return that one, and note that we no longer
        # desire it
        for d in self.desire:
            if peer.piece_in_bitfield(d):
                self.desire.remove(d)
                return d

        # if we there are no pieces we desire that this peer has
        return None

    def start(self):
        self.tracker = TrackerConnection(self.meta, self.port, self.peer_id, self._reactor)

        self.create_temp_file()

        def connect_to_peer(peer_info):
            logger.info('Connecting to peer: %s', str(peer_info))
            p = PeerConnection(self.meta, peer_info)
            p.connect(self._reactor).addCallback(self.peer_did_connect)

        def tracker_connect_success(result):
            peers = self.tracker.get_peers()
            # print(peers)

            logger.info('Tracker returned %d peers.', len(peers))
            # print(list(map(str, peers)))
            # print(peers[0])

            self.state = self._States.CONNECTING

            # connect_to_peer(peers[0])
            # connect_to_peer(peers[1])
            for p in peers:
                connect_to_peer(p)

        def tracker_connect_error(result):
            logger.error('tracker_connect_error %s', str(result))

        self.tracker.start().addCallbacks(tracker_connect_success,
                                          tracker_connect_error)

        LoopingCall(self.timer_tick).start(TICK_DELAY)

        self._reactor.run()

    def timer_tick(self):
        self.num_ticks += 1

        if self.state == self._States.DOWNLOADING and not self._bar and '--progress' in sys.argv:
            num_pieces = self.meta.num_pieces()

            self._bar = progressbar.ProgressBar(maxval=num_pieces)
            self._bar.start()
        elif self._bar is not None:
            self._bar.update(sum(self.mybitfield))

        if self.state == self._States.DONE:
            bar.finish()



        # could use num_ticks as a timer for timing out requests
        # would simply require us to pass the peerconnection the
        # value of num_ticks at the time of initiation
        # and if any time timer_tick is called, and the value of the peer
        # connection is greater than x ticks from the values of num_ticks
        # here, we can cancel the request.


        # if we haven't finished downloading all pieces yet
        if self.state == self._States.DOWNLOADING:
            idle_peers = self.idle_peers()

            # if we've got all the pieces
            if self.finished_bitfield():

                # begin seeding
                self.state == self._States.SEEDING

                # self.finished_downloading = True
                logger.info('WE HAVE ALL THE PIECES')

                # rename the file to remove .part
                self.file.close()
                try:
                    os.rename(self.meta.name().decode("utf-8") + '.part', self.meta.name().decode("utf-8"))
                except OSError as e:
                    logger.error('couldn\'t rename completed file to remove .part')

                return
            # if self.next_piece >= self.meta.num_pieces():
            #     return

            # might not be finished, but can't do anything
            if len(self.desire) == 0:
                return


            # figure out which peers we can be using
            unchoked = filter(lambda p: not p.peer_choking(), idle_peers)
            for p in unchoked:

                # self.requests[self.next_piece] = p
                # d = p.start_piece_download(self.next_piece)

                piece_to_request = self.pick_next_piece(p)
                self.requests[piece_to_request] = p
                d = p.start_piece_download(piece_to_request, self.num_ticks)
                d.addCallbacks(self.peer_piece_success, self.peer_piece_error)

            # check for timeouts among the currently downloading peers
            busy = self.busy_peers()
            for p in busy:

                # if it has timed out
                p_start_tick = p.get_start_tick()
                diff = self.num_ticks - p_start_tick
                if diff * TICK_DELAY > TIMEOUT:

                    # get the piece number it is downloading
                    piece_id = p.get_piece_number()

                    logger.info("PEER IS CANCELLING PIECE " + str(piece_id))

                    # tell it to cancel
                    p.cancel_current_download()

                    # remove the piece/peer from requests
                    self.requests.pop(piece_id, None)

                    # add the piece back to desired
                    self.add_to_desire(piece_id)


        if self.state == self._States.SEEDING:
            self.state == self._States.DONE

        if self.state == self._States.DONE:
            logger.info('WE ARE QUITTING')

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
        logger.info('peer_did_connect %s', str(peer.peer_info))

        # we can now begin downloading
        self.state = self._States.DOWNLOADING

        bitfield = peer.get_bitfield()
        if bitfield is not None:
            self._peers.append(peer)
            # do something else here?
        else:
            peer.stop()
        logger.debug(bitfield)

    def peer_piece_success(self, result):
        (peer, piece_id, piece_array) = result
        logger.info('received_piece %d from %s.', piece_id, str(peer.peer_info))
        if self._bar is not None:
            self._bar.update(sum(self.mybitfield))
        #if we already had this piece, don't bother
        if self.mybitfield[piece_id] == 1:
            return


        #write this piece to file
        self.write_piece_to_file(piece_id, piece_array)

        # add to availability table to show that we have downloaded this piece
        self.mybitfield[piece_id] = 1

        # TODO this is not correct
        # self.next_piece = piece_id + 1




        self.requests.pop(piece_id, None)


    def peer_piece_error(self, peer, piece_id, error):
        logger.error('peer_piece_error', str(peer.peer_info))
        pass




# start n connections, query them for bitfield, aggregate bitfields into
# availability dict (piece:connection), begin downloading based on availability.
# wait before bitfield query to give time for connections to recieve bitfield?
# need different port for each connection?


