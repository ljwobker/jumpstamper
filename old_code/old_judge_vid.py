#!/usr/bin/env python3

import os
import sys
import pathlib
import subprocess
import multiprocessing
import ffmpeg



def secsToTimecode(time, framerate):
    def tc_format(value):
        v = int(value)
        return f'{v:02}'
    
    frames = str(time).split('.')[1] 
    
    hours = tc_format(time // 3600)
    leftover = time % 3600

    mins = tc_format(leftover // 60)
    leftover = leftover % 60

    secs = tc_format(leftover // 1)

    rc = '\:'.join([hours, mins, secs, frames])

    return rc

def getFrameRate(infile):
    try:
        probe = ffmpeg.probe(infile) 
    except ffmpeg.Error as e:
        print(e.stderr, file=sys.stderr)
        sys.exit(1)

    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    if video_stream is None:
        print('No video stream found', file=sys.stderr)
        sys.exit(1)

    rate = video_stream['r_frame_rate'].split('/')
    # is it represented as a single integer value?
    if len(rate)==1:
        return float(rate[0])
    # or as a fraction (usually NTSC...)
    if len(rate)==2:
        return float(rate[0])/float(rate[1])
    return -1

def getTextBoxParams(infile):

    framerate = getFrameRate(infile)

    drawbox_params = {}
    drawbox_params['x'] = '0'
    drawbox_params['y'] = '0'
    drawbox_params['w'] = '0.28*iw'
    drawbox_params['h'] = '0.075*ih'
    drawbox_params['color'] = 'black@0.5'
    drawbox_params['t'] = 'fill'


    drawtext_params = {}   
    drawtext_params['fontfile'] = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
    drawtext_params['rate'] = str(framerate)
    drawtext_params['fontcolor'] = 'yellow'
    drawtext_params['fontsize'] = '96'
    drawtext_params['x'] = '0.9' 
    drawtext_params['y'] = '0.9'

    return (drawbox_params, drawtext_params)

def getNumFrames(infile):
    try:
        probe = ffmpeg.probe(infile) 
    except ffmpeg.Error as e:
        print(e.stderr, file=sys.stderr)
        sys.exit(1)

    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    if video_stream is None:
        print('No video stream found', file=sys.stderr)
        sys.exit(1)

    num_frames = int(video_stream['nb_frames'])

    return num_frames


def getFrameOffset(timestamp, framerate):
    # timestamp has to be 00:00:00:00  which is hh:mm:ss:ff
    [hh, mm, ss, ff] = timestamp.split(':')
    frames = framerate * (int(hh) * 3600 + int(mm) * 60 + int(ss))  + int(ff)
    return int(frames)

def secsFromTimestamp(timestamp, framerate):
    # timestamp has to be 00:00:00:00  which is hh:mm:ss:ff
    # returns a float representing the number of seconds for that {timestamp, framerate} 
    [hh, mm, ss, ff] = timestamp.split(':')
    seconds = (int(hh) * 3600 + int(mm) * 60 + int(ss)) + (int(ff) / framerate)
    return seconds



def makeTimeStamped(infile, outfile):
    framerate = getFrameRate(infile)

    # get the filter parameters for the drawbox/drawtext...
    drawbox_params, drawtext_params = getTextBoxParams(infile)
    drawtext_params['timecode'] = '00:00:00:00'      # making timestamp we start at zero

    print(f'Timestamping {infile} to {outfile}\n')
    rc = (
        ffmpeg
        .input(infile)
        .filter('drawbox', **drawbox_params)
        .filter('drawtext', **drawtext_params )
        .filter('scale', width='-4', height='480')
        .output(outfile, crf=26, preset='faster', t=25, an=None, y=None)
        .run()
    )
    return rc




def makeSlate(infile, slate_timestamp, slate_duration, outfile):
    framerate = getFrameRate(infile)
    slate_duration_frames = framerate * slate_duration
    frame_offset = getFrameOffset(slate_timestamp, framerate)
    secs_offset = secsFromTimestamp(slate_timestamp, framerate)
    fade_out_time = slate_duration - 1
    fade_dur = 0.75
    print(f'Generating slate file: input file: {infile}, output file {outfile}\n')
    rc = (    
        ffmpeg
        .input(infile, ss=str(secs_offset) )
        .filter('loop', loop=str(slate_duration_frames), size='1', start='1')
        .filter('scale', width='-4', height='480')
        .filter('fade', type='in', start_time=0, duration=fade_dur)
        .filter('fade', type='out', start_time=fade_out_time, duration=fade_dur)
        .setpts('PTS-STARTPTS')
        .output(outfile, crf=22, t=str(slate_duration), an=None, y=None, format='mp4')
        .run()
    )
    return rc

def makeScoreJump(infile, exit_timestamp, leadin, working_time, outfile):
    # outputs the jump itself from exit through working time, with the specified lead-in time.
    framerate = round(getFrameRate(infile))

    exit_offset = getFrameOffset(exit_timestamp, framerate)   # the FRAME number at exit
    leadin_offset = exit_offset - (leadin * framerate)  # FRAMES to leadin point (a few seconds before the exit)
    working_frames = (leadin + working_time) * framerate   # of FRAMES in the working time
    working_endframe = (leadin_offset + working_frames) + 1     # the FRAME where the jump working time ends
    freeze_frame = (working_endframe - leadin_offset)
    freeze_num_frames = 3 * framerate   # how many frames we hold the freeze

    # get the parameters for the text/timestamp box
    drawbox_params, drawtext_params = getTextBoxParams(infile)
    # right now leadin HAS to be an integer between 1 and 9... 
    drawtext_params['timecode'] = '00:00:-0'+ str(leadin) + ':00'

    rc = (
        ffmpeg
        .input(infile)
        .trim(start_frame=leadin_offset, end_frame=working_endframe)
        .filter('drawbox', **drawbox_params)
        .filter('drawtext', **drawtext_params )
        .filter('loop', loop=freeze_num_frames, size=1, start=freeze_frame)
        .filter('scale', width='-4', height='480')
        .setpts('PTS-STARTPTS')
        .output(outfile, crf=22, an=None, y=None, format='mp4')
        .run()
    )
    return rc






# def makeFreezeFrame(infile, freeze_duration, outfile):
#     framerate = getFrameRate(infile)

#     # get the number of frames, because we just need the last one...
#     num_frames = getNumFrames(infile)
#     trim_start = num_frames - 1
#     freeze_duration_frames = int(freeze_duration * framerate)

#     rc = (    
#         ffmpeg
#         .input(infile)
#         .trim(start_frame=num_frames-1, end_frame=num_frames)
#         .filter('loop', loop=str(freeze_duration_frames), size='1', start='1')
#         .filter('scale', width='-4', height='480')
#         .setpts('PTS-STARTPTS')
#         .output(outfile, crf=22, an=None, y=None, format='mp4')
#         .run()
#     )
#     return rc


def makeJumpByFrameNum(infile, outfile, slate_frm, leadin, exit_frm, wrk_time):

    framerate = round(getFrameRate(infile))
    drawbox_params, drawtext_params = getTextBoxParams(infile)
    # drawtext_params['rate'] = str(framerate)        # set for this particular file
    
    # have to manually build this to line up with the lead-in.  
    # right now, lead in MUST BE BETWEEN ONE AND NINE (sorry...)
    drawtext_params['timecode'] = '00:00:-0' + str(leadin) + ':00'      

    # compute all the frame offsets for the points of interest in the streams
    slate_len = 5 * framerate       
    freeze_len = 5 * framerate      
    work_len = (leadin + wrk_time) * framerate  
    leadin_frm = exit_frm - (leadin * framerate)  
    freeze_frm = (leadin + wrk_time) * framerate + leadin_frm  
    



    slate = (
        ffmpeg
        .input(infile)
        .trim(start_frame=slate_frm, end_frame=(slate_frm+1))    # spits out a single-frame stream
        .filter('loop', loop=slate_len, size=1, start=1)  # the first frame of the TRIMMED stream
        # .filter('scale', width='-4', height='480')
        .setpts('PTS-STARTPTS') 
    )
    
    jump = (
        ffmpeg
        .input(infile)
        .trim(start_frame=leadin_frm, end_frame=freeze_frm)     # trim from lead-in to the end of working time
        .filter('drawbox', **drawbox_params)                    # the box we draw the time over
        .filter('drawtext', **drawtext_params)                  # the time itself
        # .filter('scale', width='-4', height='480')
        .setpts('PTS-STARTPTS')
    )

    freeze = (
        ffmpeg
        .input(infile)
        .trim(start_frame=freeze_frm, end_frame=(freeze_frm+1))
        .filter('loop', loop=freeze_len, size=1, start=1)  # the first frame of the TRIMMED stream
        # .filter('scale', width='-4', height='480')
        .setpts('PTS-STARTPTS')     
    )

    joined = (
        ffmpeg
        .concat(slate, jump, freeze, v=1, a=0).node
    )
  
    out = (
        ffmpeg
        .output(joined[0], outfile, crf=22, an=None, y=None, format='mp4')
        .run()
    )








def concatSegments(slatefile, working_jumpfile, outfile):
    slate_file = ffmpeg.input(slatefile)
    jump_file = ffmpeg.input(working_jumpfile)
    (
        ffmpeg
        .concat(slate_file, jump_file)
        .output(outfile, crf=22, y=None, format='mp4')
        .run()
    )    



def makeJudgeableJump(infile, slate_time, exit_time, leadin, slate_dur):

    input_file = infile
    slate_file = 'slate_' + input_file 
    working_file = 'working_' + input_file 
    final_file = 'final_' + input_file + '.mp4'

    rc = makeSlate(infile=input_file, slate_timestamp=slate_time, slate_duration=5, outfile=slate_file)
    print(rc)
    rc = makeScoreJump(infile=input_file, exit_timestamp=exit_time, leadin=5, working_time=45, outfile=working_file)
    print(rc)
    rc = concatSegments(slate_file, working_file, final_file)
 
    return



def __main__():

    # input_file = 'AVCHD_1080P60fps.MTS'
    # slate_timestamp='00:00:02:21'
    # exit_timestamp='00:00:24:32'
    # makeJudgeableJump(input_file, slate_timestamp, exit_timestamp, leadin=5, slate_dur=5)


    input_file = sys.argv[1]
    slate_frm= int(sys.argv[2])     # cast, args are passed as strings!
    exit_frm= int(sys.argv[3])
    makeJumpByFrameNum(infile='AVCHD_1080P60fps.MTS', outfile='outfooz.mp4', slate_frm=slate_frm, leadin=3, exit_frm=exit_frm, wrk_time=45)


__main__()
exit(0)

