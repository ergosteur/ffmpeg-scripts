param(
    [Parameter(Mandatory=$false)]
    [string]$inputFile,
    [Parameter(Mandatory=$false)]
    [string]$outputFile,
    [Parameter(Mandatory=$false)]
    [int]$bitrateKbps
)

# If no input file is specified, use the only video file in the current directory
if (!$inputFile) {
    $videoFiles = Get-ChildItem -Include "*.mp4","*.mkv","*.mov" -Recurse -Depth 0
    if ($videoFiles.Count -eq 1) {
        $inputFile = $videoFiles[0].FullName
    } else {
        Write-Error "No input file specified and there is not exactly one video file in the current directory."
        exit 1
    }
}

# If no output file is specified, add a [4x3] suffix to the input file name
if (!$outputFile) {
    $fileNameWithoutExtension = [IO.Path]::GetFileNameWithoutExtension($inputFile)
    $extension = [IO.Path]::GetExtension($inputFile)
    $outputFile = "${fileNameWithoutExtension}[4x3]${extension}"
}

# If no bitrate is specified, try to get the bitrate of the input video
if (!$bitrateKbps) {
    $bitrate = & ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 $inputFile
    if ($bitrate -eq 'N/A') {
        Write-Error "Bitrate could not be determined. Please specify the bitrate using the -bitrateKbps parameter."
        exit 1
    }
    # Convert the bitrate to kilobits per second
    $bitrateKbps = [Math]::Round($bitrate / 1000)
}

# Use ffmpeg to crop the video and retain all original metadata
& ffmpeg -i $inputFile -vf "crop=ih*4/3:ih" -b:v ${bitrateKbps}k -c:a copy -map_metadata 0 $outputFile
