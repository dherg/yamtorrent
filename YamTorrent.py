import sys
import bencode
import requests
import hashlib

def main():

	# open file in binary
	try:
		torrentfile = open(sys.argv[1], "rb").read()
	except IOError:
		print("BAD FILE NAME: " + sys.argv[1])
		exit()

	# dictionary of torrent file
	torrentdict = bencode.bdecode(torrentfile)

	# re-bencode the info section
	info = torrentdict.get("info")
	bencodedinfo = bencode.bencode(info)
	# print(bencodedinfo)

	# SHA1 hash of info section
	sha1 = hashlib.sha1(bencodedinfo)
	infohash = sha1.digest()
	# print(type(bencodedinfo))
	for char in infohash:
		print(hex(ord(char)))




	# print(infohash)

if __name__ == "__main__":
	main()
