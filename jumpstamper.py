#!/usr/bin/env python3

import os
import sys
import subprocess
import ffmpeg
import openpyxl
import argparse
import copy
from dataclasses import dataclass
import pprint
import math



def jumpParser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i",   "--input_file", action="store", type=str, help="input video file")
    parser.add_argument("-o",   "--output_file", action="store", type=str,  help="output video file")
    parser.add_argument("-s",   "--stamp", action="store_true",  help="enable frame stamping")
    parser.add_argument("-st",  "--slate_time", action="store", type=float,   help="duration of the slate frame")
    parser.add_argument("-lt",  "--leadin_time", action="store", type=float,   help="start jump portion of video N seconds before exit")
    parser.add_argument("-wt",  "--working_time", action="store", type=float,   help="seconds of working (scoring) time")
    parser.add_argument("-jt",  "--jump_time", action="store", type=float,   help="length of the jump video")
    parser.add_argument("-ef",  "--exit_frame", action="store", type=int, help="frame number of the exit")
    parser.add_argument("-sf",  "--slate_frame", action="store", type=int,   help="frame number of the slate, 0 to disable")
    parser.add_argument("-ft",  "--freeze_time", action="store", type=float,   help="duration of the freeze, 0 to disable")
    parser.add_argument("-ovr", "--overlay_prof", action="store", type=str,   help="the overlay profile name")
    parser.add_argument("-enc", "--encoder_prof", action="store", type=str,   help="the encoder options profile name")
    parser.add_argument("-an",  "--annotation", action="store", type=str,   help="annotation string")
    parser.add_argument("-xlsx", "--excel_sheet", action="store", type=str, help="parse excel: header row required with arguments, each row is one jump")

    return parser



def getVideoMetadata(infile):
    ''' returns a dict of metadata via ffprobe for the first VIDEO stream in input file. '''

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
    ''' returns a float with the probed frame rate from the video file. '''
    rate = vid_metadata['r_frame_rate'].split('/')
    # is it represented as a single integer value?
    if len(rate)==1:
        return float(rate[0])
    # or as a fraction (usually NTSC...)
    if len(rate)==2:
        return float(rate[0])/float(rate[1])
    return -1





def overlayProf(profile_id, vid_metadata):
    '''
    returns a set of parameters for the drawtext filter based on the profile ID provided.
    A set of common parameters are copied to each specific text box, and then we need
    to modify whatever is unique to that text box.
    '''

    def roundToMultOf(x, base=10):
        return base * round(x/base)

    framerate = getFrameRate(vid_metadata)
    vid_h = vid_metadata['height']
    vid_w = vid_metadata['width']

    # our parameter profiles are a dictionary of dicts
    profile = { 
        'common': {},
        'framectr': {}, 
        'timestamp': {}, 
        'annot': {}, 
        }

    profile['common'] = {}    # https://ffmpeg.org/ffmpeg-filters.html#drawtext-1 
    profile['common']['fontfile'] = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
    profile['common']['rate'] = framerate
    profile['common']['fontcolor'] = 'yellow'
    profile['common']['fontsize'] = roundToMultOf(vid_h/10 , 8)
    profile['common']['box'] = 1
    profile['common']['boxcolor'] = 'black@0.5'
    profile['common']['boxborderw'] = 3
    profile['common']['y'] = 0       # x and y are offsets from the top left of frame
    profile['common']['x'] = 0

    # adjust parameters for the frame counter 
    profile['framectr'] = {
        **profile['common'], 
        'y' : (vid_h * 0.9), 
        'x' : (vid_w * 0.2),
        'text' : 'in: %{frame_num} @ %{pts}',
        'start_number' : 0,
        }

    # adjust location of the timestamp
    profile['timestamp'] = {
        **profile['common'],
        'y' : 0,
        'x' : 0,
        }

    profile['annot'] = copy.deepcopy(profile['common'])
    profile['annot']['fontsize'] = roundToMultOf(vid_h/16 , 8)
    annot_y = vid_h - profile['annot']['fontsize'] - (profile['annot']['boxborderw'] * 2)
    profile['annot']['y'] = annot_y
    profile['annot']['x'] = 0

    return profile



def encoderProf(profile_id, vid_metadata):
    ''' return the encoder profile.  Each profile has parameters for
    - the output encode options: codec, codec options, quality, etc.
    - the FFMPEG general options such as "no audio" and "hide_banner"

    Suggestion: when creating a new profile, just make a deepcopy() of the default 
    one, and change/overwrite the options that you need to.  
    '''

    framerate = getFrameRate(vid_metadata)
    vid_h = vid_metadata['height']
    vid_w = vid_metadata['width']

    profile = {}
    profile['output'] = {
        'c:v': 'libx264',
        # 'pix_fmt' : 'yuvj420p',
        'crf': 25,
        'preset': 'slow',
        'an': None,
        'y': None,
        'hide_banner': None,
        'format': 'mp4'
    }

    profile['scale'] = {'width': vid_w, 'height': vid_h}
    profile['fps'] = {'fps': framerate}


    # outputs in 1080 @ 30fps
    if (profile_id == '1080_30'):
        profile['scale'] = {'width': '-4', 'height': '1080'}
        profile['fps'] = {'fps': 30}

    # quick - useful for iterative testing!
    if (profile_id == 'quick'):
        profile['scale'] = {'width': '-4', 'height': '480'}
        # profile['fps'] = {'fps': 25}
        profile['output']['crf']  = 32
        profile['output']['preset']  = 'veryfast'

    return profile



@dataclass 
class StamperArgs:
    '''
    Collects arguments from CLI, does some sanity checking.  Class instance should be a set of 
    values that are sane for passing into FFMPEG filters -- this includes things like durations can't 
    be negative, frame numbers can't be negative, you can't back a leadin to before the first frame, etc.
    '''

    input_file : str = ''
    output_file : str = ''
    stamp : bool = False
    slate_time : float = 0.0
    freeze_time : float = 0.0
    leadin_time : float = 0.0
    working_time : float = 0.0
    jump_time : float = 60.0    
    slate_frame : int = 0
    exit_frame : int = 0
    overlay_prof : str = 'default'
    encoder_prof : str = 'default'
    annotation : str = ''
    excel_sheet : str = None

    def numFrames(self, seconds): 
        return round(seconds * self.framerate)

    def numSecs(self, frames): 
        return (frames / self.framerate)


    def __post_init__(self): 
        '''a jump has five meaningful frame indices to keep:
            - slate, lead-in, exit, freeze, end
           and some useful durations, which we compute in both frames and time:
            - total jump,slate, lead-in, freeze
        ''' 
        self.vid_metadata = getVideoMetadata(self.input_file)
        self.framerate = getFrameRate(self.vid_metadata)
        # dict of durations in seconds (mostly from CLI)
        self.secs = {
            'slate' : self.slate_time,
            'leadin' : self.leadin_time,
            'working' : self.working_time,
            'freeze' : self.freeze_time,
            'jump' : self.jump_time,
            'total' : self.jump_time + self.freeze_time + self.leadin_time + self.slate_time
        }

        # the frame numbers for points of interest
        self.framenum = {
            'slate' : self.slate_frame,
            'leadin' : self.exit_frame - self.numFrames(self.leadin_time),
            'exit' : self.exit_frame,
            'freeze' : self.exit_frame + self.numFrames(self.working_time),
            'end' : self.exit_frame + self.numFrames(self.jump_time),
        }
        # compute the duration in FRAMES from the values we have in SECONDS
        self.frames = { k:self.numFrames(v) for k,v in self.secs.items() }
        self.sanity()


    def sanity(self):
        ''' run some sanity checks on the computed values '''

        # if the reqested leadin would be before the beginning of the jump,
        # reset the leadin frame to the start and adjust the duration
        if (self.framenum['leadin'] < 0):
            self.framenum['leadin'] = 0
            # the leadin duration is now the exit frame number comverted back to seconds
            self.secs['leadin'] = self.numSecs(self.framenum['exit'])





def makeStamped(args):
    
    overlay_profile = overlayProf(args.overlay_prof, args.vid_metadata)
    framecounter_args = overlay_profile['framectr']

    output = (
        ffmpeg
        .input(args.input_file)
        .filter('drawtext', **framecounter_args)
    )

    return output



def makeSlate(args):
    
    slate_trim_args = {
        'start_frame' : args.framenum['slate'],
        'end_frame' : args.framenum['slate'] + 1,
    }

    slate = (
        ffmpeg
        .input(args.input_file)
        .trim(**slate_trim_args)    # spits out a single-frame stream
        .filter('loop', loop=args.frames['slate'], size=1, start=1)  # the first frame of the TRIMMED stream
        .setpts('N/FRAME_RATE/TB')      # fixup PTS for the looped frames
    )

    if args.secs['slate'] >= 2:
        fade_dur = 0.5
        fade_in_time = 0
        fade_out_time = args.secs['slate'] - fade_dur
        slate = (
            slate
            .filter('fade', type='in', start_time=fade_in_time, duration=fade_dur)
            .filter('fade', type='out', start_time=fade_out_time, duration=fade_dur)
        )

    return slate



def makeJump(args):

    overlay_profile = overlayProf(args.overlay_prof, args.vid_metadata)
    timestamp_args = overlay_profile['timestamp']
    annot_args = overlay_profile['annot']
    annot_args['text'] = args.annotation

    trim_args = {
        'start_frame': args.framenum['leadin'],   
        'end_frame': args.framenum['end'],
    }

    # shift the freeze frame, because we trimmed the original stream and all the frame numbers change
    args.framenum['freeze'] = args.framenum['freeze'] - args.framenum['leadin'] + 1
    freeze_loop_args = {
        'loop': args.frames['freeze'],
        'size': 1,
        'start': args.framenum['freeze'],
    }

    fade_duration = 2
    jump_fade_args = {
        'type' : 'out',
        'start_time' : args.secs['slate'] + args.secs['jump'] + args.secs['freeze'] - fade_duration,
        'duration' : fade_duration,
    }

    base_EIF_calc = '%{eif:(trunc(t-LEADIN)):d:2}.%{eif:abs((1M*(t-LEADIN)-1M*trunc(t-LEADIN))/10000):d:2}'
    timestamp_args['text'] = base_EIF_calc.replace('LEADIN', str(args.leadin_time))
    jump = (
        ffmpeg
        .input(args.input_file)
        .trim(**trim_args)
        .setpts('N/FRAME_RATE/TB')      # fixup PTS for the looped frames
        .filter('drawtext', **timestamp_args)
        .filter('drawtext', **annot_args)
        .filter('loop', **freeze_loop_args)  
        .setpts('N/FRAME_RATE/TB')      # fixup PTS for the looped frames
        .filter('fade', **jump_fade_args)
    )
    return jump


def joinAndPostFilters(args, to_concat):
    enc_opts = encoderProf(args.encoder_prof, args.vid_metadata)
    scale_args = enc_opts['scale']
    fps_filter_args = enc_opts['fps']
    joined = (
        ffmpeg
        .concat(*to_concat, v=1, a=0)
        .filter('scale', **scale_args)
        # .filter('fps', **fps_filter_args)
        .node       # I still don't know what this does.. 
    )
    return joined




def processJump(list_of_args):

    for args in list_of_args:
        enc_opts = encoderProf(args.encoder_prof, args.vid_metadata)
        output_args = enc_opts['output']

        if args.stamp:      # the stamp flag is set, so do that...
            framestamped = makeStamped(args)
            to_output = joinAndPostFilters(args, [framestamped])

        elif args.slate_time == 0:      # there's no slate info from the CLI
            jump = makeJump(args)
            to_output = joinAndPostFilters(args, [jump])

        else:           # we have a slate to add up front...
            slate = makeSlate(args)
            jump = makeJump(args)
            to_output = joinAndPostFilters(args, [slate, jump])

        output = ffmpeg.output(to_output[0], args.output_file, **output_args)
        output.run()
        print (f"FFMPEG command string was: \n {' '.join(output.compile())}")



def jumpsFromXlsx(xls_file):
    ''' returns a list of dicts, where each dict is a set of arguments for a single jump '''
    try:
        wb = openpyxl.load_workbook(xls_file)
    except:
        print(f"failed to open file {xls_file}")
    ws = wb.active
    # assert that worksheet has at least two rows
    # assert that input_file and output_file are both in row 1


    listOfJumpArgs = []
    for jumprow in ws.iter_rows(min_row=2):
        jump_args = {}
        for cell in jumprow:
            # param_key is the value from row 1 for that column
            param_key = ws.cell(row=1, column=cell.column).value
            param_value = cell.value
            jump_args[param_key] = param_value
        if all (jump_args[k] is not None for k in ['input_file', 'output_file']):   # have to have in/out files, skip "empty" rows...
            listOfJumpArgs.append(jump_args)

    return listOfJumpArgs


def getCmdLineList(parser):
    '''
    if it's an excel sheet, return each set of arguments as an element in the list
    if it's a single jump, return a list with one element containing the passed args
    '''
    cleaned_jumps = []
    inputArgDict = vars(parser.parse_args())  
    if inputArgDict['excel_sheet'] is not None:
        jumpsToProcess = jumpsFromXlsx(inputArgDict['excel_sheet'])
    else:
        jumpsToProcess = [inputArgDict]         # make the jump into a single item list
    

    for rawjump in jumpsToProcess:
        # jump = StamperArgs(**rawjump)
        cleanedArgs = { k:v for (k,v) in rawjump.items() if v is not None }
        jump = StamperArgs(**cleanedArgs)
        cleaned_jumps.append(jump)
    # pprint.pprint(cleanedArgs)
    return cleaned_jumps


def __main__():

    parser = jumpParser()
    # cli_args = StamperArgs(**getCmdLineArgs(parser))
    cli_arg_list = getCmdLineList(parser)
    processJump(cli_arg_list)  

    return 0


__main__()
exit(0)

