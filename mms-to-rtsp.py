import sys
import socket
import re
import select
import struct
import urllib
import subprocess

def help():
    usage="""
Usage: %s URL

Stream MMS/RTSP url to vlc.
This will start a proxy and will launch vlc (via 'open -a vlc') to
read the given stream from the proxy.

URL should start with mms:// or rtsp://
""" % sys.argv[0]
    print usage

def patch_server_data(buf, state):
    ## Patch OPTIONS response to include GET_PARAMETER as public method
    rtsp_index = buf.find("RTSP/1.0")
    if rtsp_index != -1:
        target.send(buf[:rtsp_index])
        buf = buf[rtsp_index:]
        print "Patching OPTIONS response, adding GET_PARAMETER to public methods"
        buf = buf.replace("\r\n","\r\nPublic: GET_PARAMETER\r\n", 1)
        state['options_patch_needed'] = False
    return buf

def patch_vlc_data(buf, state):
    ## OPTIONS request are important. We get the escaped url to be used later in other requests,
    ## and we mark the server's response to be patched for GET_PARAMETER
    match = re.match('OPTIONS ([^ ]+) RTSP/1.0', buf)
    if match:
        print "Client sent an OPTIONS request, will save the url for later and patch the response"
        state['original_url'] = match.groups()[0]
        state['options_patch_needed'] = True

    ## PLAY/PAUSE/GET_PARAMETER requests have an escaped URI that confused the server, replace it with
    ## an unescaped URI that we previously got from the OPTIONS request
    if original_url:
        match = re.search('(PLAY|PAUSE|GET_PARAMETER) ([^ ]+) RTSP/1.0', buf)
        if match:
            buf = re.sub('(PLAY|PAUSE|GET_PARAMETER) [^ ]+ RTSP/1.0', '\\1 %s RTSP/1.0' % original_url, buf)
            print "Replaced %s uri.\n  Orig: %s\n  Repl: %s" % (match.groups()[0], match.groups()[1], original_url)

def handle_client(host, port, vlc):
    print "Connecting to stream source at %s:%d" % (host, port)
    stream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    stream.connect((host, port))
    stream.setblocking(0)
    stream_file = client.makefile()
    print "Connected"

    state = dict(original_url=None, options_patch_needed=False)
    readbuf_size = 1024*1024
    # Read from all buffers with data in them until one is at EOF
    while True:
        rlist, wlist, elist = select.select([client, vlc], [], [])
        for source in rlist:
            if source is stream:
                source_name = "backend"
                target = vlc
            else:
                source_name = "vlc"
                target = client
            buf = source.recv(readbuf_size)
            # Check EOF
            if not buf:
                print "%s socket disconnected" % source_name
                target.close()
                return
            # Patch data from the server
            if source is stream:
                buf = patch_server_data(buf, state)
            # Patch data from VLC
            if source is vlc:
                buf = patch_vlc_data(buf, state)
            target.send(buf)

def main():
    if len(sys.argv) != 2 or not sys.argv[1].startswith(('mms://', 'rtsp://')):
        help()
        sys.exit(1)

    url = sys.argv[1]
    url = re.sub("^mms", 'rtsp', url)

    server_host, path = re.sub('^[a-z]+://', '', url).split('/', 1)
    server_host, dummy, server_port = server_host.partition(":")
    server_port = server_port or 554

    print "Starting proxy"
    server  = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('localhost', 0))
    server.listen(1)
    local_host, local_port = server.getsockname()
    print "Started. Listening on port %d" % local_port
    #host = '132.68.3.150'
    #port = 554

    print "Starting VLC"
    local_url = 'rtsp://%s:%s/%s' % (local_host, local_port, path)
    subprocess.Popen(['open', '-a', 'vlc', local_url])
    # TODO: set a timeout on the waiting here
    while True:
        print "Waiting for client..."
        vlc = server.accept()[0]
        vlc.setblocking(0)
        print "Connected"
        handle_client(server_host, server_port, vlc)

main()
