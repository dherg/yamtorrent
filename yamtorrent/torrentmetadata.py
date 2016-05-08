import glob
import hashlib
import bencodepy

class TorrentMetadata(object):

    def __init__(self, filename=None, peer_id=None):
        filename = filename if filename else glob.glob('*.torrent')[0]
        if not filename:
            raise FileNotFoundError()

        self.peer_id = peer_id

        with open(filename, 'rb') as torrentfile:
            self._metadata = bencodepy.decode(torrentfile.read())

            try:
                # re-bencode the info section
                info = self._metadata[b"info"]

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
