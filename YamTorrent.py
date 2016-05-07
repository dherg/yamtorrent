import sys
# import bencode
import requests
import hashlib
import bencodepy

def main():

	# open file in binary
	try:
		torrentfile = open(sys.argv[1], "rb").read()
	except IOError:
		print("BAD FILE NAME: " + sys.argv[1])
		exit()

	print("BEGINNING")

	# dictionary of torrent file
	# torrentdict = bencode.bdecode(torrentfile)
	torrentdict = bencodepy.decode(torrentfile)
	# print(torrentdict)
	# print(type(torrentdict))

	# re-bencode the info section
	info = torrentdict[b"info"]
	# print(info)
	bencodedinfo = bencodepy.encode(info)
	# print(info)
	# print(bencodedinfo)



	#COMPUTE PARAMETERS FOR ANNOUNCE

	# SHA1 hash of info section
	sha1 = hashlib.sha1(bencodedinfo)
	info_hash = sha1.digest()
	# print(type(bencodedinfo))
	# for char in info_hash:
	# 	print(hex(char))
	# 	print(char)

	peer_id = (hashlib.sha1(b"0")).digest()
	port = "6881"
	uploaded = "0"
	downloaded = "0"

	try:
		left = 0
		for f in info[b"files"]:
			left += f[b"length"]
	except KeyError:
		left = info[b"length"]

	compact = "1"
	event = "started"

	url = torrentdict[b"announce"]


	p = {"info_hash": info_hash, "peer_id": peer_id, "port": port, "uploaded": uploaded, "downloaded": downloaded, "left": left, "compact": compact, "event": event}
	r = requests.get(url.decode(), params=p)

	# print(info_hash)
	# print(bencodedinfo)

	# with open("temp.txt",'wb') as f:
	# 	f.write(r.text.encode())

	print(r.text)
	print(r.url)
	print(r.text[0])
	print(r.text[362])
	print('CONTENT')
	print(r.content)
	print('END CONTENT')

	#this doesn't work
	response = bencodepy.decode(r.content)
	print(response)


if __name__ == "__main__":
	main()
