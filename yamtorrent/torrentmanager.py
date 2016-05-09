#!/usr/bin/env python3
import bencodepy
import struct
import socket
import sys
from urllib.parse import urlencode

from twisted.internet.defer import Deferred
from twisted.web.client import getPage
from . import PeerInfo


# manages tracker and peer connections for a single torrent
class TorrentManager(object):

	def __init__(self, meta, port, peer_id):
		self.meta = meta
		self.port = port
		self.peer_id = peer_id





# start n connections, query them for bitfield, aggregate bitfields into
# availability dict (piece:connection), begin downloading based on availability.
# wait before bitfield query to give time for connections to recieve bitfield?
# need different port for each connection?

