import glob
import hashlib
import bencodepy

class TorrentFile(object):

    def __init__(self, filename=None):
        filename = filename if filename else glob.glob('*.torrent')[0]
        if not filename:
            raise FileNotFoundError()

        with open(filename, 'rb') as torrentfile:
            self.torrent_dict = bencodepy.decode(torrentfile.read())

            # re-bencode the info section
            self.info = self.torrent_dict[b"info"]
            bencodedinfo = bencodepy.encode(self.info)

            # SHA1 hash of info section
            self.info_hash = hashlib.sha1(bencodedinfo).digest()

    def get_file_list(self):
        try:
            return self.info[b'files']
        except KeyError:
            return None

    def get_length(self):
        files = self.get_file_list()
        length = 0
        if files:
            for f in files:
                length += f[b'length']
        else:
            length = self.info[b'length']
        return length
