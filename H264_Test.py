import subprocess as sp

FFMPEG_BIN = "/usr/bin/ffmpeg"
FFPLAY_BIN = "/usr/bin/ffplay"

h264_encode = [FFMPEG_BIN,
               '-i', '/dev/video0',
               '-r', '5',  # FPS
               '-pix_fmt', 'bgr24',  # opencv requires bgr24 pixel format.
               '-vcodec', 'h264',
               '-an', '-sn',  # disable audio processing
               '-f', 'image2pipe', '-']
encode_pipe = sp.Popen(h264_encode, stdout=sp.PIPE, bufsize=10)

h264_decode = [FFPLAY_BIN,
               '-vcodec', 'h264',
               '-i', '-']

decode_pipe = sp.Popen(h264_decode, stdin=sp.PIPE)

try:
    while True:
        pass
except KeyboardInterrupt:
    pass

encode_pipe.stdout.flush()
