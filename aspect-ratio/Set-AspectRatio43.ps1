<#
.SYNOPSIS
    This script changes the aspect ratio of all .mp4 and .mkv files in a specified directory.

.DESCRIPTION
    This script uses ffmpeg to change the aspect ratio of all .mp4 and .mkv files in a specified input directory and its subdirectories. The output files are saved to a specified output directory with the same file names as the input files.

.PARAMETER InputDirectory
    The path to the input directory containing the .mp4 and .mkv files to process.

.PARAMETER OutputDirectory
    The path to the output directory where the processed files will be saved.

.PARAMETER OutputFormat
    The desired output format of the processed files. Can be either "mkv" or "mp4". If not specified, the script will keep the same format as the input files.

.EXAMPLE
    .\script.ps1 -InputDirectory C:\path\to\input\directory -OutputDirectory C:\path\to\output\directory

.EXAMPLE
    .\script.ps1 -InputDirectory C:\path\to\input\directory -OutputDirectory C:\path\to\output\directory -OutputFormat mp4

.NOTES
    Version:        1.0
    Author:         Bing
    Creation Date:  2023-06-25
#>

param (
    [Parameter(Mandatory=$true)]
    [string]$InputDirectory,
    [Parameter(Mandatory=$true)]
    [string]$OutputDirectory,
    [string]$OutputFormat
)

Get-ChildItem -Path $InputDirectory -Include *.mp4, *.mkv -Recurse | ForEach-Object {
    $inputFile = $_.FullName
    $outputFile = Join-Path $OutputDirectory ([System.IO.Path]::GetFileNameWithoutExtension($_.Name) + "." + $(if ($OutputFormat) { $OutputFormat } else { $_.Extension }))
    & ffmpeg -i $inputFile -c copy -aspect 4:3 -bsf:v "h264_metadata=sample_aspect_ratio=4/3" $outputFile
}
