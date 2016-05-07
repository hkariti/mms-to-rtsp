import sys
import socket
import re
import select
import struct
import urllib

def help():
    usage="""
Usage: %s URL

Stream MMS/RTSP url to vlc.

URL should start with mms:// or rtsp://
""" % sys.argv[0]
    print usage

#if len(sys.argv) != 2 or not sys.argv[1].startswith(('mms://', 'rtsp://')):
#    help()
#    sys.exit(1)
#
#url = sys.argv[1]
#url = re.sub("^mms", 'rtsp', url)
#
#host, path = re.sub('^[a-z]+://', '', url).split('/', 1)
#host, dummy, port = host.partition(":")
#port = port or 554
host = '132.68.3.150'
port = 554

server  = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('localhost', 554))
server.listen(1)

def handle_client(vlc):
    print "COnnecting to %s:%d" % (host, port)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, port))
    client.setblocking(0)
    client_file = client.makefile()

    original_url = None
    readbuf_size = 1024*1024
    options_request = False
    while True:
        rlist, wlist, elist = select.select([client, vlc], [], [])
        for f in rlist:
            if f is client:
                source = "backend"
                target = vlc
            else:
                source = "vlc"
                target = client
            buf = f.recv(readbuf_size)
            if not buf:
                print "%s socket disconnected" % source
                target.close()
                return
            if f is client:
                if options_request:
                    rtsp_index = buf.find("RTSP/1.0")
                    if rtsp_index != -1:
                        target.send(buf[:rtsp_index])
                        buf = buf[rtsp_index:]
                        print "Patching OPTIONS response, adding GET_PARAMETER to public methods"
                        buf = buf.replace("\r\n","\r\nPublic: GET_PARAMETER\r\n", 1)
                        options_request = False

            if f is vlc:
                match = re.match('OPTIONS ([^ ]+) RTSP/1.0', buf)
                if match:
                    print "Client sent an OPTIONS request, will save the url for later and patch the response"
                    original_url = match.groups()[0]
                    options_request = True
                if original_url:
                    match = re.search('(PLAY|PAUSE|GET_PARAMETER) ([^ ]+) RTSP/1.0', buf)
                    if match:
                        print "Replaced %s uri.\n  Orig: %s\n  Repl: %s" % (match.groups()[0], match.groups()[1], original_url)
                        buf = re.sub('(PLAY|PAUSE|GET_PARAMETER) [^ ]+ RTSP/1.0', '\\1 %s RTSP/1.0' % original_url, buf)
                #if 'Scale:' in buf:
                #    print "Replaced scale line with speed line"
                #    buf = buf.replace("Scale:", "Speed:")
            target.send(buf)

while True:
    print "Waiting for client..."
    vlc = server.accept()[0]
    vlc.setblocking(0)
    print "Connected"
    handle_client(vlc)

