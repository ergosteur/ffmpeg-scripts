param (
    [Parameter(Mandatory=$true)][string]$input,
    [Parameter(Mandatory=$true)][string]$output
)

# Check that the input file is really 1920x1080
$ffprobe = ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$input"
$width, $height = $ffprobe.Split(",")
if ($width -ne "1920" -or $height -ne "1080") {
    Write-Error "Error: The input file must be 1920x1080."
    exit 1
}

# Crop the video and encode the output file using HEVC, 10-bit, with a quality of 23 and a tune for animation
ffmpeg -i "$input" -vf "crop=1440:1080" -c:v libx265 -pix_fmt yuv420p10le -x265-params crf=23:tune=animation -c:a copy -c:s copy -map_metadata 0 -map 0:v? -map 0:a? -map 0:s? "$output"
