#!/bin/bash
# Extract + OCR every downloaded Vikings/Scots preview video (scripts/extract_video_frames.py), Beastyqt first.
# 1 fps for the Beastyqt overviews, 0.5 fps for the rest. GPU OCR through .cache/ocr-venv (onnxruntime-directml).
# Usage: bash scripts/run_upcoming_ocr.sh [id:fps ...]
cd "$(dirname "$0")/.."
SPECS="$*"
[ -z "$SPECS" ] && SPECS="nd74LibluQ0:1 c_oaynL66jY:1 uNw-K34ZDPs:0.5 qlogYcWhKEU:0.5 ehO1BOe7wG8:0.5 wzT5WTqIIU4:0.5 vKPxGYSbN2Q:0.5 xjYytU_zXTA:0.5 qARfRxyhRhA:0.5 OCna8RhsP9E:0.5"
for spec in $SPECS; do
  id=${spec%%:*}; fps=${spec##*:}
  if [ ! -f ".cache/upcoming-videos/$id.mp4" ]; then echo "{\"id\":\"$id\",\"status\":\"missing\"}"; continue; fi
  OCR_DML=1 timeout 2400 .cache/ocr-venv/Scripts/python -X utf8 scripts/extract_video_frames.py "$id" --fps "$fps" --workers 4 </dev/null 2>&1 | grep -v "OrtInferSession\|Warning"
done
echo ALLDONE
