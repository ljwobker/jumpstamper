#!/usr/bin/env python3

import ffmpeg
import subprocess

def getDrawArgs():
    # these are the common/shared drawtext args
    draw_args = {}    # https://ffmpeg.org/ffmpeg-filters.html#drawtext-1 
    draw_args['fontfile'] = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
    draw_args['rate'] = 25
    draw_args['fontcolor'] = 'yellow'
    draw_args['fontsize'] = 60
    draw_args['x'] = '0' 
    draw_args['y'] = '50'
    draw_args['box'] = 1
    draw_args['boxcolor'] = 'black@0.75'
    draw_args['boxborderw'] = '3'
    return draw_args

def stampWithInputFrame(infile='testsrc.mpg', outfile='in_stamped.mp4'):
    output_args = {'crf': 22, 'an': None, 'y': None, 'hide_banner': None, 'format': 'mp4', 'loglevel': 'info'}
    stamp_args = getDrawArgs()
    # stamp_args['text'] = 'timestamp %{pts:gmtime:0:%05S.%t}'
    # stamp_args['text'] = 'timestamp %{pts:flt}'
    stamp_args['text'] = 'in_f %{frame_num} @ %{pts}'
    stamp_args['start_number'] = 0

    stamp2_args = getDrawArgs()
    stamp2_args['text'] = 'pts %{pts:flt}'
    stamp2_args['y'] = '200'

    stamp2_args['start_number'] = 0


    stampit = (
        ffmpeg
        .input(infile)
        .filter('drawtext', **stamp_args)
        # .filter('drawtext', **stamp2_args)
        .output(outfile, **output_args)
    )
    stampit.run()
    print('FFMPEG compiled command line :\n' + ' '.join(stampit.compile()))


def filtertest():
    output_args = {'crf': 25, 'an': None, 'y': None, 'hide_banner': None, 'format': 'mp4', 'loglevel': 'warning'}
    outstamp_args = getDrawArgs()
    outstamp_args['text'] = 'outf %{frame_num} pts %{pts}'
    outstamp_args['start_number'] = 0
    outstamp_args['y'] = '300'

    trimtest = (
        ffmpeg
        .input('in_stamped.mp4')
        .filter('loop', loop=10, size=25, start=50)
        .setpts('N/FRAME_RATE/TB')
        # .filter('loop', loop=75, size=1, start=175)
        # .setpts('N/FRAME_RATE/TB')
        # .trim(start_frame=125, end_frame=275)
        # .trim(start_frame=100, duration=1)
        # .setpts('N/FRAME_RATE/TB')      # fixup PTS for the looped frames
        .filter('drawtext', **outstamp_args)   
        .output('trimtest.mp4', **output_args)
    )

    trimtest.run()
    print('FFMPEG compiled command line :\n' + ' '.join(trimtest.compile()))
    print('To execute manually in shell you have to wrap the filter_complex in double quotes')

# create a source test file with "ffmpeg -f lavfi -i testsrc=duration=10:size=1280x720:rate=25 testsrc.mpg"
subprocess.run('ffmpeg -hide_banner -y -f lavfi -i testsrc=duration=80:size=640x320:rate=25 testsrc.mpg', shell=True)
stampWithInputFrame()
# filtertest()

