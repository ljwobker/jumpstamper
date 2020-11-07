#!/usr/bin/env python3

import ffmpeg
import pprint
import sys

def pprobe(infile):
    try:
        probe = ffmpeg.probe(infile) 
    except ffmpeg.Error as e:
        print(e.stderr, file=sys.stderr)
        sys.exit(1)

    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    if video_stream is None:
        print('No video stream found', file=sys.stderr)
        sys.exit(1)
    
    pprint.pprint(video_stream)



outfile = 'ljhack.mp4'
infile = sys.argv[1]
pprobe(infile)
rc = (
    ffmpeg.input(infile)
    .trim(start_frame=1, end_frame=127)
    .filter('loop', loop=100, size=1, start=126)
    .setpts('PTS-STARTPTS')          # reset timestamp
    .output(outfile, crf=22, an=None, y=None, format='mp4')
    # .run()

)