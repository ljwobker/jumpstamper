# Jumpstamper

### NAME ###

**jumpstamper** - a program to overlay ("stamp") various things on top of skydiving videos

### DESCRIPTION ### 
"Jumpstamper" was designed to add things like timestamps and frame numbers and text output over competitive
skydiving video streams.  It could possibly be reconfigured for a number of other things but most of the functionality (and certainly much of the context) comes from the competition skydiving universe.

### DEPENDENCIES ###
Python >= 3.7.  Jumpstamper relies heavily on [ffmpeg](https://github.com/kkroening/ffmpeg-python/) and its associated [filters](https://ffmpeg.org/ffmpeg-filters.html), and is built around the [ffmpeg-python](https://github.com/kkroening/ffmpeg-python/blob/master/README.md) library.  We use [openpyxl](https://openpyxl.readthedocs.io/en/stable/) to parse excel files.  Both are available on [pypi](http://pypi.org), you should use pip/pip3 to install them.

```
pip3 install openpyxl ffmpeg-python
```

Fonts for FFMpeg aren't exactly straightforward, it's very possible you'll have to adjust the code to find fonts that are installed on your particular system.  The default font is set inside the `self.common_dt` parameter dictionary.  On my Linux system, the line looks like this:

`            'font' : 'Arial',`

but I can get a LOT more specific if I want to:

`            'fontfile' : '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf,'`

One user reported that on a Mac, this line works:

`            'fontfile' : '/Library/Fonts/Arial.ttf',`


### THEORY ###
the script tries to at least *loosely* follow the ffmpeg config model, where you have an input file, a set of operations/transformations on that file, and an output file.  A set of command line options and/or profiles are used to control the behavior.  


### EXAMPLES / TIPS ###

---


Take `input.mp4`, stamp it with the frame number (so you can find things like the exit and slate frames), and output to `stamped_input.mp4`:
```
jumpstamper.py  -i input.mp4  -s  -o stamped_input.mp4 
```

---


After looking at the stamped file, you've decided that the slate frame is number `255` and the exit is at frame number `890`.  You want to have a final result that goes like this:
 - show the slate frame for 3 seconds
 - begin the jump with 5 seconds of lead-in prior to the exit frame
 - show the jump for 35 seconds of working time
 - at the 35 second point, freeze the current frame for 5 seconds
 - continue playing the rest of the jump up until 60 seconds, then end the file.
 - additionally, you want to display "Day 2, Jump 4, A-B-C-D-E" over the video.  (If you're going to put spaces or commas or anything that might confuse the shell, you MUST wrap them in quotes...)

The corresponding command line to execute is:
 ```
 ./jumpstamper.py -i input.mp4 -o d02j04_A-B-C-D-E.mp4 -sf 255 -st 3 -lt 5 -ef 890 -wt 35 -jt 60 -an "Day 2, Jump 4, A-B-C-D-E"
```

---

Now say you have a bunch of files from a hard day of jumping and you want to do the frame overlay on all of them at once.  We'll just use a [tiny bit of BASH](https://tldp.org/LDP/abs/html/abs-guide.html#EX22) here and do them all in one shot:
```
#!/bin/bash
for file in GOPR*.MP4
do 
    ./jumpstamper.py -i $file -s -o stamped-$file
done
```

---

If you want to process a bunch of files at once, you can build an excel file with all the different times and frame numbers, and have the script parse each row and stamp each jump accordingly.  Here our excel file is named `encode.xlsx`:
```
./jumpstamper.py -xls encode.xlsx
```
An example.xlsx file is included, the format is such that each row represents a single jump to process.  The column headers are the 'long form' variable names such as `slate_time` or `exit_frame`


---

If you aren't interested in the exact exit time, but maybe want to just trim your jumps some and re-encode them, set `working_time` to zero with `-wt 0` to suppress the timer overlay.  For example, if you wanted to remove the first 15 seconds of the video for a jump encoded at 48 fps and keep the 60 seconds following that point, you could do the following.  (Note: because the exit_frame is in frames, you have to do the math yourself to convert seconds to frames, which means you also have to know the frame rate of your video...)
```
./jumpstamper.py -i input.mp4 -o output.mp4 -wt 0 -ef 720 -jt 60
```

---

If you want to just transcode through an entire jump with the timer counting up the whole time, set the "working_time" and "jump_time" values to something arbitrarily high.  
```
jumpstamper.py -i GOPR2935.MP4 -o thru.mp4 -enc quick -wt 90 -ef 0 -jt 90
```

---



### OPTIONS ###

There are quite a few, but the idea is we wanted to be able to put all the possibilities into a single command.  

`-i, --input_file` : the input file.

`-o, --output_file` : the output file.  Note that unlike ffmpeg, jumpstamper has an explicit option to define the output file.  

`-s, --stamp` : (*optional*) take the input file and "stamp" it with frame numbers.  These can then be used to determine the frame numbers for parameters such as the exit frame or slate frame.

`-ef, --exit_frame` : (*optional*) the frame number of the exit from the original input video, (i.e. when the timer for a scoring jump begins)

`-sf, --slate_frame` : (*optional*, default=0) the frame number (from the original input video) of a readable slate for competition/scoring jumps -- or just a fun camera geek or still if you're into that sort of thing...

`-st, --slate_time` : (*optional*, default=3 if slate_frame is used, 0 otherwise) duration of the slate frame.

`-ft, --freeze_time` : (*optional*, default=0) duration of the freeze frame.  At the end of working time, the script will "freeze-frame" the video.  Generally used to determine if the formation at the end of working time is complete or not.  

`-lt, --leadin_time` : (*optional*, default=0) duration of the lead-in to the exit.   

`-wt, --working_time` : (*optional*, default=0) duration of working time for the jump.  (e.g. 35s for 4-way FS, 50s for 8-way, etc.).  If `working_time` is set to zero, no timer is displayed for that jump.  This can be useful if you just want to trim down a video without caring exactly when the exit is.

`-jt, --jump_time` : (*optional*, default=60) duration of the output jump video.  Useful for trimming unnecessary video from the end of the jump/file.  Note if the jump time "ends" before the freeze frame begins, you won't get the freeze.

`-dt, --fade_time`: (*optional*, default is 0) duration of the fade out from the main jump.  (Note that the shortcut is `dt` rather than `ft` because `freeze_time` got there first!)

`-ovr, --overlay_prof` : (*optional*) a profile that describes what various overlay elements (such as the counter/clock, the jump name, the team name, etc.) are present, their parameters (color, size, etc.) and where they are overlaid on the video.  These are a combination of script parameters as well as options that are fed to the various ffmpeg filters.

`-enc, --encoder_prof` : (*optional*)  (*advanced users*) an encoder profile is a set of options used to encode/transcode the video file.  This includes things like the output resolution, the output quality, and the output codec.  A `quick` profile is included specifically for things like testing and stamping.

`-an, --annotation` : (*optional*, default=None) the string to use for the annotation block of the overlay.  This could be something like the jump sequence, the team name, the videographer credits, etc.

`-xls, --excel_sheet` : If present, parse the given file (must be in .xlsx format).  The first row MUST be a valid set of parameters such as "--exit_frame" and "--working_time".  Each subsequent row is processed as a single jump with the corresponding parameters passed directly to the script.  Be aware that the input/output file columns need to be in TEXT format within excel, and they are relative to wherever you called the script from.  So if your input_file is `./foozle/jump1.mp4` and you call it from `/home/judge1` then your input file must be `/home/judge1/foozle/jump1.mp4`


If you wish to modify a profile or layout, I strongly suggest making a copy of an existing one and working from that!


 ### General Notes.... ###
 - ffmpeg is multithreaded by default, there is very little advantage to explictly launching multiple parallel instances.  
 - encoding time/speed is HUGELY variable, based on what encoder options you use,  what kind of machine you're running, the resolution, frame rate, and length of your source video.  The rabbit hole of optimizations here is deep and I hope to get to it one day...
 - You can use Ctrl-C to stop a running encode.


### About the author ###
LJ Wobker is an avid competitive skydiver, a network engineer by trade, and knows only just enough python to code something up like this.  Please be aware that I've mostly written this for myself and my friends to use, and it's not something you should consider professional by any stretch, nor fully supported.  If you have an idea for improvement, please let me know via email at [ljwobker@pobox.com](mailto:ljwobker@pobox.com) and I'll see what we can do.  If you find something that doesn't work, please let me know.  Be aware that the FFMPEG program is pretty damn powerful, but it's also quite complex and the filtering syntax is not always obvious.  I'll be a lot lot lot more prone to help out if you've read over the relevant filter docs and the ffmpeg-python docs/examples so you have some idea of what's going on.