
@echo off
vspipe.exe ep01.vpy - --y4m | x264 --b-adapt 2 --keyint 240 --min-keyint 23 --direct auto --subme 11 --trellis 2 --no-dct-decimate --no-fast-pskip --preset placebo --rc-lookahead 72 --crf 14.5 --me umh --deblock -1:-1 --qcomp 0.72 --aq-mode 3 --aq-strength 0.85 --merange 32 --no-mbtree --ipratio 1.40 --pbratio 1.30 --psy-rd 0.90:0.00 --bframes 16 --ref 16 --fade-compensate 0 --output-depth 10 --colormatrix bt709 --slow-firstpass --partitions all --demuxer y4m --output Output/01.mkv -
pause