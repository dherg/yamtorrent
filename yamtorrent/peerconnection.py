import sys
import struct
import hashlib
from bitstring import BitArray
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import ClientFactory, Protocol
from twisted.internet.endpoints import TCP4ClientEndpoint
from enum import Enum
import logging

logger = logging.getLogger('PeerConnection')


class PeerConnection(object):

    PIECE_HASH_SIZE = 20 # BitTorrent standard
    BLOCK_SIZE = 16384 # 16KB

    class _States(Enum):
        WAIT_CONNECT = 0
        WAIT_HANDSHAKE = 1
        LATER = 2

    def __init__(self, meta, peer_info, protocol=None):
        self.meta = meta
        self.peer_info = peer_info
        self.bitfield = None
        self.state = self._States.WAIT_CONNECT
        self._protocol = protocol
        self._bitfield = None
        self.buf = bytearray()
        self.piece_deferreds = {}

        # need to keep track of choking/interested state for self and peer
        # connections start out as choking and not interested
        self._am_choking = True
        self._am_interested = False
        self._peer_choking = True
        self._peer_interested = False

        # storing the blocks of the piece we're working on until we get a full piece to
        # return to TorrentManager (or should we return every block on reciept and have
        # TorrentManager keep track of blocks in addition to pieces?)
        # In this model the blocks of a piece are downloaded in order (0 to piece length/BLOCK_SIZE)
        # self.piece_number = 0
        # self.next_offset = 0
        # self.piece_array = bytearray()
        # self.start_tick = 0
        self.reset_download_info()

    def reset_download_info(self):
        self.piece_number = 0
        self.next_offset = 0
        self.piece_array = bytearray()
        self.start_tick = 0

        # vars for the last piece and block
        self.last_piece_size = 0
        self.last_block_size = 0
        self.last_block_number = 0
        self.last_piece_offset = 0

    # called by TorrentManager to start download when this connection is unchoked
    def start_piece_download(self, piece_number, start_tick):

        logger.info('starting download piece %i', piece_number)
        self.send_interested()

        self.reset_download_info()
        self.piece_number = piece_number
        self.start_tick = start_tick


        if self._peer_choking:
            logger.warning('piece download requested but I\'m being choked...')
            return None # return error?

        if self.is_last_piece():
            logger.info('is last piece')
            # handle last piece
            self.calculate_last_piece()
            # figure out the block size for the initial request
            if self.last_block_number == 0:
                initial_block_size = self.last_block_size
            else:
                initial_block_size = self.BLOCK_SIZE
            # send the initial request
            self.send_request(self.piece_number, self.last_piece_offset, initial_block_size)
            d = Deferred()
            self.piece_deferreds[piece_number] = d
        else:
            # send initial request
            self.send_request(self.piece_number, self.next_offset * self.BLOCK_SIZE, self.BLOCK_SIZE)
            d = Deferred()
            self.piece_deferreds[piece_number] = d
            return d


    def calculate_last_piece(self):
        # find out how large last piece is supposed to be: lengthoffile - ((numpieces - 1) * piecesize):
        self.last_piece_size = self.meta.full_length() - ((self.meta.num_pieces() - 1) * self.meta.piece_length())

        # find out how large last block will be: last_piece_size % BLOCK_SIZE
        self.last_block_size = self.last_piece_size % self.BLOCK_SIZE
        # find (zero-based) index of last block
        self.last_block_number = int(self.last_piece_size / self.BLOCK_SIZE)
        if self.last_block_size == 0:
            self.last_block_number = self.last_block_number - 1


    # check to see if the current piece number is the last piece in the torrent
    def is_last_piece(self):
        piece_num = self.piece_number
        total_pieces = self.meta.num_pieces()
        if piece_num == total_pieces - 1:
            return True
        else:
            return False


    def get_start_tick(self):
        return self.start_tick

    def get_piece_number(self):
        return self.piece_number

    # returns whether the piece is in our bitfield
    def piece_in_bitfield(self, piece_number):
        return self._bitfield[piece_number]

    # should callback to TorrentManager
    # called when a piece is complete. the piece is in piece_array
    def piece_downloaded(self, piece_number, piece_array):
        self.piece_deferreds[piece_number].callback((self, piece_number, piece_array))

    def am_choking(self):
        return self._am_choking

    def am_interested(self):
        return self._am_interested

    def peer_choking(self):
        return self._peer_choking

    def peer_interested(self):
        return self._peer_interested

    def connect(self, reactor):
        self.done = Deferred()
        d = (TCP4ClientEndpoint(reactor, self.peer_info.ip, self.peer_info.port)
             .connect(ProtocolAdapterFactory(self)))
        d.addErrback(lambda res: self.connection_failed(res))
        self.state = self._States.WAIT_CONNECT

        return self.done

    def request_handshake(self):
        msg = struct.pack('!B', 19) + b"BitTorrent protocol" + bytearray(8) + self.meta.info_hash() + self.meta.peer_id
        self._protocol.tx_data(msg)
        self.state = self._States.WAIT_HANDSHAKE

    def rcv_handshake(self, data):
        logger.info('rcv_handshake: len = %d', len(data))
        pass

    # NOT USING RIGHT NOW
    def send_bitfield(self):
        # construct message
        msg = bytearray(2)
        # self.transport.write(msg)
        # self.state = self._States.WAIT_BITFIELD


    # Once a piece is downloaded, validate it using the hash in torrent file before returning to TorrentManager
    def validate_piece(self, piece_array):
        thishash = hashlib.sha1(piece_array).digest()
        start = self.piece_number * self.PIECE_HASH_SIZE
        if thishash == self.meta.piece_hashes()[start:start + self.PIECE_HASH_SIZE]:
            logger.info('validating piece %i: hash matched!', self.piece_number)
            self.piece_downloaded(self.piece_number, piece_array)
        else:
            logger.info('validating piece %i: hash did not match!', self.piece_number)
            # restart piece download? disconnect?
        pass

    def send_request(self, piece_number, offset, length):
        logger.debug('send_request piece %d  offset=%d  length=%d to %s', piece_number, offset, length, str(self.peer_info))

        msg = struct.pack('!IBIII', 13, 6, piece_number, int(offset), length)
        self._protocol.tx_data(msg)
        pass


    def send_keepalive(self):
        logger.info('send_keepalive to %s', str(self.peer_info))
        msg = struct.pack('!I', 0)
        self._protocol.tx_data(msg)
        pass

    def send_choke(self):
        logger.info('send_choke to %s', str(self.peer_info))
        msg = struct.pack('!I', 1) + struct.pack('!B', 0)
        self._protocol.tx_data(msg)
        self._am_choking = True
        pass

    def send_unchoke(self):
        logger.info('send_unchoke to %s', str(self.peer_info))
        msg = struct.pack('!I', 1) + struct.pack('!B', 1)
        self._protocol.tx_data(msg)
        self._am_choking = False
        pass

    def send_interested(self):
        logger.info('send_interested to %s', str(self.peer_info))
        msg = struct.pack('!I', 1) + struct.pack('!B', 2)
        self._protocol.tx_data(msg)
        self._am_interested = True

    def send_notinterested(self):
        logger.info('send_notinterested to %s', str(self.peer_info))
        msg = struct.pack('!I', 1) + struct.pack('!B', 3)
        self._protocol.tx_data(msg)
        self._am_interested = False
        pass

    # self.send_request(self.piece_number, self.next_offset * self.BLOCK_SIZE, self.BLOCK_SIZE)

    def cancel_current_download(self):
        self.send_cancel(self.piece_number, self.next_offset * self.BLOCK_SIZE, self.BLOCK_SIZE)
        # self.piece_deferreds[self.piece_number].errback(CancelError("piece number " + str(self.piece_number) + "was cancelled"))
        self.piece_deferreds.pop(self.piece_number,None)

        self.reset_download_info()


    def send_cancel(self, piece_number, offset, length):
        logger.info('send_cancel piece %d offset=%d length=%d to %s', piece_number, offset, length, str(self.peer_info))
        msg = struct.pack('!IBIII', 13, 8, piece_number, int(offset), length)
        self._protocol.tx_data(msg)
        pass


    def rcv_keepalive(self):
        logger.debug('rcv_keepalive')
        # we probably should reset a timer or something
        pass

    def rcv_choke(self, msg, msg_length):
        logger.info('rcv_choke %d', msg_length)
        self._peer_choking = True
        pass

    def rcv_unchoke(self, msg, msg_length):
        logger.info('rcv_unchoke %d', msg_length)
        self._peer_choking = False

        pass

    def rcv_interested(self, msg, msg_length):
        logger.info('rcv_interested %d', msg_length)
        self._peer_interested = True
        pass

    def rcv_notinterested(self, msg, msg_length):
        logger.info('rcv_notinterested %d', msg_length)
        self._peer_interested = False
        pass

    def rcv_have(self, msg, msg_length):
        logger.debug('rcv_have %d', msg_length)

        # update bitfield to reflect
        have_id = struct.unpack("!I",msg[1:msg_length])[0]
        try:
            self._bitfield[have_id] = 1
        except TypeError:
            logger.warning('Received have for client that did not send a valid bitfield.')
            pass

    def rcv_bitfield(self, msg, msg_length):
        # parse bitfield
        bitfield = BitArray(bytes=msg[1:msg_length])

        # validate bitfield
        def validate_bitfield(bitfield):
            num_pieces = self.meta.num_pieces()
            length = len(bitfield)
            if (length < num_pieces or
                (length > num_pieces and
                 any(bitfield[num_pieces:length]))):
                return False
            return True

        if validate_bitfield(bitfield):
            self._bitfield = bitfield
        else:
            self._bitfield = None

        self.done.callback(self)

    def rcv_request(self, msg, msg_length):
        logger.info('rcv_request %d', msg_length)
        pass

    def rcv_piece(self, msg, msg_length):
        piece_number = int.from_bytes(msg[1:5], 'big')
        offset = int.from_bytes(msg[5:9], 'big')
        logger.debug('rcv_piece: id={} off={} len={}'.format(piece_number, offset, msg_length - 1))

        # handle last pieces separately
        if self.is_last_piece():
            # append if it is the block we are looking for
            if offset == self.last_piece_offset:
                self.piece_array = self.piece_array + msg[9:]
                # calculate the next offset
                self.last_piece_offset = self.last_piece_offset + self.BLOCK_SIZE
            else:
                logger.debug('recieved offset=%d wanted offset=%d', offset, self.last_piece_offset)

            # check to see if the piece is complete. otherwise request the next piece
            if (self.last_piece_offset >= self.last_piece_size): # then piece is complete
                logger.info('piece number %d complete', piece_number)
                self.validate_piece(self.piece_array)
            elif self._am_interested and not self._peer_choking:
                # figure out the length to request. min(BLOCK_SIZE, piece_length - next_offset)
                request_length = min(self.BLOCK_SIZE, self.last_piece_size - self.last_piece_offset)
                self.send_request(self.piece_number, self.last_piece_offset, request_length)
            return


        # append to piece if it is the block we were looking for
        if offset == self.next_offset * self.BLOCK_SIZE:
            self.piece_array = self.piece_array + msg[9:]
            self.next_offset = self.next_offset + 1
        else:
            logger.debug('recieved offset=%d wanted offset=%d', offset, self.next_offset * self.BLOCK_SIZE)

        # check to see if piece is complete. otherwise request the next piece if we can
        if (self.next_offset * self.BLOCK_SIZE) >= self.meta.piece_length():
            logger.info('piece number %d complete', piece_number)
            self.validate_piece(self.piece_array)
        elif self._am_interested and not self._peer_choking:
            self.send_request(self.piece_number, self.next_offset * self.BLOCK_SIZE, self.BLOCK_SIZE)


    def rcv_cancel(self, msg, msg_length):
        logger.info('rcv_cancel %d', msg_length)
        pass

    def rcv_port(self, msg, msg_length):
        logger.info('rcv_port %d', msg_length)
        pass

    def process_buf(self):
        # if this should a received handshake
        if (len(self.buf) > 0) and (len(self.buf) >= 49 + self.buf[0]) and (self.state == self._States.WAIT_HANDSHAKE):

            pstrlen = self.buf[0]
            pstr = self.buf[1:pstrlen + 1]
            reserved = self.buf[pstrlen + 1:pstrlen + 9]
            info_hash = self.buf[pstrlen + 9:pstrlen+29]
            peer_id = self.buf[pstrlen+29:pstrlen+49]

            # check that this is the handshake receipt
            if (pstr == b"BitTorrent protocol") and (info_hash == self.meta.info_hash()):

                self.state = self._States.LATER
                data = self.buf[:pstrlen+49]

                self.buf = self.buf[pstrlen+49:]
                logger.debug('handshake match.')

                return data, 0

            else:
                logger.info('PROBABLY SHOULD DROP CONNECTION B/C BAD HANDSHAKE')

        # if we don't even have a length at the start
        if len(self.buf) < 4:
            return None, 0

        msg_length = struct.unpack("!I", self.buf[:4])[0]

        # if we have the full message in the buffer
        if len(self.buf) >= 4 + msg_length:
            data = self.buf[:msg_length+4]

            # remove message from buffer
            self.buf = self.buf[msg_length+4:]

            return data, msg_length


        # can't figure out this line, but it fails if there's not enough left
        try:
            if self.buf[4] != 7:
                logger.debug('process_buf[unhandled] len=%d want=%d type=%d', len(self.buf), msg_length, self.buf[4])
        except IndexError:
            logger.warning('not enough in buffer to check type')

        return None, 0

    def handle_message(self, msg, msg_length):
        # if this is a keep-alive
        if msg_length == 0:
            self.rcv_keepalive()
            return None

        msg_type = msg[4]

        options = {
            0: self.rcv_choke,
            1: self.rcv_unchoke,
            2: self.rcv_interested,
            3: self.rcv_notinterested,
            4: self.rcv_have,
            5: self.rcv_bitfield,
            6: self.rcv_request,
            7: self.rcv_piece,
            8: self.rcv_cancel,
            9: self.rcv_port
        }

        try:
            options[msg_type](msg[4:], msg_length)
        except KeyError:
            logger.info('received unknown message_id %d', msg_type)

    # this is called async by your event loop
    def rx_data(self, data):

        self.buf += data

        next_message, msg_length = self.process_buf()

        if next_message is not None:
            self.handle_message(next_message, msg_length)

            # check if there are more messages
            self.rx_data(bytearray())

        # # parse data here
        # if self.state == self._States.WAIT_HANDSHAKE:
        #     self.rcv_handshake(data)
        #     self.request_bitfield()
        # elif self.state == self._States.WAIT_BITFIELD:
        #     self.rcv_bitfield(data)
        # else:
        #     # unknown message
        #     pass

    def did_connect(self, protocol):
        self._protocol = protocol
        self.request_handshake()

    def connection_lost(self):
        logger.info('connection lost!')

    def connection_failed(self, result):
        logger.info('failed to connect to peer!')

    # Properties
    def get_bitfield(self):
        return self._bitfield

class ProtocolAdapter(Protocol):

    def __init__(self, delegate):
        self._delegate = delegate

    def tx_data(self, data):
        self.transport.write(data)

    # overridden from twisted.protocol.Protocol
    def dataReceived(self, data):
        if self._delegate is not None:
            self._delegate.rx_data(data)

    # overridden from twisted.protocol.Protocol
    def connectionMade(self):
        if self._delegate is not None:
            self._delegate.did_connect(self)

    def connectionLost(self, reason):
        if self._delegate is not None:
            self._delegate.connection_lost()

    def stop(self):
        self.transport.loseConnection()


class ProtocolAdapterFactory(ClientFactory):

    def __init__(self, delegate):
        self.done = Deferred()
        self._delegate = delegate

    def buildProtocol(self, address):
        return ProtocolAdapter(self._delegate)


# class CancelError(Exception):
#     def __init__(self, value):
#         self.value = value
#     def __str__(self):
#         return repr(self.value)
