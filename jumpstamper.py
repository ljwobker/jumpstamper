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



def getVideoMetadata(infile: str) -> dict:
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


def getFrameRate(vid_metadata: dict) -> float:
    ''' returns a float with the probed frame rate from the video file. '''
    rate = vid_metadata['r_frame_rate'].split('/')
    # is it represented as a single integer value?
    if len(rate)==1:
        return float(rate[0])
    # or as a fraction (usually NTSC...)
    if len(rate)==2:
        return float(rate[0])/float(rate[1])
    return -1





def overlayProf(profile_id: str, vid_metadata: dict) -> dict:
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

    common = {}    # https://ffmpeg.org/ffmpeg-filters.html#drawtext-1 
    common['fontfile'] = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
    common['rate'] = framerate
    common['fontcolor'] = 'yellow'
    common['fontsize'] = roundToMultOf(vid_h/12 , 8)
    common['box'] = 1
    common['boxcolor'] = 'black@0.5'
    common['boxborderw'] = 3

    # adjust parameters for the frame counter 
    framectr = {
        **common, 
        'y' : (vid_h * 0.9), 
        'x' : (vid_w * 0.2),
        'text' : 'in: %{frame_num} @ %{pts}',
        'start_number' : 0,
        }

    # set the location of the timestamp
    timestamp = {
        **common, 
        'y' : 0,
        'x' : 0,
        }

    annot_fontsize = roundToMultOf(vid_h/16 , 8)
    annot = {
        **common,
        'fontsize': annot_fontsize,       # 1/16th of height rounded
        'y': vid_h - annot_fontsize,      # offset by the height from the bottom
        'x': 0,
        }   

    profile = { 
        'framectr': framectr, 
        'timestamp': timestamp, 
        'annot': annot, 
        }
    return profile



def encoderProf(profile_id: str, vid_metadata: dict) -> dict:
    ''' return the encoder profile.  Each profile has parameters for
    - the output encode options: codec, codec options, quality, etc.
    - the FFMPEG general options such as "no audio" and "hide_banner"

    Suggestion: when creating a new profile, just make a deepcopy() of the default 
    one, and change/overwrite the options that you need to.  
    '''

    framerate = getFrameRate(vid_metadata)
    vid_h = vid_metadata['height']
    vid_w = vid_metadata['width']

    output = {
        'c:v': 'libx264',
        # 'pix_fmt' : 'yuvj420p',
        'crf': 27,
        'preset': 'slow',
        'an': None,
        'y': None,
        'hide_banner': None,
        'format': 'mp4',
        'benchmark': None,
    }

    scale = {'width': vid_w, 'height': vid_h}
    fps = {'fps': framerate}


    # outputs in 1080 @ 30fps
    if (profile_id == '1080_30'):
        scale = {'width': '-4', 'height': '1080'}
        fps = {'fps': 30}

    # quick - useful for iterative testing!
    if (profile_id == 'quick'):
        scale = {'width': '-4', 'height': '480'}
        # fps = {'fps': 25}
        output['crf']  = 30
        output['preset']  = 'veryfast'

    if (profile_id == 'x265_high'):
        output['c:v'] = 'libx265'
        output['preset'] = 'medium'
        output['crf'] = '28'

    # the null profile does NOT inherit anything so we have to replicate here...
    # for debug/test only  ;-)
    if (profile_id == 'null'):
        output = {
            'format': 'null',
            'y': None,
            'hide_banner': None,
            'benchmark': None,
        }


    return_id = {
        'output' : output,
        'scale' : scale,
        'fps': fps,
    }

    return return_id



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

    def numFrames(self, seconds: float) -> int: 
        return round(seconds * self.framerate)

    def numSecs(self, frames: int) -> float: 
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





def makeStamped(args: StamperArgs):
    
    overlay_profile = overlayProf(args.overlay_prof, args.vid_metadata)
    framecounter_args = overlay_profile['framectr']

    output = (
        ffmpeg
        .input(args.input_file)
        .filter('drawtext', **framecounter_args)
    )

    return output



def makeSlate(args: StamperArgs):
    
    slate_trim_args = {
        'start_frame' : args.framenum['slate'],
        'end_frame' : args.framenum['slate'] + 1,
    }

    slate = (
        ffmpeg
        .input(args.input_file)
        .crop(width='0.8*in_w', height='ih', x='0.1*in_w', y=0)
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



def makeJump(args: StamperArgs) -> ffmpeg.nodes.FilterableStream:

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
        'start_time' : args.secs['leadin'] + args.secs['jump'] + args.secs['freeze'] - fade_duration,
        'duration' : fade_duration,
    }


    if (args.working_time == 0):          # set text to empty string, which causes drawtext to do nothing
        timestamp_args['text'] = ''         
    else:
        # this is an expression that drawtext can evaluate to get the timestamp in the format 
        # that we want.  See 'eif' 'trunc' 'abs' functions and 't' variable in docs.
        base_EIF_calc = '%{eif:(trunc(t-LEADIN)):d:2}.%{eif:abs((1M*(t-LEADIN)-1M*trunc(t-LEADIN))/10000):d:2}'
        timestamp_args['text'] = base_EIF_calc.replace('LEADIN', str(args.leadin_time))

    jump = (
        ffmpeg
        .input(args.input_file)
        .trim(**trim_args)
        .setpts('N/FRAME_RATE/TB')      # fixup PTS for the trimmed stream
        .crop(width='0.8*in_w', height='ih', x='0.1*in_w', y=0)
        .filter('drawtext', **timestamp_args)
        .filter('drawtext', **annot_args)
        .filter('loop', **freeze_loop_args)  
        .setpts('N/FRAME_RATE/TB')      # fixup PTS for the looped frames
        .filter('fade', **jump_fade_args)
    )
    return jump


def joinAndPostFilters(args: StamperArgs, to_concat: list) -> ffmpeg.nodes.FilterableStream:
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




def processJumps(list_of_args: list):

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

        if args.encoder_prof == 'null':
            args.output_file = '/dev/null'
        output = ffmpeg.output(to_output[0], args.output_file, **output_args)

        output.run()
        print (f"FFMPEG command string was: \n {' '.join(output.compile())}")


def jumpsFromXlsx(xls_file: str) -> list:
    ''' returns a list of dicts, where each dict is a set of CLI-equivalent arguments for a jump '''
    try:
        wb = openpyxl.load_workbook(xls_file)
    except Exception:
        print(f"failed to open file {xls_file}")
    ws = wb.active
    # TODO: assert that worksheet has at least two rows
    # TODO:assert that input_file and output_file are both in row 1


    jumpArgs = []
    for jumprow in ws.iter_rows(min_row=2):
        jump_args = {}
        for cell in jumprow:
            # param_key is the value from row 1 for that column
            param_key = ws.cell(row=1, column=cell.column).value
            param_value = cell.value
            # TODO: need to ignore header values that aren't known ArgParse arguments
            jump_args[param_key] = param_value
        if all (jump_args[k] is not None for k in ['input_file', 'output_file']):   # have to have in/out files, skip "empty" rows...
            jumpArgs.append(jump_args)

    return jumpArgs


def getCmdLineList(parser: argparse.ArgumentParser) -> list:
    '''
    if it's an excel sheet, return each set of arguments as an element in the list
    if it's a single jump from a set of CLI args, return a single element list containing the passed args
    '''
    cleaned_jumps = []
    cli_args = vars(parser.parse_args())  
    if cli_args['excel_sheet'] is not None:
        jumpsToProcess = jumpsFromXlsx(cli_args['excel_sheet'])
    else:
        jumpsToProcess = [cli_args]         # make the jump into a single item list
    

    for rawjump in jumpsToProcess:
        cleanedArgs = { k:v for (k,v) in rawjump.items() if v is not None }
        jump = StamperArgs(**cleanedArgs)
        cleaned_jumps.append(jump)
    return cleaned_jumps


def __main__():

    parser = jumpParser()
    cli_arg_list = getCmdLineList(parser)
    processJumps(cli_arg_list)  

    return 0


__main__()

