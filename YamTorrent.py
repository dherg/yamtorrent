#!/usr/bin/env python3
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

from yamtorrent import PeerInfo, TorrentMetadata, PeerConnection, TrackerConnection, TorrentManager

import logging

def main():
    port = b'6881'
    peer_id = b'-YT0001-' + os.urandom(12)
    meta_info = None
    logger = logging.getLogger('YamTorrent')
    try:
        if len(sys.argv) <= 1:
            logger.error('NO TORRENT FILE NAME GIVEN')
            filename = None
        else:
            filename = sys.argv[1]
        meta_info = TorrentMetadata(filename, peer_id)
    except FileNotFoundError:
        logger.error('INVALID FILE NAME: ' + filename)
        sys.exit(0)
    torrent = TorrentManager(meta_info, port, peer_id)
    torrent.start()


if __name__ == '__main__':
    debugging = True
    if '--progress' in sys.argv:
        logging.basicConfig(level=logging.CRITICAL)
    elif '--verbose' in sys.argv:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    main()
