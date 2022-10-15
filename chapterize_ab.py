import re
import subprocess
import argparse
import sys
from typing import Optional
from io import StringIO
from pathlib import Path
from os import getcwd
from rich.progress import track
from rich.console import Console
from rich.pretty import Pretty, pprint as rpprint
from rich.panel import Panel
from rich.table import Table
from vosk import Model, KaldiRecognizer, SetLogLevel, list_languages

'''
    Globals
'''

prog_name = 'Chapterize-Audiobooks'
prog_version = '0.1.0'
con = Console()

'''
    Utility Function Declarations
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


def verify_language(language: str) -> str:
    """
    Verifies language option in argparse.

    :param language: Model language
    :return: The language string if it is a supported language
    """

    # Allocate buffer to capture print output
    buff = StringIO()
    sys.stdout = buff
    list_languages()
    languages = buff.getvalue().split("\n")[0:-1]
    # Restore stdout
    sys.stdout = sys.__stdout__

    if not language:
        con.print("[bold red]ERROR:[/] Language option appears to be empty")
        sys.exit(14)
    elif language and language not in languages:
        con.print("[bold red]ERROR:[/] Invalid language code entered. Possible options:\n")
        rpprint(languages)
        print("\n")
        sys.exit(15)
    else:
        return language


'''
    Function Declarations
'''

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
    parser.add_argument('--language', '-l', dest='lang', nargs='?', default='en-us',
                        metavar='LANGUAGE', type=verify_language,
                        help='Model language to use. Requires a supported model (en-us is provided)')
    parser.add_argument('--list_languages', '-ll', action='store_true', help='List supported languages and exit')
    parser.add_argument('--cover_art', '-ca', dest='cover_art', nargs='?', default=None,
                        metavar='COVER_ART_PATH', type=path_exists, help='Path to cover art file. Optional')
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

    if args.list_languages:
        con.print("[green]Supported langauge codes:\n")
        list_languages()
        con.print(
            "\n[bold yellow]Only the 'en-us' model is provided. "
            "Other language models must be downloaded manually.\n"
            "Follow [link=https://alphacephei.com/vosk/models]this link[/link] "
            "to download models in other languages. See the README for more info.[/]\n"
        )
        exit(0)

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
    meta_file = meta_join if meta_join else Path(getcwd()).joinpath('metadata.txt')

    return args.audiobook, meta_file, meta_fields, args.lang


def print_table(list_dicts: list[dict]) -> None:
    """
    Formats a list of dictionaries into a table. Currently only used for timecodes.

    :param list_dicts: List of dictionaries to format
    :return: None
    """

    table = Table(
        title='[bold magenta]Parsed Timecodes for Chapters[/]',
        caption='[red]EOF[/] = End of File',
        # row_styles=['dim', '']
    )
    table.add_column('Start')
    table.add_column('End')
    table.add_column('Chapter')

    merge_rows = []
    for item in list_dicts:
        row = []
        for v in item.values():
            row.append(v)
        merge_rows.append(row)

    if len(merge_rows[-1]) != 3:
        merge_rows[-1].append('EOF')
    for i, row in enumerate(merge_rows):
        table.add_row(f"[green]{str(row[0])}", f"[red]{str(row[2])}", f"[bright_blue]{str(row[1])}")

    con.print(table)


def extract_metadata(audiobook: str | Path, metadata_file: str | Path) -> dict:
    """
    Extracts existing metadata from the input file.

    :param audiobook: Path to the input audiobook file
    :param metadata_file: Path to the temporary ffmpeg metadata file
    :return: A dictionary containing metadata values
    """

    subprocess.run(['ffmpeg', '-y', '-loglevel', 'quiet', '-i', audiobook,
                    '-f', 'ffmetadata', f'{metadata_file}'])

    meta_dict = {}
    # If path exists and has some content
    if path_exists(metadata_file) and Path(metadata_file).stat().st_size > 10:
        con.print("[bold green]SUCCESS![/] Metadata extraction complete")
        with open(metadata_file, 'r') as fp:
            meta_lines = fp.readlines()

        for line in meta_lines:
            line_split = line.split('=')
            if len(line_split) == 2:
                key, value = [x.strip('\n') for x in line_split]
                if key in ['title', 'genre', 'album_artist', 'artist', 'album', 'year']:
                    meta_dict[key] = value
    else:
        con.print("[bold yellow]WARNING:[/] Failed to parse metadata file, or none was found")
    # Delete the metadata file once done
    Path(metadata_file).unlink()

    return meta_dict


def extract_coverart(audiobook: str | Path) -> str | Path | None:
    """
    Extract coverart file from audiobook if present.

    :param audiobook: Input audiobook file
    :return: Path to cover art jpg file if found, otherwise None
    """

    covert_art = str(audiobook).replace('.mp3', '.jpg')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'quiet', '-i',
                    audiobook, '-an', '-c:v', 'copy', covert_art])
    if Path(covert_art).exists() and Path(covert_art).stat().st_size > 10:
        con.print("[bold green]SUCCESS![/] Cover art extracted")
        print("\n")
        return covert_art
    else:
        con.print("[bold yellow]WARNING:[/] Failed to extract cover art, or none was found\n")
        return None


def convert_to_wav(file: str | Path) -> Path:
    """
    Convert input file to lossless wav format. Currently unused, but might be useful for
    legacy versions of vosk.

    :param file: Input .mp3 file to convert
    :return: Path to .wav file
    """

    wav_file = str(file).replace('.mp3', '.wav')
    con.print("[magenta]Converting file to wav...[/]")
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

    try:
        parts = time.split(':')
        last, milliseconds = str(parts[-1]).split('.')
        parts[-1] = str(int(last) - 1)
    except Exception as e:
        parts = None
        milliseconds = None
        con.print(f"[bold red]ERROR:[/] Could not covert end chapter marker: [red]{e}[/]")
        sys.exit(9)

    return f"{':'.join(parts)}.{milliseconds}"


def split_file(audiobook: str | Path, timecodes: list,
               metadata: dict, cover_art: Optional[str]) -> None:
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
        command.extend(['-i', cover_art, '-id3v2_version', '3', '-metadata:s:v',
                        'comment="Cover (front)"'])
        stream = ['-map', '0:0', '-map', '1:0', '-c', 'copy']
    else:
        command.extend(['-id3v2_version', '3'])
        stream = ['-c', 'copy']

    # Handle metadata strings if they exist
    if 'album_artist' in metadata:
        command.extend(['-metadata', f"album_artist={metadata['album_artist']}",
                        '-metadata', f"artist={metadata['album_artist']}"])
    if 'genre' in metadata:
        command.extend(['-metadata', f"genre={metadata['genre']}"])
    if 'album' in metadata:
        command.extend(['-metadata', f"album={metadata['album']}"])
    if 'date' in metadata:
        command.extend(['-metadata', f"date={metadata['date']}"])
    if 'comment' in metadata:
        command.extend(['-metadata', f"comment={metadata['comment']}"])

    counter = 1
    for times in track(timecodes, description="Processing audiobook..."):
        command_copy = command.copy()
        if 'start' in times:
            start_list = ['-ss', times['start']]
            command_copy[5:5] = start_list
        if 'end' in times:
            command_copy.extend(['-to', times['end']])
        if 'chapter_type' in times:
            file_path = audiobook.parent.joinpath(f"{file_stem} - {times['chapter_type']}.mp3")
        else:
            file_path = audiobook.parent.joinpath(f"{file_stem} - {counter}.mp3")
            counter += 1

        command_copy.extend([*stream, '-metadata', f"title={times['chapter_type']}",
                             f'{file_path}'])

        try:
            with open(log_path, 'a+') as fp:
                fp.write('----------------------------------------------------\n\n')
                subprocess.run(command_copy, stdout=fp, stderr=fp)
        except Exception as e:
            con.print(
                f"[bold red]ERROR:[/] An exception occurred writing logs to file: " 
                f"[red]{e}[/]\nOutputting to stdout..."
            )
            subprocess.run(command_copy, stdout=subprocess.STDOUT)
        # Reset the list but keep reference
        command_copy = None


def generate_timecodes(audiobook: str | Path, language: str) -> Path:
    """
    Generate chapter timecodes using vosk Machine Learning API.

    :param audiobook: Path to input audiobook file
    :param language: Language used by the parser
    :return: Path to timecode file
    """

    sample_rate = 16000
    model_root = Path(r"model")
    try:
        if model_path := [d for d in model_root.iterdir() if d.is_dir() and 'vosk' in d.stem][0]:
            con.print(":white_heavy_check_mark: Local ML model found\n")
    except IndexError:
        con.print(
            "[bold yellow]WARNING:[/] Local ML model was not found (did you delete it?).\n"
            "The script will attempt to use an online model, which "
            "isn't always reliable. Fair warning."
        )
        model_path = None

    out_file = str(audiobook).replace('.mp3', '.srt')
    if Path(out_file).exists() and Path(out_file).stat().st_size > 10:
        con.print("[bold green]SUCCESS![/] An existing timecode file was found")
        print("\n")

        return Path(out_file)

    SetLogLevel(-1)
    model = Model(lang=language, model_path=model_path)
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

        con.print("[bold green]SUCCESS![/] Timecode file created\n")
    except Exception as e:
        con.print(f"[bold red]ERROR:[/] Failed to generate timecode file with vosk: [red]{e}[/]\n")
        sys.exit(3)

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
        'chapter and verse', 'chapters', 'this chapter', 'chapter of', 'in chapter'
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
                    chapter_type = 'Epilogue'
                elif 'chapter' in content[i+1]:
                    chapter_type = f'Chapter {counter}'
                    counter += 1
                elif 'prologue' in content[i+1]:
                    chapter_type = 'Chapter 0 (Prologue)'
                else:
                    chapter_type = ''
                # Build dict with start codes and marker
                if len(timecodes) == 0:
                    time_dict = {'start': '00:00:00', 'chapter_type': chapter_type}
                else:
                    time_dict = {'start': start, 'chapter_type': chapter_type}
                timecodes.append(time_dict)
            else:
                con.print("[bold yellow]WARNING:[/] A timecode was skipped. A Start time failed to match")
                continue
        else:
            continue
    # Add end key based on end time of next chapter minus one second for overlap
    for i, d in enumerate(timecodes):
        if i != len(timecodes) - 1:
            d['end'] = convert_time(timecodes[i+1]['start'])

    if timecodes:
        return timecodes
    else:
        con.print('[bold red]ERROR:[/] Timecodes list cannot be empty. Exiting...')
        sys.exit(2)


def main():
    """
    Main driver function.

    :return: None
    """

    print("\n\n")
    con.rule("\n[cyan]Starting script[/cyan]")
    print("\n")
    con.print("[magenta]Preparing chapterfying magic[/magenta] :zap:...")
    print("\n")

    audiobook_file, metadata_file, in_metadata, lang = parse_args()
    if not str(audiobook_file).endswith('.mp3'):
        con.print("[bold red]ERROR:[/] The script only works with .mp3 files (for now)")
        sys.exit(5)

    con.rule("[cyan]Extracting metadata[/cyan]")
    print("\n")
    parsed_metadata = extract_metadata(audiobook_file, metadata_file)
    # Combine the dicts, overwriting existing keys with user values if passed
    if parsed_metadata and in_metadata:
        con.print("[magenta]Merging extracted and user metadata[/]...\n")
        parsed_metadata |= in_metadata
    # This should never hit, as genre has a default value in argparse
    elif not in_metadata and not parsed_metadata:
        con.print("[bold yellow]WARNING:[/] No metadata to append. What a shame\n")
    # No metadata was found in file, using only argparse defaults
    elif in_metadata and not parsed_metadata:
        parsed_metadata = in_metadata
        print("\n")
    con.print(Panel(Pretty(parsed_metadata), title="ID3 Metadata"))
    print("\n")

    con.rule("[cyan]Discovering Cover Art")
    print("\n")
    if not parsed_metadata['cover_art']:
        con.print("[magenta]Perusing for cover art[/]...")
        cover_art = extract_coverart(audiobook_file)
    else:
        if parsed_metadata['cover_art'].exists():
            con.print("[bold green]SUCCESS![/] Cover art is...covered!")
            print("\n")
            cover_art = parsed_metadata['cover_art']
        else:
            con.print("[bold yellow]WARNING:[yellow] Cover art path does not exist")
            cover_art = None

    # Generate timecodes from mp3 file
    con.rule("[cyan]Generate Timecodes")
    print("\n")
    with con.status("[magenta]Sit tight, this might takes a while[/]...", spinner='pong'):
        timecodes_file = generate_timecodes(audiobook_file, lang)

    # Open file and parse timecodes
    with open(timecodes_file, 'r') as fp:
        file_lines = fp.readlines()
    con.rule("[cyan]Parse Timecodes")
    print("\n")
    timecodes = parse_timecodes(file_lines)
    if not timecodes:
        con.print("[bold red]ERROR:[/] Timecode dictionary cannot be empty")
        sys.exit(1)
    con.print("[bold green]SUCCESS![/] Timecodes parsed\n")
    print_table(timecodes)
    print("\n")

    # Split the file
    con.rule("[cyan]Chapterize File")
    print("\n")
    split_file(audiobook_file, timecodes, parsed_metadata, cover_art)
    # Count the generated files and compare to timecode dict
    file_count = (sum(1 for x in audiobook_file.parent.glob('*.mp3') if x.is_file()))
    expected = len(timecodes)
    if file_count >= expected:
        con.print(f"[bold green]SUCCESS![/] Audiobook split into {file_count} files\n")
    else:
        con.print(
            f"[bold yellow]WARNING:[/] {file_count} files were generated "
            f"which is less than the expected {expected}\n"
        )


if __name__ == '__main__':
    main()
