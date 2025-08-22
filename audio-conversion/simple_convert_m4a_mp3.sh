#!/bin/bash

convert_m4a_to_mp3() {
    local m4a_file="$1"
    local mp3_file="${m4a_file%.m4a}.mp3"
    
    # Check if the mp3 file already exists
    if [[ -f "$mp3_file" ]]; then
        printf "MP3 file already exists: %s\n" "$mp3_file"
        return
    fi
    
    # Convert m4a to mp3 using ffmpeg
    if ! ffmpeg -i "$m4a_file" "$mp3_file"; then
        printf "Failed to convert: %s\n" "$m4a_file" >&2
    else
        printf "Successfully converted: %s\n" "$m4a_file"
    fi
}

export -f convert_m4a_to_mp3

find . -type f -iname '*.m4a' -exec bash -c 'convert_m4a_to_mp3 "$0"' {} \;

