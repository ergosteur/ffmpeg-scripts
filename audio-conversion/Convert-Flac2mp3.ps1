$files = Get-ChildItem -Filter '*.flac' 
$files | ForEach-Object { ffmpeg -i $_.FullName -c:a libmp3lame -q:a 0 -map_metadata 0 "$($_.Directory)\$($_.Basename).mp3" }