import sys
import struct
import hashlib
from bitstring import BitArray
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import ClientFactory, Protocol
from twisted.internet.endpoints import TCP4ClientEndpoint
from enum import Enum


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
        self.piece_number = 0
        self.next_offset = 0
        self.piece_array = bytearray()

    # called by TorrentManager to start download when this connection is unchoked
    def start_piece_download(self, piece_number):

        print('starting download piece', piece_number)
        self.send_interested()
        self.piece_number = piece_number
        self.next_offset = 0
        self.piece_array = bytearray()
        if self._peer_choking:
            print('piece download requested but I\'m being choked...')
            return None # return error?

        # test download
        self.send_request(self.piece_number, self.next_offset * self.BLOCK_SIZE, self.BLOCK_SIZE)
        d = Deferred()
        self.piece_deferreds[piece_number] = d
        return d

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
        print('rcv_handshake:', data)
        print(len(data))
        pass

    # NOT USING RIGHT NOW
    def send_bitfield(self):
        # construct message
        msg = bytearray(2)
        # self.transport.write(msg)
        # self.state = self._States.WAIT_BITFIELD


    # Once a piece is downloaded, validate it using the hash in torrent file before returning to TorrentManager
    def validate_piece(self, piece_array):
        print('validating piece', self.piece_number)
        thishash = hashlib.sha1(piece_array).digest()

        start = self.piece_number * self.PIECE_HASH_SIZE
        if thishash == self.meta.piece_hashes()[start:start + self.PIECE_HASH_SIZE]:
            print('hash matched!')
            self.piece_downloaded(self.piece_number, piece_array)
        else:
            print('hash did not match...')
            # restart piece download? disconnect?
        pass

    def send_request(self, piece_number, offset, length):
        print('send_request piece', piece_number, 'offset', offset, 'length' , length, 'to', self.peer_info)

        msg = struct.pack('!IBIII', 13, 6, piece_number, int(offset), length)
        self._protocol.tx_data(msg)
        pass


    def send_keepalive(self):
        print('send_keepalive to', self.peer_info)
        msg = struct.pack('!I', 0)
        self._protocol.tx_data(msg)
        pass

    def send_choke(self):
        print('send_choke to', self.peer_info)
        msg = struct.pack('!I', 1) + struct.pack('!B', 0)
        self._protocol.tx_data(msg)
        self._am_choking = True
        pass

    def send_unchoke(self):
        print('send_unchoke to', self.peer_info)
        msg = struct.pack('!I', 1) + struct.pack('!B', 1)
        self._protocol.tx_data(msg)
        self._am_choking = False
        pass

    def send_interested(self):
        print('send_interested to', self.peer_info)
        msg = struct.pack('!I', 1) + struct.pack('!B', 2)
        self._protocol.tx_data(msg)
        self._am_interested = True

    def send_notinterested(self):
        print('send_notinterested to', self.peer_info)
        msg = struct.pack('!I', 1) + struct.pack('!B', 3)
        self._protocol.tx_data(msg)
        self._am_interested = False
        pass

    # self.send_request(self.piece_number, self.next_offset * self.BLOCK_SIZE, self.BLOCK_SIZE)

    def send_cancel(self, piece_number, offset, length):
        print('send_cancel piece', piece_number, 'offset', offset, 'length' , length, 'to', self.peer_info)
        msg = struct.pack('!IBIII', 13, 8, piece_number, int(offset), length)
        self._protocol.tx_data(msg)
        pass


    def rcv_keepalive(self):
        print('rcv_keepalive')
        # we probably should reset a timer or something
        pass

    def rcv_choke(self, msg, msg_length):
        print('rcv_choke', msg_length)
        self._peer_choking = True
        pass

    def rcv_unchoke(self, msg, msg_length):
        print('rcv_unchoke', msg_length)
        self._peer_choking = False

        pass

    def rcv_interested(self, msg, msg_length):
        print('rcv_interested', msg_length)
        self._peer_interested = True
        pass

    def rcv_notinterested(self, msg, msg_length):
        print('rcv_notinterested', msg_length)
        self._peer_interested = False
        pass

    def rcv_have(self, msg, msg_length):
        print('rcv_have', msg_length)

        # update bitfield to reflect
        have_id = struct.unpack("!I",msg[1:msg_length])[0]
        self._bitfield[have_id] = 1

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
        print('rcv_request', msg_length)
        pass

    def rcv_piece(self, msg, msg_length):
        piece_number = int.from_bytes(msg[1:5], 'big')
        offset = int.from_bytes(msg[5:9], 'big')
        print('rcv_piece: id={} off={} len={}'.format(piece_number, offset, msg_length - 1))

        # append to piece if it is the block we were looking for
        if offset == self.next_offset * self.BLOCK_SIZE:
            self.piece_array = self.piece_array + msg[9:]
            self.next_offset = self.next_offset + 1
        else:
            print('recieved offset', offset, 'wanted offset', self.next_offset * self.BLOCK_SIZE)

        # check to see if piece is complete. otherwise request the next piece if we can
        # TODO: handle last pieces (i.e. when there will be a block that is not standard size)
        if (self.next_offset * self.BLOCK_SIZE) >= self.meta.piece_length():
            print('piece number', piece_number, 'complete!')
            self.validate_piece(self.piece_array)
        elif self._am_interested and not self._peer_choking:
            self.send_request(self.piece_number, self.next_offset * self.BLOCK_SIZE, self.BLOCK_SIZE)


    def rcv_cancel(self, msg, msg_length):
        print('rcv_cancel', msg_length)
        pass

    def rcv_port(self, msg, msg_length):
        print('rcv_port', msg_length)
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
                print('handshake match.')

                return data, 0

            else:
                print('PROBABLY SHOULD DROP CONNECTION B/C BAD HANDSHAKE')

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
                print('process_buf[unhandled] len=', len(self.buf), 'want=', msg_length, 'type = ', self.buf[4])
        except builtins.IndexError:
            print('not enough in buffer to check type')

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

        options[msg_type](msg[4:], msg_length)

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
        print('connection lost!')

    def connection_failed(self, result):
        print('failed to connect to peer!')

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
