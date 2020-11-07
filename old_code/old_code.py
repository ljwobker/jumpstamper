




def makeJumpByFrameNum(infile, outfile, sane_args):
    '''
    infile/outfile : filenames
    sane_args: a set of sanity checked args and computed times used to build filters
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
        .trim(start_frame=leadin_frm, duration=XXX) # trim from lead-in to the end of working time
        .setpts('N/FRAME_RATE/TB')      # fixup PTS for the looped frames
        # .filter('drawtext', **drawtext_params)                  # the time 
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


def makeStampedVid(infile, outfile, mode='frame', duration=30):
    ''' generates a stamped video from the input file.  If mode is "frame" we stamp
    the video with incrementing frame numbers.  If the mode is "time" we stamp with an
    incrementing timecode.  
    '''
    vid_metadata = getVideoMetadata(infile)
    framerate = round(getFrameRate(vid_metadata))
    drawtext_params = getTextBoxParams(vid_metadata)


    # get shared drawtext params, then set unique for frame- vs. time-stamping
    drawtext_params = getTextBoxParams(vid_metadata)
    if (mode == 'frame'):
        # the frame-stamp specific arguments for drawtext
        drawtext_params['text'] = '%{frame_num}'
        drawtext_params['start_number'] = 0
    elif (mode == 'time'):
        # the timecode-stamp specific arguments for drawtext
        drawtext_params['timecode'] = '00:00:00:00'      # making timestamp we start at zero

    # run that shit...
    scale_args = {'width': -4, 'height': 320}
    output_args = {'t': duration, 'crf': 24, 'preset': 'faster', 'an': None, 'y': None, 'hide_banner': None, 'format': 'mp4'}
    fps_filter_args = {'fps': 30}

    rc = (
        ffmpeg
        .input(infile)
        .filter('drawtext', **drawtext_params )
        .filter('scale', **scale_args)
        .filter('fps', **fps_filter_args)
        .output(args.output_file, **output_args)
        .run()
    )
    return rc

