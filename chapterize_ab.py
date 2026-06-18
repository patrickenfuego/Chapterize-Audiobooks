#!/usr/bin/env python3

import re
import subprocess
import argparse
import sys
from typing import Optional, TypeVar
from pathlib import Path
from shutil import (
    unpack_archive,
    copytree,
    rmtree,
    which
)

from rich.console import Console
from rich.pretty import Pretty
from rich.panel import Panel
from rich.table import Table
import rich.progress
from rich.progress import (
    BarColumn,
    DownloadColumn,
    TimeRemainingColumn,
    Progress,
    TextColumn,
    MofNCompleteColumn
)
from vosk import Model, KaldiRecognizer, SetLogLevel

# Local imports
from model.models import (
    models_small,
    models_large,
    model_languages,
    get_language_features
)

'''
    Globals
'''

__version__ = '0.6.0'
__author__ = 'patrickenfuego'

PathLike = TypeVar('PathLike', Path, str, None)
vosk_url = "https://alphacephei.com/vosk/models"
vosk_link = f"[link={vosk_url}]this link[/link]"
# Default to ffmpeg in PATH
ffmpeg = 'ffmpeg'
ffprobe = 'ffprobe'
con = Console()

'''
    Utility Function Declarations
'''


def path_exists(path: PathLike) -> Path:
    """Utility function to check if a path exists. Used by argparse.

    :param path: File path to verify
    :return: The tested file path if it exists
    """
    if Path(path).exists():
        return Path(path)
    else:
        raise FileNotFoundError(f"The path: <{path}> does not exist")


def verify_language(language: str) -> str:
    """Verifies that the selected language is valid.

    Used to confirm that the language passed via argparse is valid and also supported
    in the list of downloadable model files if the download option is selected.

    :param language: Model language
    :return: The language string if it is a supported language
    """

    found = False
    code = ''

    if language.lower() in model_languages.values():
        code = language.lower()
        found = True
    if not found and language.title() in model_languages.keys():
        code = model_languages[language.title()]
        found = True

    if not language:
        con.print("[bold red]ERROR:[/] Language option appears to be empty")
        sys.exit(1)
    elif not found:
        con.print("[bold red]ERROR:[/] Invalid language or langauge code entered. Possible options:")
        print("\n")
        con.print(Panel(Pretty(model_languages), title="Supported Languages & Codes"))
        print("\n")
        sys.exit(2)
    else:
        return code


def verify_download(language: str, model_type: str) -> str:
    """Verifies that the selected language can be downloaded by the script.

    If the download option is selected, this function verifies that the language
    model and size are supported by the script.

    :param language: Language of the model to download.
    :param model_type: Type of model (small or large).
    :return: String name of the model file to download if supported.
    """

    lang_code = verify_language(language)
    name = ''
    found = False
    other = 'small' if model_type == 'large' else 'large'

    if model_type == 'small':
        for line in models_small:
            if lang_code in line:
                name = line
                break
    elif model_type == 'large':
        for line in models_large:
            if lang_code in line:
                name = line
                break

    # If the specified model wasn't found, check for a different size
    if not name and model_type == 'small':
        for line in models_large:
            if lang_code in line:
                found = True
                break
    elif not name and model_type == 'large':
        for line in models_small:
            if lang_code in line:
                found = True
                break

    if not name and found:
        con.print(
            f"[bold yellow]WARNING:[/] The selected model cannot be downloaded for '{language}' "
            f"in the specified size '{model_type}'. However, a '{other}' model was found. "
            f"You can re-run the script and choose {other}, or attempt to "
            f"download a different model manually from {vosk_link}."
        )
        sys.exit(3)
    elif not name:
        con.print(
            f"[bold red]ERROR:[/] The selected model cannot be downloaded for '{language}' "
            f"in size {model_type}. You can try and download a different model manually "
            f"from {vosk_link}."
        )
        sys.exit(33)

    return name


def parse_config() -> dict:
    """Parses the toml config file.

    :return: A dictionary containing the config file contents.
    """

    if (config := Path.cwd().joinpath('defaults.toml')).exists():
        with open(config, 'r') as fp:
            lines = fp.readlines()
        defaults = {k: v for k, v in [l.strip("\n").replace("'", "").split('=') for l in lines if '#' not in l]}
        return defaults
    else:
        con.print("[bold red]ERROR:[/] Could not locate [blue]defaults.toml[/] file. Did you move or delete it?")
        print("\n")
        return {}


'''
    Function Declarations
'''


def parse_args():
    """
    Parses command line arguments.

    :return: A tuple containing the audiobook path, metadata file path, and user-defined metadata values
    """

    model_name = ''
    download = ''

    parser = argparse.ArgumentParser(
        description='''
        Splits a single monolithic mp3 audiobook file into multiple chapter files using Machine Learning. 
        Metadata and cover art are also extracted from the source file, but any user supplied values
        automatically take precedence when conflicts arise.
        '''
    )
    parser.add_argument('audiobook', nargs='?', metavar='AUDIOBOOK_PATH',
                        type=path_exists, help='Path to audiobook file. Positional argument. Required')
    parser.add_argument('--timecodes_file', '-tc', nargs='?', metavar='TIMECODES_FILE',
                        type=path_exists, dest='timecodes',
                        help='Path to generated srt timecode file (if ran previously in a different directory)')
    parser.add_argument('--language', '-l', dest='lang', nargs='?', default='en-us',
                        metavar='LANGUAGE', type=verify_language,
                        help='Model language to use (en-us provided). See the --download_model parameter.')
    parser.add_argument('--model', '-m', dest='model_type', nargs='?', default='small',
                        type=str, choices=['small', 'large'],
                        help='Model type to use if multiple models are available. Default is small.')
    parser.add_argument('--list_languages', '-ll', action='store_true', help='List supported languages and exit')
    parser.add_argument('--download_model', '-dm', choices=['small', 'large'], dest='download',
                        nargs='?', default=argparse.SUPPRESS,
                        help='Download the model archive specified in the --language parameter')
    parser.add_argument('--cover_art', '-ca', dest='cover_art', nargs='?', default=None,
                        metavar='COVER_ART_PATH', type=path_exists, help='Path to cover art file. Optional')
    parser.add_argument('--author', '-a', dest='author', nargs='?', default=None,
                        metavar='AUTHOR', type=str, help='Author. Optional metadata field')
    parser.add_argument('--description', '-d', dest='description', nargs='?', default=None,
                        metavar='DESCRIPTION', type=str, help='Book description. Optional metadata field')
    parser.add_argument('--title', '-t', dest='title', nargs='?', default=None,
                        metavar='TITLE', type=str, help='Audiobook title. Metadata field')
    parser.add_argument('--narrator', '-n', dest='narrator', nargs='?', default=None,
                        metavar='NARRATOR', type=str, help='Narrator of the audiobook. Saves as the "Composer" ID3 tag')
    parser.add_argument('--genre', '-g', dest='genre', nargs='?', default='Audiobook',
                        metavar='GENRE', type=str,
                        help='Audiobook genre. Separate multiple genres using a semicolon. Multiple genres can be passed as a string delimited by ";". Optional metadata field')
    parser.add_argument('--year', '-y', dest='year', nargs='?', default=None,
                        metavar='YEAR', type=str, help='Audiobook release year. Optional metadata field')
    parser.add_argument('--comment', '-c', dest='comment', nargs='?', default=None,
                        metavar='COMMENT', type=str, help='Audiobook comment. Optional metadata field')
    parser.add_argument('--write_cue_file', '-wc', action='store_true', dest='write_cue',
                        help='Generate a cue file in the audiobook directory for editing chapter markers. Can also be set in defaults.toml. Default disabled')
    parser.add_argument('--cue_path', '-cp', nargs='?', default=None, metavar='CUE_PATH', type=path_exists,
                        help='Path to cue file in non-default location (i.e., not in the audiobook directory) containing chapter timecodes. Can also be set in defaults.toml, which has lesser precedence than this argument')

    args = parser.parse_args()
    config = parse_config()

    if args.list_languages:
        con.print(Panel(Pretty(model_languages), title="Supported Languages & Codes"))
        print("\n")
        con.print(
            "[yellow]NOTE:[/] The languages listed are supported by the "
            "[bold green]--download_model[/]/[bold green]-dm[/] parameter (either small, large, or both). "
            f"You can find additional models at {vosk_link}."
        )
        print("\n")
        sys.exit(0)

    if 'download' in args:
        if args.lang == 'en-us':
            con.print(
                "[bold yellow]WARNING:[/] [bold green]--download_model[/] was used, but a language was not set. "
                "the default value [cyan]'en-us'[/] will be used. If you want a different language, use the "
                "[bold blue]--language[/] option to specify one."
            )

        download = 'small' if args.download not in ['small', 'large'] else args.download
        model_name = verify_download(args.lang, download)


    # Set ID3 metadata fields based on passed args
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
    if args.description:
        meta_fields['description'] = args.description
    if args.narrator:
        meta_fields['narrator'] = args.narrator

    # If the user chooses to download a model, and it was verified
    if download:
        model_type = download
    # If the user passes a value via CLI (overrides config)
    elif 'model_type' in args:
        model_type = args.model_type
    # If the config file contains a value
    elif config['default_model']:
        # Verify valid model size
        if (model_type := config['default_model']) not in ('small', 'large'):
            con.print(
                f"[bold red]ERROR:[/] Invalid model size in config file: '{model_type}'. "
                "Defaulting to 'small'."
            )
            model_type = 'small'
    else:
        model_type = 'small'

    # Check if cue file write is enabled, if custom path was passed, or if cue already exists
    if args.cue_path:
        cue_file = args.cue_path
        con.print(
            f"[bright_magenta]Cue file <<[/] [blue]custom path[/]: Reading cue file from [green]{cue_file}[/]"
        )
    elif config['cue_path']:
        if not Path(config['cue_path']).exists():
            con.print(
                "[bold yellow]WARNING:[/] Cue file in [blue]defaults.toml[/] does not exist and will be skipped"
            )
            cue_file = None
        else:
            cue_file = Path(config['cue_path'])
            con.print(
                f"[bright_magenta]Cue file <<[/] [blue]default.toml[/]: Reading cue file from [green]{cue_file}[/]"
            )
    elif (
            args.write_cue or
            config['generate_cue_file'] == 'True' or
            args.audiobook.with_suffix('.cue').exists()
        ):

        cue_file = args.audiobook.with_suffix('.cue')
        method = ('Writing', 'to') if not cue_file.exists() else ('Reading', 'from')
        con.print(f"[bright_magenta]Cue file[/]: {method[0]} cue file {method[1]} [green]{cue_file}[/]")
    else:
        cue_file = None

    if cue_file:
        print("\n")

    # If the user passes a language via CLI
    if 'lang' in args:
        language = args.lang
    # Check for a value in the config file
    elif 'default_language' in config:
        language = verify_language(config['default_language'])
    else:
        language = 'en-us'

    # Set ffmpeg from system PATH or config file
    global ffmpeg
    if config['ffmpeg_path'] and config['ffmpeg_path'] != 'ffmpeg':
        if Path(config['ffmpeg_path']).exists():
            ffmpeg = Path(config['ffmpeg_path'])
        elif (ffmpeg := which('ffmpeg')) is not None:
            con.print(
                "[yellow]NOTE:[/] ffmpeg path in [blue]defaults.toml[/] does not exist, but "
                f"was found in system PATH: [green]{ffmpeg}[/]"
            )
            ffmpeg = 'ffmpeg'
        else:
            con.print("[bold red]CRITICAL:[/] ffmpeg path in [blue]defaults.toml[/] does not exist")
            sys.exit(1)
    elif (ffmpeg := which('ffmpeg')) is not None:
        ffmpeg = 'ffmpeg'
    else:
        con.print("[bold red]CRITICAL:[/] ffmpeg was not found in config file or system PATH. Aborting")
        sys.exit(1)

    # Set ffprobe from system PATH or config file
    global ffprobe
    if 'ffprobe_path' in config and config['ffprobe_path'] != 'ffprobe':
        if Path(config['ffprobe_path']).exists():
            ffprobe = Path(config['ffprobe_path'])
        elif (ffprobe := which('ffprobe')) is not None:
            con.print(
                "[yellow]NOTE:[/] ffprobe path in [blue]defaults.toml[/] does not exist, but "
                f"was found in system PATH: [green]{ffprobe}[/]"
            )
            ffprobe = 'ffprobe'
        else:
            con.print("[bold red]CRITICAL:[/] ffprobe path in [blue]defaults.toml[/] does not exist")
            sys.exit(1)
    elif (ffprobe := which('ffprobe')) is not None:
        ffprobe = 'ffprobe'
    else:
        con.print("[bold red]CRITICAL:[/] ffprobe was not found in config file or system PATH. Aborting")
        sys.exit(1)

    return args.audiobook, meta_fields, language, model_name, model_type, cue_file


def build_progress(bar_type: str) -> Progress:
    """Builds a progress bar object and returns it.

    :param bar_type: Type of progress bar.
    :return: a Progress object
    """

    text_column = TextColumn(
        "[bold blue]{task.fields[verb]}[/] [bold magenta]{task.fields[noun]}",
        justify="right"
    )

    if bar_type == 'chapterize':
        progress = Progress(
            text_column,
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            MofNCompleteColumn(),
            "•",
            TimeRemainingColumn()
        )
    elif bar_type == 'download':
        progress = Progress(
            text_column,
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            DownloadColumn()
        )
    else:
        raise ValueError("Unknown progress bar type")

    return progress


def print_table(list_dicts: list[dict]) -> None:
    """Formats a list of dictionaries into a table. Currently only used for timecodes.

    :param list_dicts: List of dictionaries to format
    :return: None
    """

    table = Table(
        title='[bold magenta]Parsed Timecodes for Chapters[/]',
        caption='[red]EOF[/] = End of File'
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


def extract_metadata(audiobook_path: PathLike) -> dict:
    """Extracts existing metadata from the input file.

    :param audiobook_path: Path to the input audiobook file
    :return: A dictionary containing metadata values
    """

    metadata_file = audiobook_path.parent.joinpath('metadata.txt')
    # Extract metadata to file using ffmpeg
    subprocess.run([str(ffmpeg), '-y', '-loglevel', 'quiet', '-i', audiobook_path,
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
    metadata_file.unlink()

    return meta_dict


def extract_coverart(audiobook_path: PathLike) -> Path | None:
    """Extract coverart file from audiobook if present.

    :param audiobook_path: Input audiobook file
    :return: Path to cover art jpg file if found, otherwise None
    """

    covert_art = audiobook_path.with_suffix('.jpg')
    subprocess.run([str(ffmpeg), '-y', '-loglevel', 'quiet', '-i',
                    audiobook_path, '-an', '-c:v', 'copy', covert_art])
    if Path(covert_art).exists() and Path(covert_art).stat().st_size > 10:
        con.print("[bold green]SUCCESS![/] Cover art extracted")
        print("\n")
        return covert_art
    else:
        con.print("[bold yellow]WARNING:[/] Failed to extract cover art, or none was found")
        print("\n")
        return None


def convert_to_wav(audiobook_path: PathLike) -> Path:
    """
    Convert input file to lossless wav format. Currently unused, but might be useful for
    legacy versions of vosk.

    :param audiobook_path: Input .mp3 file to convert
    :return: Path to .wav file
    """

    wav_file = audiobook_path.with_suffix('.wav')
    con.print("[magenta]Converting file to wav...[/]")
    result = subprocess.run([
        str(ffmpeg), '-i', audiobook_path, '-ar', '16000', '-ac', '1', wav_file
    ])

    print(f"Subprocess result: {result.returncode}")

    return wav_file


def download_model(name: str) -> None:
    """Downloads the specified language model from vosk (if available).

    :param name: Name of the model found on the vosk website
    :return: None (void)
    """

    try:
        import requests
        from requests.exceptions import ConnectionError as ReqConnectionError
    except ImportError:
        con.print(
            "[bold red]CRITICAL:[/] requests library is not available, and is required for "
            "downloading models. Run [bold green]pip install requests[/] and re-run the script."
        )
        sys.exit(18)

    full = f'{vosk_url}/{name}.zip'
    out_base = Path('__file__').parent.absolute() / 'model'
    out_zip = out_base / f'{name}.zip'
    out_dir = out_base / name

    if out_dir.exists():
        con.print("[bold yellow]it appears you already have the model downloaded. Sweet![/]")
        return

    progress = build_progress(bar_type='download')
    with requests.get(full, stream=True, allow_redirects=True) as req:
        if req.status_code != 200:
            raise ReqConnectionError(
                f"Failed to download the model file: {full}. HTTP Response: {req.status_code}"
            )

        size = int(req.headers.get('Content-Length'))
        chunk_size = 50 if 'small' in name else 300
        task = progress.add_task("", size=size, noun=name, verb='Downloading')
        progress.update(task, total=size)
        with open(out_zip, 'wb') as dest_file:
            with progress:
                for chunk in req.iter_content(chunk_size=chunk_size):
                    dest_file.write(chunk)
                    progress.update(task, advance=len(chunk))

    try:
        unpack_archive(out_zip, out_dir)
        if out_dir.exists():
            con.print("[bold green]SUCCESS![/] Model downloaded and extracted successfully")
            print("\n")
            out_zip.unlink()
            child_dir = out_dir / name
            # If it extracts inside another directory, copy up and remove extra
            if child_dir.exists():
                child_dir.rename(Path(f"{child_dir}-new"))
                child_dir = copytree(Path(f"{child_dir}-new"), out_base / f"{name}-new")
                rmtree(out_dir)
                child_dir.rename(Path(out_dir))
        elif out_zip.exists() and not out_dir.exists():
            con.print(
                "[bold red]ERROR:[/] Model archive downloaded successfully, but failed to extract. "
                "Manually extract the archive into the model directory and re-run the script."
            )
            sys.exit(4)
        else:
            con.print(
                "[bold red]CRITICAL:[/] Model archive failed to download. The selected model "
                f"might not be supported by the script, or is unavailable. Follow {vosk_link} "
                "to download a model manually.\n"
            )
            sys.exit(5)
    except Exception as e:
        con.print(f"[bold red]CRITICAL:[/] Failed to unpack or rename the model: [red]{e}[/red]")
        sys.exit(29)


def convert_time(time: str) -> str:
    """Convert timecodes for chapter markings.

    Helper function to subtract 1 second from each start time which is used as the
    end time for the previous chapter segment. If the update rolls over to a new
    digit in the hour, minute, or second segments, adjust all necessary segments.

    :param time: Timecode in Sexagesimal format
    :return: Sexagesimal formatted time marker
    """

    try:
        parts = time.split(':')
        last, milliseconds = str(parts[-1]).split('.')

        pattern = re.compile(r'0\d')
        # Check for leading 0 and adjust time
        if pattern.match(last):
            # Adjust the hours position
            if parts[1] == '00' and last == '00':
                if pattern.match(parts[0]):
                    first = f'0{str(int(parts[0]) - 1)}'
                else:
                    first = str(int(parts[0]) - 1)
                parts = [first, '59', '59']
            # Adjust the minutes position
            elif last == '00':
                if pattern.match(parts[1]):
                    mid = f'0{str(int(parts[1]) - 1)}'
                else:
                    mid = str(int(parts[1]) - 1)
                parts = [parts[0], mid, '59']
            # Adjust the seconds position
            else:
                parts[-1] = f'0{str(int(last) - 1)}'
        else:
            parts[-1] = str(int(last) - 1)
    except Exception as e:
        con.print(f"[bold red]CRITICAL:[/] Could not covert end chapter marker for {time}: [red]{e}[/red]")
        sys.exit(6)

    return f"{':'.join(parts)}.{milliseconds}"


def split_file(audiobook_path: PathLike,
               timecodes: list[dict],
               metadata: dict,
               cover_art: Optional[str]) -> None:

    """Splits a single .mp3 file into chapterized segments.

    :param audiobook_path: Path to original .mp3 audiobook
    :param timecodes: List of start/end markers for each chapter
    :param metadata: File metadata passed via CLI and/or parsed from audiobook file
    :param cover_art: Optional path to cover art
    :return: An integer status code
    """

    file_stem = audiobook_path.stem
    # Set the log path for output. If it exists, generate new filename
    log_path = audiobook_path.parent.joinpath('ffmpeg_log.txt')
    if log_path.exists():
        with open(log_path, 'a+') as fp:
            fp.writelines([
                '********************************************************\n',
                'NEW LOG START\n'
                '********************************************************\n\n'
            ])
    command = [ffmpeg, '-y', '-hide_banner', '-loglevel', 'info', '-i', f'{str(audiobook_path)}']
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
    if 'description' in metadata:
        command.extend(['-metadata', f"description={metadata['description']}"])
    if 'narrator' in metadata:
        command.extend(['-metadata', f"composer={metadata['narrator']}"])

    progress = build_progress(bar_type='chapterize')
    with progress:
        task = progress.add_task('', total=len(timecodes), verb='Processing', noun='Audiobook...')
        for counter, times in enumerate(timecodes, start=1):
            counter = f'0{counter}' if counter < 10 else counter
            command_copy = command.copy()
            if 'start' in times:
                command_copy[5:5] = ['-ss', times['start']]
            if 'end' in times:
                command_copy[7:7] = ['-to', times['end']]
            if 'chapter_type' in times:
                file_path = audiobook_path.parent.joinpath(f"{file_stem} {counter} - {times['chapter_type']}.mp3")
            else:
                file_path = audiobook_path.parent.joinpath(f"{file_stem} - {counter}.mp3")

            track_num = ['-metadata', f"track={counter}/{len(timecodes)}"]
            command_copy.extend([*stream, *track_num, '-metadata', f"title={times['chapter_type']}",
                                 f'{file_path}'])

            try:
                with open(log_path, 'a+') as fp:
                    fp.write('----------------------------------------------------\n\n')
                    subprocess.run(command_copy, stdout=fp, stderr=fp)
            except Exception as e:
                con.print(
                    f"[bold red]ERROR:[/] An exception occurred writing logs to file: "
                    f"[red]{e}[/red]\nOutputting to stdout..."
                )
                subprocess.run(command_copy, stdout=subprocess.STDOUT)

            # Reset the list but keep reference
            command_copy = None

            progress.update(task, advance=1)


def generate_timecodes(audiobook_path: PathLike, language: str, model_type: str) -> Path:
    """Generate chapter timecodes using vosk Machine Learning API.

    This function searches for the specified model/language within the project's 'models' directory and
    uses it to perform a speech-to-text conversion on the audiobook, which is then saved in a subrip (srt) file.

    If more than 1 model is present, the script will attempt to guess which one to use based on input.

    :param audiobook_path: Path to input audiobook file
    :param language: Language used by the parser
    :param model_type: The type of model (large or small)
    :return: Path to timecode file
    """

    sample_rate = 16000
    model_root = Path(r"model")

    # If the timecode file already exists, exit early and return path
    out_file = audiobook_path.with_suffix('.srt')
    if out_file.exists() and out_file.stat().st_size > 10:
        con.print("[bold green]SUCCESS![/] An existing srt timecode file was found")
        print("\n")

        return out_file

    try:
        if model_path := [d for d in model_root.iterdir() if d.is_dir() and language in d.stem]:
            print("\n")
            con.print(f":white_heavy_check_mark: Local ML model found. Language: '{language}'\n")
            # If there is more than 1 model, infer the proper one from the name
            if len(model_path) > 1:
                con.print(
                    f"[yellow]Multiple models for '{language}' found. "
                    f"Attempting to use the {model_type} model[/yellow]"
                )
                if model_type == 'small':
                    model_path = [d for d in model_path if 'small' in d.stem][0]
                else:
                    model_path = [d for d in model_path if 'small' not in d.stem][0]
            else:
                model_path = model_path[0]
    except IndexError:
        con.print(
            "[bold yellow]WARNING:[/] Local ML model was not found (did you delete it?) "
            "or multiple models were found and the proper one couldn't be inferred.\n"
            "The script will attempt to download an online model, which "
            "isn't always reliable. Fair warning."
        )
        model_path = None

    SetLogLevel(-1)
    model = Model(lang=language, model_path=str(model_path))
    rec = KaldiRecognizer(model, sample_rate)
    rec.SetWords(True)

    try:
        # Convert the file to wav (if needed), and stream output to file
        # Start by getting the length (in seconds) of the mp3 file and converting that to wav file
        # size in bytes, for the progress bar.
        length = subprocess.run([ffprobe, '-show_entries',
                                 'format=duration', '-i', audiobook_path],
                                text=True, capture_output=True).stdout
        (_, length, _) = length.splitlines()
        (_, length) = length.split('=')
        # Length of .wav file is 2 bytes per sample, 16K samples per second.
        length=int(float(length) * 16000 * 2)

        with rich.progress.wrap_file(subprocess.Popen([str(ffmpeg), "-loglevel", "quiet", "-i",
                               audiobook_path,
                               "-ar", str(sample_rate), "-ac", "1", "-f", "s16le", "-"],
                              stdout=subprocess.PIPE).stdout, length) as stream:
            with open(out_file, 'w+') as fp:
                fp.writelines(rec.SrtResult(stream))

        con.print("[bold green]SUCCESS![/] Timecode file created\n")
    except Exception as e:
        con.print(f"[bold red]ERROR:[/] Failed to generate timecode file with vosk: [red]{e}[/red]\n")
        sys.exit(7)

    return Path(out_file)


def parse_timecodes(srt_content: list, language: str = 'en-us') -> list[dict]:
    """Parse the contents of the srt timecode file.

    Parses the output from `generate_timecodes` and generates start/end times, as well as chapter
    type (prologue, epilogue, etc.) if available.

    :param srt_content: List of timecodes extracted from the output of vosk
    :param language: Selected language. Used for importing excluded phrases
    :return: A list of dictionaries containing start, end, and chapter type data
    """

    # Get lang specific markers and excluded phrases
    excluded_phrases, markers = get_language_features(language)
    # If language features are None, they haven't been defined
    if not excluded_phrases or not markers:
        from model.models import get_lang_from_code
        lang_str = get_lang_from_code(language)
        con.print(
            f"[bold red]CRITICAL:[/] Language features for [bright_blue]{lang_str.title()}[/] are not "
            "yet configured. If you speak this language, consider contributing to this project."
        )
        sys.exit(13)

    timecodes = []
    counter = 1

    for i, line in enumerate(srt_content):
        if (
                # Not the end of the list
                i != (len(srt_content) - 1) and
                # Doesn't contain an excluded phrase
                not any(x in srt_content[i+1] for x in excluded_phrases) and
                # Contains a marker substring
                any(m in srt_content[i+1] for m in markers)
        ):
            if start_regexp := re.search(r'\d\d:\d\d:\d\d,\d+(?=\s-)', line, flags=0):
                start = start_regexp.group(0).replace(',', '.')

                # Prologue
                if markers[0] in srt_content[i+1]:
                    chapter_type = markers[0].title()
                # Chapter X
                elif markers[1] in srt_content[i+1]:
                    # Add leading zero for better sorting if < 10
                    chapter_count = f'0{counter}' if counter < 10 else f'{counter}'
                    chapter_type = f'{markers[1].title()} {chapter_count}'
                    counter += 1
                # Epilogue
                elif markers[2] in srt_content[i+1]:
                    chapter_type = markers[2].title()
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
        sys.exit(8)


def verify_count(audiobook_path: PathLike, timecodes: list[dict]) -> None:
    """Verify that the expected number of files were generated.

    Compares the number of files split from the audiobook to ensure it matches the length of the generated
    timecodes.

    :param audiobook_path: Path to audiobook file
    :param timecodes: List of dictionaries containing chapter type, start, and end times
    :return: None (void)
    """

    file_count = sum(1 for x in audiobook_path.parent.glob('*.mp3') if x.stem != audiobook_path.stem)
    expected = len(timecodes)
    if file_count >= expected:
        con.print(f"[bold green]SUCCESS![/] Audiobook split into {file_count} files\n")
    else:
        con.print(
            f"[bold yellow]WARNING:[/] {file_count} files were generated "
            f"which is less than the expected {expected}\n"
        )


def write_cue_file(timecodes: list[dict], cue_path: PathLike) -> bool:
    """Write audiobook timecodes to a cue file.

    Cue files can be created using the `-write_cue_file`/`-wc` argument. This provides the user with an
    easy interface for adding, modifying, or deleting chapter names, start, and end timecodes, which is
    useful when the ML speech-to-text misses or inaccurately labels a section.

    :param timecodes: Parsed timecodes to be written to the cue file
    :param cue_path: Path to cue file
    :return: Boolean success/failure flag
    """

    try:
        with open(cue_path, 'x') as fp:
            fp.write(f'FILE "{cue_path.stem}.mp3" MP3\n')
            for i, time in enumerate(timecodes, start=1):
                fp.writelines([
                    f"TRACK {i} AUDIO\n",
                    f'  TITLE\t"{time["chapter_type"]}"\n',
                    f"  START\t{time['start']}\n"
                ])
                if i != len(timecodes):
                    fp.write(f"  END\t\t{time['end']}\n")
    except OSError as e:
        con.print(f"[bold red]ERROR:[/] Failed to write cue file: [red]{e}[/]")
        # Delete cue file to prevent parsing error if partially written
        if cue_path.exists():
            cue_path.unlink()
        return False

    return True

def read_cue_file(cue_path: PathLike) -> list[dict] | None:
    """Read audiobook timecodes from a cue file.

    Cue files can be created using the `-write_cue_file` argument. After creation, the cue file is
    used exclusively for reading timecodes unless an error occurs or the file is moved/renamed/deleted.

    :param cue_path: Path to cue file
    :return: List of timecodes in dictionary form
    """

    timecodes = []
    time_dict = {}

    with open(cue_path, 'r') as fp:
        content = fp.readlines()
    content = [l.strip('\n') for l in content]

    for i, line in enumerate(content[1:]):
        try:
            if 'TITLE' in line:
                time_dict['chapter_type'] = re.search(r'TITLE\t"(.*)"', line)[1]
            if 'START' in line:
                time_dict['start'] = re.search(r'START\t(.+)', line)[1]
            if 'END' in line and i != len(content) - 1:
                time_dict['end'] = re.search(r'END\t+(.+)', line)[1]
        except (ValueError, IndexError) as e:
            con.print(f"[bold red]ERROR:[/] Failed to match line: [red]{e}[/]. Returning...")
            return None

        if 'TRACK' in content[i+1] and time_dict:
            timecodes.append(time_dict)
            time_dict = {}
        elif line == content[-1] and time_dict:
            timecodes.append(time_dict)

    if timecodes:
        return timecodes
    else:
        con.print(
            f"[bold red]ERROR:[/] Timecodes read from cue file cannot be empty. "
            "Timecodes will be parsed normally until the error is corrected."
        )
        return None


def main():
    """
    Main driver function.

    :return: None
    """

    print("\n\n")
    con.rule("[cyan]Starting script[/cyan]")
    print("\n")
    con.print("[magenta]Preparing chapterfying magic[/magenta] :zap:...")
    print("\n")

    # Check python version
    if not sys.version_info >= (3, 10, 0):
        con.print("[bold red]CRITICAL:[/] Python version must be 3.10.0 or greater to run this script\n")
        sys.exit(20)

    # Destructure tuple
    audiobook_file, in_metadata, lang, model_name, model_type, cue_file = parse_args()
    if not str(audiobook_file).endswith('.mp3'):
        con.print("[bold red]ERROR:[/] The script only works with .mp3 files (for now)")
        sys.exit(9)

    # Extract metadata from input file
    con.rule("[cyan]Extracting metadata[/cyan]")
    print("\n")
    parsed_metadata = extract_metadata(audiobook_file)
    # Combine the dicts, overwriting existing keys with user values if passed
    if parsed_metadata and in_metadata:
        con.print("[magenta]Merging extracted and user metadata[/magenta]...")
        print("\n")
        parsed_metadata |= in_metadata
    # This should never hit, as genre has a default value in argparse
    elif not in_metadata and not parsed_metadata:
        con.print("[bold yellow]WARNING:[/] No metadata to append. What a shame")
        print("\n")
    # No metadata was found in file, using only argparse defaults
    elif in_metadata and not parsed_metadata:
        parsed_metadata = in_metadata
        print("\n")
    con.print(Panel(Pretty(parsed_metadata), title="ID3 Metadata"))
    print("\n")

    # Search for existing cover art
    con.rule("[cyan]Discovering Cover Art[/cyan]")
    print("\n")
    if not parsed_metadata['cover_art']:
        con.print("[magenta]Perusing for cover art in source[/magenta]...")
        cover_art = extract_coverart(audiobook_file)
    else:
        if parsed_metadata['cover_art'].exists():
            con.print("[bold green]SUCCESS![/] Cover art is...covered!")
            print("\n")
            cover_art = parsed_metadata['cover_art']
        else:
            con.print("[bold yellow]WARNING:[/] Cover art path does not exist")
            cover_art = None

    # Download model if option selected
    if model_name and lang:
        con.rule(f"[cyan]Downloading '{lang} ({model_type})' Model[/cyan]")
        print("\n")
        con.print("[magenta]Preparing download...[/magenta]")
        print("\n")
        download_model(model_name)

    # Generate timecodes from mp3 file
    con.rule("[cyan]Generating Timecodes[/cyan]")
    print("\n")
    if model_type == 'small':
        message = "[magenta]Sit tight, this might take a while[/magenta]..."
    else:
        message = "[magenta]Sit tight, this might take a [u]long[/u] while[/magenta]..."
    with con.status(message, spinner='pong'):
        timecodes_file = generate_timecodes(audiobook_file, lang, model_type)

    # If cue file exists, read timecodes from file
    if cue_file and cue_file.exists():
        con.rule("[cyan]Reading Cue File[/cyan]")
        print("\n")

        if (timecodes := read_cue_file(cue_file)) is not None:
            con.print("[bold green]SUCCESS![/] Timecodes parsed from cue file")
    else:
        timecodes = None

    # If timecodes not parsed from cue file, parse from srt
    if not timecodes:
        # Open file and parse timecodes
        with open(timecodes_file, 'r') as fp:
            file_lines = fp.readlines()
        con.rule("[cyan]Parsing Timecodes[/cyan]")
        print("\n")

        timecodes = parse_timecodes(file_lines, lang)
        con.print("[bold green]SUCCESS![/] Timecodes parsed")

    # Print timecodes table
    print("\n")
    print_table(timecodes)
    print("\n")

    # Generate cue file if selected and one doesn't already exist
    con.rule("[cyan]Writing Cue File[/cyan]")
    print("\n")
    if cue_file and not cue_file.exists():
        if (success := write_cue_file(timecodes, cue_file)) is True:
            con.print("[bold green]SUCCESS![/] Cue file created")
    elif cue_file and cue_file.exists():
        con.print(
            "[yellow]NOTE:[/] An existing cue file was found. Move, delete, or rename it to generate a new one"
        )
    else:
        con.print("[yellow]NOTE:[/] Nothing to write")
    print("\n")

    # Split the file
    con.rule("[cyan]Chapterizing File[/cyan]")
    print("\n")
    split_file(audiobook_file, timecodes, parsed_metadata, cover_art)

    # Count the generated files and compare to timecode dict to ensure they match
    verify_count(audiobook_file, timecodes)


if __name__ == '__main__':
    main()
