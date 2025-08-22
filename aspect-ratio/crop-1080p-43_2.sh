#!/bin/bash

# Check if the correct number of arguments are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <input file> <output file>"
    exit 1
fi

# Assign the input arguments to variables
inputFile="$1"
outputFile="$2"

# Get the bitrate of the input video
bitrate=$(ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$inputFile")

# Convert the bitrate to kilobits per second
bitrateKbps=$((bitrate / 1000))

# Use ffmpeg to crop the video and retain all original metadata
ffmpeg -i "$inputFile" -vf "crop=ih*4/3:ih" -b:v ${bitrateKbps}k -c:a copy -map_metadata 0 "$outputFile"
