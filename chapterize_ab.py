import os
import re
import subprocess
import argparse
from pprint import pprint
from typing import Optional
from pathlib import Path
from sys import exit
from vosk import Model, KaldiRecognizer, SetLogLevel

prog_name = 'Chapterize-Audiobooks'
prog_version = '0.1.0'


'''
    Function Declarations
'''


def path_exists(path: str | Path) -> Path:
    """
    Utility function to check if a path exists. Used by argparse.

    :param path: File path to verify
    :return: The tested file path if it exists
    """
    if Path(path).exists():
        return Path(path)
    else:
        raise FileExistsError(f"The path: <{path}> does not exist")


def parse_args():
    """
    Parses command line arguments.

    :return: A tuple containing the audiobook path, metadata file path, and user-defined metadata values
    """
    parser = argparse.ArgumentParser(
        description='''
        Splits a single monolithic mp3 audiobook file into multiple chapter files using Machine Learning. 
        Metadata and cover art are also extracted from the source file, but any user supplied values
        automatically take precedence when conflicts arise.
        ''')
    parser.add_argument('audiobook', nargs='?', metavar='AUDIOBOOK_PATH',
                        type=path_exists, help='Path to audiobook file. Required')
    parser.add_argument('--timecodes_file', '-tc', nargs='?', metavar='TIMECODES_FILE',
                        type=path_exists, dest='timecodes',
                        help='Path to generated srt timecode file (if ran previously in a different directory)')
    parser.add_argument('--cover_art', '-ca', dest='cover_art', nargs='?', default=None,
                        metavar='COVER_ART_PATH', type=path_exists, help='Path to cover art file. Optional.')
    parser.add_argument('--author', '-a', dest='author', nargs='?', default=None,
                        metavar='AUTHOR', type=str, help='Author. Optional metadata field')
    parser.add_argument('--title', '-t', dest='title', nargs='?', default=None,
                        metavar='TITLE', type=str, help='Audiobook title. Metadata field')
    parser.add_argument('--genre', '-g', dest='genre', nargs='?', default='Audiobook',
                        metavar='GENRE', type=str, help='Audiobook genre. Optional metadata field')
    parser.add_argument('--year', '-y', dest='year', nargs='?', default=None,
                        metavar='YEAR', type=str, help='Audiobook release year. Optional metadata field')
    parser.add_argument('--comment', '-c', dest='comment', nargs='?', default=None,
                        metavar='COMMENT', type=str, help='Audiobook comment. Optional metadata field')

    args = parser.parse_args()
    meta_fields = {'cover_art': args.cover_art if args.cover_art else None,
                   'genre': args.genre}
    if args.author:
        meta_fields['album_artist'] = args.author
    if args.title:
        meta_fields['album'] = args.title
    if args.year:
        meta_fields['date'] = args.year
    if args.comment:
        meta_fields['comment'] = args.comment
    meta_join = args.audiobook.parent.joinpath('metadata.txt')
    meta_file = meta_join if meta_join else Path(os.getcwd()).joinpath('metadata.txt')

    return args.audiobook, meta_file, meta_fields


def extract_metadata(audiobook: str | Path, metadata_file: str | Path) -> dict:
    """
    Extracts existing metadata from the input file.

    :param audiobook: Path to the input audiobook file
    :param metadata_file: Path to the temporary ffmpeg metadata file
    :return: A dictionary containing metadata values
    """
    subprocess.run(['ffmpeg', '-loglevel', 'quiet', '-i', audiobook,
                    '-f', 'ffmetadata', f'{metadata_file}'])

    meta_dict = {}
    print("Extracting metadata from the input...", end=" ")
    # If path exists and has some content
    if path_exists(metadata_file) and Path(metadata_file).stat().st_size > 10:
        print("Metadata file successfully generated:")
        with open(metadata_file, 'r') as fp:
            meta_lines = fp.readlines()

        for line in meta_lines:
            line_split = line.split('=')
            if len(line_split) == 2:
                key, value = [x.strip('\n') for x in line_split]
                if key in ['title', 'genre', 'album_artist', 'artist', 'album', 'year']:
                    meta_dict[key] = value
    else:
        print("ERROR: Failed to extract metadata file")
    # Delete the metadata file once done
    Path(metadata_file).unlink()

    return meta_dict


def extract_coverart(audiobook: str | Path):
    """
    Extract coverart file from audiobook if present.

    :param audiobook: Input audiobook file
    :return: Path to cover art jpg file if found, otherwise None
    """
    covert_art = str(audiobook).replace('.mp3', '.jpg')
    subprocess.run(['ffmpeg', '-loglevel', 'quiet', '-i',
                    audiobook, '-an', '-c:v', 'copy', covert_art])
    if Path(covert_art).exists() and Path(covert_art).stat().st_size > 10:
        print("Cover art extracted\n")
        return covert_art
    else:
        print("WARNING: Failed to extract cover art, or none was found\n")
        return None


def convert_to_wav(file: str | Path) -> Path:
    """
    Convert input file to lossless wav format. Currently unused, but might be useful for
    legacy versions of vosk.

    :param file: Input .mp3 file to convert
    :return: Path to .wav file
    """
    wav_file = str(file).replace('.mp3', '.wav')
    print("Converting file to wav...")
    result = subprocess.run([
        'ffmpeg', '-i', file, '-ar', '16000', '-ac', '1', wav_file
    ])

    print(f"Subprocess result: {result.returncode}")

    return Path(wav_file)


def convert_time(time: str) -> str:
    """
    Convert timecodes for chapter markings.
    Helper function to subtract 1 second from each start time, which is used as the
    end time for the previous chapter segment.

    :param time: Timecode in Sexagesimal format
    :return: Sexagesimal formatted time marker
    """
    parts = time.split(':')
    last = str(parts[-1]).split('.')[0]
    milliseconds = parts[-1].split('.')[1]
    parts[-1] = str(int(last) - 1)

    return f"{':'.join(parts)}.{milliseconds}"


def split_file(audiobook: str | Path, timecodes: list,
               metadata: dict, cover_art: Optional[str]):
    """
    Splits a single .mp3 file into chapterized segments.

    :param audiobook: Path to original .mp3 audiobook
    :param timecodes: List of start/end markers for each chapter
    :param metadata: File metadata passed via CLI and/or parsed from audiobook file
    :param cover_art: Optional path to cover art
    :return: An integer status code
    """

    file_stem = audiobook.stem
    # Set the log path for output. If it exists, generate new filename
    log_path = audiobook.parent.joinpath('ffmpeg_log.txt')
    if log_path.exists():
        with open(log_path, 'a+') as fp:
            fp.write('********************************************************\n')
            fp.write('NEW LOG START\n')
            fp.write('********************************************************\n\n')

    command = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'info', '-i', f'{str(audiobook)}']
    if cover_art:
        command.extend(['-i', cover_art, '-map', '0:0', '-map', '1:0',
                        '-c', 'copy', '-id3v2_version', '3', '-metadata:s:v:1',
                        'title="Cover"'])
    else:
        command.extend(['-c', 'copy', '-id3v2_version', '3'])

    # Handle metadata strings if they exist
    if 'album_artist' in metadata and cover_art:
        command.extend(['-metadata:s:a:0', f"album_artist={metadata['album_artist']}"])
    elif 'album_artist' in metadata:
        command.extend(['-metadata', f"album_artist={metadata['album_artist']}"])
    if 'genre' in metadata and cover_art:
        command.extend(['-metadata:s:a:0', f"genre={metadata['genre']}"])
    elif 'genre' in metadata:
        command.extend(['-metadata', f"genre={metadata['genre']}"])
    if 'album' in metadata and cover_art:
        command.extend(['-metadata:s:a:0', f"album={metadata['album']}"])
    elif 'album' in metadata:
        command.extend(['-metadata', f"album={metadata['album']}"])
    if 'date' in metadata and cover_art:
        # command.extend(['-meta
        command.extend(['-metadata:s:a:0', f"date={metadata['date']}"])
    elif 'date' in metadata:
        command.extend(['-metadata', f"date={metadata['date']}"])
    if 'comment' in metadata and cover_art:
        command.extend(['-metadata:s:a:0', f"comment={metadata['comment']}"])
    elif 'comment' in metadata:
        command.extend(['-metadata', f"comment={metadata['comment']}"])

    counter = 1
    for times in timecodes:
        command_copy = command.copy()
        if 'start' in times:
            command_copy.extend(['-ss', times['start']])
        if 'end' in times:
            command_copy.extend(['-to', times['end']])
        if 'chapter_type' in times:
            file_path = audiobook.parent.joinpath(f"{file_stem} - {times['chapter_type']}.mp3")
        else:
            file_path = audiobook.parent.joinpath(f"{file_stem} - {counter}.mp3")

        if cover_art:
            command_copy.extend(['-metadata:s:a:0', f"title={times['chapter_type']}",
                                 f'{file_path}'])
        else:
            command_copy.extend(['-metadata', f"title={times['chapter_type']}",
                                 f'{file_path}'])
        counter += 1

        try:
            with open(log_path, 'a+') as fp:
                fp.write('----------------------------------------------------\n\n')
                subprocess.run(command_copy, stdout=fp, stderr=fp)
        except Exception as e:
            print(f"An exception occurred writing logs to file: {e}\nOutputting to stdout...")
            subprocess.run(command_copy, stdout=subprocess.STDOUT)


def generate_timecodes(audiobook: str | Path) -> Path:
    """
    Generate chapter timecodes using vosk Machine Learning API.

    :param audiobook: Path to input audiobook file
    :return: Path to timecode file
    """
    sample_rate = 16000
    out_file = str(audiobook).replace('.mp3', '.srt')
    if Path(out_file).exists() and Path(out_file).stat().st_size > 10:
        print("NOTE: There appears to be an existing timecode file. Skipping creation\n")
        return Path(out_file)

    SetLogLevel(-1)
    model = Model(lang="en-us",
                  model_path=r"vosk_api/python/example/model/vosk-model-small-en-us-0.15")
    rec = KaldiRecognizer(model, sample_rate)
    rec.SetWords(True)

    try:
        # Convert the file to wav (if needed), and stream output to file
        with subprocess.Popen(["ffmpeg", "-loglevel", "quiet", "-i",
                               audiobook,
                               "-ar", str(sample_rate), "-ac", "1", "-f", "s16le", "-"],
                              stdout=subprocess.PIPE).stdout as stream:
            with open(out_file, 'w+') as fp:
                fp.writelines(rec.SrtResult(stream))
    except Exception as e:
        print(f"Failed to generate timecode file with vosk: {e}\n")
        exit(3)

    return Path(out_file)


def parse_timecodes(content: list) -> list[dict[str, str]]:
    """
    Parses the contents of the timecode file generated by vosk and generates start/end times,
    as well as chapter type (prologue, epilogue, etc.) if available.

    :param content: List of timecodes extracted from the output of vosk
    :return: A list of dictionaries containing start, end, and chapter type data
    """

    # Some false positive phrases that trigger a chapter marker...will need building over time
    excluded_phrases = [
        'chapter and verse', 'chapters'
    ]
    timecodes = []
    counter = 1

    for i, line in enumerate(content):
        if (
                # Not the end of the list
                i != (len(content) - 1) and
                # Doesn't contain an excluded phrase
                not any(x in content[i+1] for x in excluded_phrases) and
                # Contains a chapter substring
                ('chapter' in content[i+1] or
                 'prologue' in content[i+1] or
                 'epilogue' in content[i+1])
        ):
            if start_regexp := re.search(r'\d\d:\d\d:\d\d,\d+(?=\s-)', line, flags=0):
                start = start_regexp.group(0).replace(',', '.')

                if 'epilogue' in content[i+1]:
                    chapter_type = 'epilogue'
                elif 'chapter' in content[i+1]:
                    chapter_type = f'Chapter {counter}'
                    counter += 1
                elif 'prologue' in content[i+1]:
                    chapter_type = 'prologue'
                else:
                    chapter_type = ''
                # Build dict with start codes and marker
                if len(timecodes) == 0:
                    time_dict = {'start': '00:00:00', 'chapter_type': chapter_type}
                else:
                    time_dict = {'start': start, 'chapter_type': chapter_type}
                timecodes.append(time_dict)
            else:
                print("Warning: A timecode was skipped. A Start/End time failed to match")
                continue
        else:
            continue
    # Add end key based on end time of next chapter minus one second for overlap
    for i, d in enumerate(timecodes):
        if i != len(timecodes) - 1:
            d['end'] = convert_time(timecodes[i + 1]['start'])

    if timecodes:
        return timecodes
    else:
        print('Timecodes list cannot be empty. Exiting...')
        exit(2)


def main():
    """
    Main driver function.

    :return: None
    """
    print("Starting script...\n")
    audiobook_file, metadata_file, in_metadata = parse_args()
    parsed_metadata = extract_metadata(audiobook_file, metadata_file)
    # Combine the dicts, overwriting existing keys with user values if passed
    parsed_metadata |= in_metadata
    pprint(parsed_metadata)
    print("\n")

    if not parsed_metadata['cover_art']:
        print("Perusing for cover art...", end=" ")
        cover_art = extract_coverart(audiobook_file)
    else:
        print("Path to cover art provided\n")
        cover_art = parsed_metadata['cover_art']

    # Generate timecodes from mp3 file
    print("Generating timecodes from input file...this might takes a while")
    timecodes_file = generate_timecodes(audiobook_file)

    # Open file and parse timecodes
    with open(timecodes_file, 'r') as fp:
        file_lines = fp.readlines()
    print("Parsing timecode file...", end=" ")
    timecodes = parse_timecodes(file_lines)
    if not timecodes:
        print("ERROR: Timecode dictionary cannot be empty")
        exit(1)
    print("Success! Parsed timecodes:")
    pprint(timecodes)

    print("\nRunning split on input file...", end=" ")
    split_file(audiobook_file, timecodes, parsed_metadata, cover_art)
    # Subtract 1, accounting for the existing file
    file_count = (sum(1 for x in audiobook_file.parent.glob('*.mp3') if x.is_file())) - 1
    if file_count >= len(timecodes):
        print(f"SUCCESS! File successfully split into {file_count} files")
    else:
        print(f"WARNING: {file_count} files were generated, which is less than expected")


if __name__ == '__main__':
    main()
