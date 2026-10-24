"""Transcribe a downloaded preview video's audio with faster-whisper (CPU, int8) when YouTube captions are unavailable.

Input:  .cache/upcoming-videos/<id>.m4a
Output: data/upcoming-civs/transcripts/<id>.whisper.txt  ([mm:ss] text per segment, same shape as the caption .txt files)
Usage:  python -X utf8 scripts/whisper_transcribe.py <id> [--model small.en] [--lang en]
"""
import argparse, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('vid'); ap.add_argument('--model', default='small.en'); ap.add_argument('--lang', default='en')
    args = ap.parse_args()
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device='cpu', compute_type='int8', cpu_threads=12,
                         download_root=str(ROOT / '.cache/whisper'))
    segments, info = model.transcribe(str(ROOT / f'.cache/upcoming-videos/{args.vid}.m4a'), language=args.lang,
                                      vad_filter=True, beam_size=5,
                                      initial_prompt='Age of Empires IV Vikings Scots: Bondi, Berserker, Hirdman, Völur, Longhouse, '
                                                     'Shield Maiden, Jylland Knight, Skåne Crossbowman, Konungr Hall, Baugr Fort, '
                                                     'Cateran, Gallowglass, Kirkman, Ghillie, Tacksman, Border Reiver, Tower House.')
    out = ROOT / f'data/upcoming-civs/transcripts/{args.vid}.whisper.txt'
    with open(out, 'w', encoding='utf-8') as fh:
        for s in segments:
            fh.write(f'[{int(s.start) // 60:02d}:{int(s.start) % 60:02d}] {s.text.strip()}\n'); fh.flush()
    print('done', out, info.duration)

if __name__ == '__main__':
    main()
