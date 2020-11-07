# Jumpstamper

### NAME ###

**jumpstamper** - a program to overlay ("stamp") various things on top of skydiving videos

### DESCRIPTION ### 
"Jumpstamper" is heavily based on ffmpeg and ffmpeg-python, and was originally designed
to add things like timestamps and frame numbers and text output over competitive
skydiving video streams.  It could possibly be reconfigured for a number of other things
but most of the functionality (and certainly much of the context) comes from the skydiving
universe.

### DEPENDENCIES ###
Jumpstamper relies heavily on [ffmpeg](https://github.com/kkroening/ffmpeg-python/) and its associated [filters](https://ffmpeg.org/ffmpeg-filters.html), and is built around the [ffmpeg-python](https://github.com/kkroening/ffmpeg-python/blob/master/README.md) library.  

### THEORY ###
the script tries to at least *loosely* follow the ffmpeg config model, where you have an input file, a set of operations/transformations on that file, and an output file.  A set of command line options and/or profiles are used to control the behavior.  


### OPTIONS ###

`-i, --input_file` : the input file.

`-o, --output_file` : the output file.  Note that unlike ffmpeg, jumpstamper has an explicit option to define the output file.  

`-s, --stamp` : (*optional*) take the input file and "stamp" it with frame numbers.  These can then be used to determine the frame numbers for parameters such as the exit frame or slate frame.

`-ef, --exit_frame` : (*optional*) the frame number of the exit from the original input video, (i.e. when the timer for a scoring jump begins)

`-sf, --slate_frame` : (*optional*, default=0) the frame number (from the original input video) of a readable slate for competition/scoring jumps -- or just a fun camera geek or still if you're into that sort of thing...

`-st, --slate_time` : (*optional*, default=3 if slate_frame is used, 0 otherwise) duration of the slate frame.

`-ft, --freeze_time` : (*optional*, default=0) duration of the freeze frame.  At the end of working time, the script will "freeze-frame" the video.  Generally used to determine if the formation at the end of working time is complete or not.  

`-lt, --leadin_time` : (*optional*, default=3) duration of the lead-in to the exit.   

`-wt, --working_time` : (*optional*, default=0) duration of working time for the jump.  (e.g. 35s for 4-way FS, 50s for 8-way, etc.)

`-jt, --jump_time` : (*optional*, default=60) duration of the output jump video.  Useful for trimming unnecessary video from the end of the jump/file.

`-ovr, --overlay_prof` : (*optional*) a profile that describes what various overlay elements (such as the counter/clock, the jump name, the team name, etc.) are present, their parameters (color, size, etc.) and where they are overlaid on the video.  These are a combination of script parameters as well as options that are fed to the various ffmpeg filters.

`-enc, --encoder_prof` : (*optional*)  (*advanced users*) an encoder profile is a set of options used to encode/transcode the video file.  This includes things like the output resolution, the output quality, and the output codec.  

`-an, --annotation` : (*optional*, default=None) the string to use for the annotation block of the overlay.  This could be something like the jump sequence, the team name, the videographer credits, etc.

`-xls, --excel_sheet` : If present, parse the given file (must be in .xlsx format).  The first row MUST be a valid set of parameters such as "--exit_frame" and "--working_time".  Each subsequent row is processed as a single jump with the corresponding parameters passed directly to the script.  


If you wish to modify a profile or layout, I strongly suggest making a copy of an existing one and working from that!

### EXAMPLES ###
Take `input.mp4`, stamp it with the frame number (so you can find things like the exit and slate frames), and output to `input_stamped.mp4`
```
jumpstamper.py  -i input.mp4  -s  -o stamped_input.mp4 
```

After looking at the stamped file, you've decided that the slate frame is number `255` and the exit is at frame number `890`.  You want to have a final stream that goes like this:
 - show the slate frame for 3 seconds
 - begin the jump with 5 seconds of lead-in prior to the exit frame
 - show the jump for 35 seconds of working time
 - at the 35 second point, freeze the current frame for 5 seconds
 - continue playing the rest of the jump up until 60 seconds, then end the file.
 - additionally, you want to display "Day 2, Jump 4, A-B-C-D-E" over the video.

The corresponding command line to execute is:
 ```
 ./jumpstamper.py -i input.mp4 -o d02j04_A-B-C-D-E.mp4 -sf 255 -st 3 -lt 5 -ef 890 -wt 35 -jt 60 -an "Day 2, Jump 4, A-B-C-D-E"
```

a


 
