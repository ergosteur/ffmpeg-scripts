#!/bin/bash

# Parse the input and output filenames from the command line arguments
while getopts "i:o:" opt; do
  case $opt in
    i) input="$OPTARG" ;;
    o) output="$OPTARG" ;;
    *) echo "Usage: $0 -i input.mkv -o output.mkv" >&2; exit 1 ;;
  esac
done

# Check that the input and output filenames were provided
if [ -z "$input" ] || [ -z "$output" ]; then
  echo "Usage: $0 -i input.mkv -o output.mkv" >&2
  exit 1
fi

# Check that the input file is really 1920x1080
width=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of default=noprint_wrappers=1:nokey=1 "$input")
height=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=noprint_wrappers=1:nokey=1 "$input")
if [ "$width" != "1920" ] || [ "$height" != "1080" ]; then
  echo "Error: The input file must be 1920x1080." >&2
  exit 1
fi

# Crop the video and encode the output file using HEVC, 10-bit, with a quality of 23 and a tune for animation
ffmpeg -i "$input" -vf "crop=1440:1080" -c:v libx265 -pix_fmt yuv420p10le -x265-params crf=23:tune=animation -c:a copy -c:s copy -map_metadata 0 -map 0:v? -map 0:a? -map 0:s? "$output"
