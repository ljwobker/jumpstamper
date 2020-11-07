#!/usr/bin/env python3

import ffmpeg
import pprint
import sys



infile = sys.argv[1]
outfile = 'deint_' + infile + '.mp4'

rc = (
    ffmpeg.input(infile)
    .filter('yadif')
    .output(outfile, crf=20, an=None, y=None, format='mp4')
    .run()

)