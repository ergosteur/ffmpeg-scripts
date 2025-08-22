#!/bin/bash

# Check if the correct number of arguments is passed
if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <input_dir> <output_dir>"
  echo "Error: Both input and output paths must be provided."
  exit 1
fi

# Validate input arguments for proper quoting
for arg in "$@"; do
  if [[ "$arg" =~ \\[[:space:]] || "$arg" =~ \\[[:punct:]] ]]; then
    echo "Error: Paths must be quoted and should not contain escaped spaces or special characters."
    echo "Example: \"$0 '/path/with spaces' '/another/path/with spaces'\""
    exit 1
  fi
done

# Get input and output directories from command-line arguments
input_dir="$1"
output_dir="$2"

# Remove trailing slashes from input and output directories if present
input_dir="${input_dir%/}"
output_dir="${output_dir%/}"

# Initialize counters
converted_count=0
copied_count=0
skipped_count=0

# Ensure the output directory exists
mkdir -p "$output_dir"

# Process all .m4a files: convert to .mp3 and save to the output directory
echo "Processing .m4a files..."
find "$input_dir" -type f -name '*.m4a' | while IFS= read -r file; do
  # Get the relative path of the file (preserving subdirectory structure)
  relative_path=$(dirname "${file#$input_dir/}")
  # Create the corresponding directory in the output path
  mkdir -p "$output_dir/$relative_path"
  # Extract the base name of the file (without the directory or extension)
  base_name=$(basename "${file%.m4a}")
  # Convert the file and save it in the corresponding output directory
  output_file="$output_dir/$relative_path/$base_name.mp3"
  if [[ -f "$output_file" ]]; then
    echo "Skipped: $file (already exists)"
    skipped_count=$((skipped_count + 1))
  else
    ffmpeg -i "$file" -c:a libmp3lame -q:a 0 -map_metadata 0 -n "$output_file" && \
    echo "Converted: $file -> $output_file"
    converted_count=$((converted_count + 1))
  fi
done

# Process all .mp3 files: copy them to the output directory without re-encoding
echo "Processing .mp3 files..."
find "$input_dir" -type f -name '*.mp3' | while IFS= read -r file; do
  # Get the relative path of the file (preserving subdirectory structure)
  relative_path=$(dirname "${file#$input_dir/}")
  # Create the corresponding directory in the output path
  mkdir -p "$output_dir/$relative_path"
  # Copy the .mp3 file to the corresponding directory in the output path
  output_file="$output_dir/$relative_path/$(basename "$file")"
  if [[ -f "$output_file" ]]; then
    echo "Skipped: $file (already exists)"
    skipped_count=$((skipped_count + 1))
  else
    cp "$file" "$output_file" && echo "Copied: $file -> $output_file"
    copied_count=$((copied_count + 1))
  fi
done

# Summary
echo
echo "Summary:"
echo "Total .m4a files converted: $converted_count"
echo "Total .mp3 files copied: $copied_count"
echo "Total files skipped (already exist): $skipped_count"
