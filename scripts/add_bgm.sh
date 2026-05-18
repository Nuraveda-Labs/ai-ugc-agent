#!/usr/bin/env bash
# add_bgm.sh — mix BGM under a video with sidechain ducking.
# Usage:  add_bgm.sh <video_in> <bgm_in> <video_out>
#
# If <bgm_in> is "synth" or doesn't exist, a soft ambient pad is generated.
# Sidechain compresses BGM under the VO so dialogue stays clear.
set -euo pipefail

VID_IN="${1:?video.mp4}"
BGM_IN="${2:-synth}"
VID_OUT="${3:?out.mp4}"

mkdir -p "$(dirname "$VID_OUT")"

# Get video duration
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VID_IN")
DUR_INT=$(printf "%.0f" "$DUR")

# If BGM not provided / not found / "synth", generate an ambient pad
if [[ "$BGM_IN" == "synth" || ! -f "$BGM_IN" ]]; then
  TMP_BGM="/tmp/bgm_synth_${RANDOM}.mp3"
  echo "[bgm] synth pad ${DUR_INT}s -> $TMP_BGM"
  # Soft ambient pad: layered sines at musical intervals (A2, E3, A3, C#4)
  # plus brown noise wash, lowpass-filtered, slow tremolo for "live" feel
  ffmpeg -y -loglevel error \
    -f lavfi -i "sine=frequency=110:sample_rate=48000:duration=${DUR_INT}" \
    -f lavfi -i "sine=frequency=164.81:sample_rate=48000:duration=${DUR_INT}" \
    -f lavfi -i "sine=frequency=220:sample_rate=48000:duration=${DUR_INT}" \
    -f lavfi -i "sine=frequency=277.18:sample_rate=48000:duration=${DUR_INT}" \
    -f lavfi -i "anoisesrc=color=brown:sample_rate=48000:duration=${DUR_INT}" \
    -filter_complex "
      [0:a]volume=0.18[a1];
      [1:a]volume=0.13[a2];
      [2:a]volume=0.10[a3];
      [3:a]volume=0.08[a4];
      [4:a]volume=0.10,lowpass=f=600[noise];
      [a1][a2][a3][a4][noise]amix=inputs=5:duration=longest:normalize=0,
      lowpass=f=900,
      tremolo=f=0.18:d=0.4,
      loudnorm=I=-26:TP=-2:LRA=4
    " \
    -ac 2 -ar 48000 -c:a libmp3lame -b:a 160k "$TMP_BGM"
  BGM_IN="$TMP_BGM"
fi

echo "[mix] $VID_IN + $BGM_IN -> $VID_OUT"

# Loop BGM to fit, normalize, sidechain duck under VO, mix.
ffmpeg -y -loglevel error \
  -i "$VID_IN" -stream_loop -1 -i "$BGM_IN" \
  -filter_complex "
    [1:a]loudnorm=I=-23:TP=-2.0:LRA=7,volume=0.30[bg];
    [0:a][bg]sidechaincompress=threshold=0.045:ratio=10:attack=15:release=350[ducked];
    [0:a][ducked]amix=inputs=2:duration=first:dropout_transition=2,
    loudnorm=I=-16:TP=-1.5:LRA=9[aout]
  " \
  -map 0:v -map "[aout]" -t "$DUR" \
  -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart \
  "$VID_OUT"

echo "[mix] done: $VID_OUT"
