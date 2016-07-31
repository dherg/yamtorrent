import glob
import hashlib
import bencodepy
import logging

logger = logging.getLogger('TorrentMetadata')

class TorrentMetadata(object):
    PIECE_HASH_SIZE = 20

    def __init__(self, filename=None, peer_id=None):

        # automatically opens first .torrent file in directory if no file given.
        # (desired behavior?)
        filename = filename if filename else glob.glob('*.torrent')[0]
        if not filename:
            raise FileNotFoundError()

        self.peer_id = peer_id

        logger.debug('opening torrent file {}'.format(filename))

        with open(filename, 'rb') as torrentfile:
            self._metadata = bencodepy.decode(torrentfile.read())
            

            try:
                # re-bencode the info section
                info = self._metadata[b"info"]

                # piece hash values
                self._piece_hashes = info[b'pieces']


                # SHA1 hash of info section
                self._info_hash = hashlib.sha1(bencodepy.encode(info)).digest()
                self._name = info[b'name']
                self._announce = self._metadata[b'announce']



                if b'length' in info:
                    # torrent only has one file
                    self._folder = ''
                    self._files = list((info[b'name'], info[b'length']))
                    self._length = info[b'length']
                else:
                    self._folder = info[b'name']
                    self._files = [(f[b'path'], f[b'length']) for f in info[b'files']]
                    self._length = sum([l for (p, l) in self._files])

                self._num_pieces = int(len(info[b'pieces'])/self.PIECE_HASH_SIZE)
                self._piece_length = info[b'piece length']
            except KeyError:
                raise ValueError('Invalid Torrent File: Missing a field!')

    def announce(self):
        return self._announce

    def info_hash(self):
        return self._info_hash

    def file_list(self):
        return self._files

    def full_length(self):
        return self._length

    def name(self):
        return self._name

    def num_pieces(self):
        return self._num_pieces

    def piece_length(self):
        return self._piece_length

    def piece_hashes(self):
        return self._piece_hashes
