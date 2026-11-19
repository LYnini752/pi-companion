#!/usr/bin/env python3
"""Small CLI adapter around pinned pywhispercpp; loaded in a bounded subprocess."""
import argparse
from pathlib import Path
from pywhispercpp.model import Model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', required=True)
    parser.add_argument('-f', required=True)
    parser.add_argument('-l', default='zh')
    parser.add_argument('-of', required=True)
    parser.add_argument('-t', type=int, default=4)
    parser.add_argument('-otxt', action='store_true')
    parser.add_argument('-nt', action='store_true')
    args = parser.parse_args()
    if not Path(args.m).is_file():
        parser.error('Model must be an existing local file; automatic downloads are disabled')
    options = {'initial_prompt': '以下是普通话对话，请使用简体中文。'} if args.l == 'zh' else {}
    model = Model(args.m, n_threads=args.t, params_sampling_strategy=1, print_realtime=False,
                  print_progress=False, print_timestamps=False, print_special=False, **options)
    segments = model.transcribe(args.f, language=args.l)
    Path(args.of + '.txt').write_text(''.join(segment.text for segment in segments).strip(), encoding='utf-8')


if __name__ == '__main__':
    main()
