#!/usr/bin/env python3

import os
import sys
import pathlib
import subprocess
import multiprocessing
import ffmpeg
import openpyxl




def getVideoMetadata(infile):
    
    try:
        probe = ffmpeg.probe(infile) 
    except ffmpeg.Error as e:
        print(e.stderr, file=sys.stderr)
        sys.exit(1)

    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    if video_stream is None:
        print('No video stream found', file=sys.stderr)
        sys.exit(1)

    return video_stream


def getFrameRate(vid_metadata):

    rate = vid_metadata['r_frame_rate'].split('/')
    # is it represented as a single integer value?
    if len(rate)==1:
        return float(rate[0])
    # or as a fraction (usually NTSC...)
    if len(rate)==2:
        return float(rate[0])/float(rate[1])
    return -1



def getTextBoxParams(vid_metadata):

    framerate = round(getFrameRate(vid_metadata))
    vid_height = vid_metadata['height']

    drawtext_params = {}    # https://ffmpeg.org/ffmpeg-filters.html#drawtext-1 
    drawtext_params['fontfile'] = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
    drawtext_params['rate'] = framerate
    drawtext_params['fontcolor'] = 'yellow'
    drawtext_params['fontsize'] = round((vid_height / 96)) * 8
    drawtext_params['x'] = (-2.4 * drawtext_params['fontsize'])         # inset box to hide hours
    drawtext_params['y'] = '0'
    drawtext_params['box'] = 1
    drawtext_params['boxcolor'] = 'black@0.5'
    drawtext_params['boxborderw'] = '3'

    return (drawtext_params)


def makeJumpByFrameNum(infile, outfile, slate_frm, leadin, exit_frm, wrk_time):
    '''
    infile/outfile : filenames
    slate_frm, exit_frm: the frame number (i.e. frame index into the stream) where the slate or exit happens
    wrk_time: the working time of the jump (in seconds), from exit until the freeze frame
    leadin: duration (in seconds) for the leadin and how long the slate and final frame are paused
    '''


    vid_metadata = getVideoMetadata(infile)
    framerate = (getFrameRate(vid_metadata))
    drawtext_params = getTextBoxParams(vid_metadata)
    
    # have to manually build this to line up with the lead-in.  
    # right now, lead in MUST BE BETWEEN ONE AND NINE (sorry...)
    drawtext_params['timecode'] = '00:00:-0' + str(leadin) + ':00'      

    if (slate_frm == 0):
        slate_numframes = 1     # if user gives zero slate, we just do a single frame at the beginning
    else:
        slate_numframes = leadin * framerate               # length in frames of the slate

    # compute all the frame offsets for the points of interest in the streams
    freeze_numframes = leadin * framerate              # length in frames of the freeze
    work_numframes = (leadin + wrk_time) * framerate  # length in frames of the whole working jump
    leadin_frm = exit_frm - (leadin * framerate)  # frame number for where the lead-in starts
    freeze_frm = leadin_frm + work_numframes + 1      # frame number where we freeze 


    # the arguments to the scale filter (we reuse the same ones in all streams)
    scale_args = {'width': '-4', 'height': '1080'}
    fps_args = {'fps': 30}
    crop_args = {'x': '0.1*in_w', 'y': '0', 'width': '0.8*in_w', 'height': '0.9*in_h'}


    slate = (
        ffmpeg
        .input(infile)
        .trim(start_frame=slate_frm, end_frame=(slate_frm+1))    # spits out a single-frame stream
        .filter('loop', loop=slate_numframes, size=1, start=1)  # the first frame of the TRIMMED stream
        .setpts('N/FRAME_RATE/TB')      # fixup PTS for the looped frames
    )
    
    jump = (
        ffmpeg
        .input(infile)
        .trim(start_frame=leadin_frm, end_frame=freeze_frm) # trim from lead-in to the end of working time
        .setpts('N/FRAME_RATE/TB')      # fixup PTS for the looped frames
        .filter('drawtext', **drawtext_params)                  # the time 
        .filter('loop', loop=freeze_numframes, size=1, start=work_numframes)
        .setpts('N/FRAME_RATE/TB')      # fixup PTS for the looped frames
    )

    joined = (
        ffmpeg
        .concat(slate, jump, v=1, a=0)
        .filter('scale', **scale_args)
        .filter('fps', **fps_args)
        .node       ### ARGH what does this DO???  ####
    )
  
    # set some common output arguments
    output_args = {'crf': 25, 'an': None, 'y': None, 'hide_banner': None, 'format': 'mp4'}

    # run, then print the compiled FFMPEG output string for easier debug...
    output = ffmpeg.output(joined[0], outfile, **output_args)
    output.run()
    print ("FFMPEG command line output:\n" + " ".join(output.compile()))



def __main__():


    assert len(sys.argv) == 4, "Must have exactly 3 arguments:\nUsage:  ./script.py [original input file] [slate frame #] [exit frame #]"

    input_file = sys.argv[1]
    slate_frm= int(sys.argv[2])     # cast, args are passed as strings!
    exit_frm= int(sys.argv[3])
    output_file = 'final_' + input_file
    makeJumpByFrameNum(infile=input_file, outfile=output_file, slate_frm=slate_frm, leadin=2, exit_frm=exit_frm, wrk_time=43)
    return 0

__main__()
exit(0)

