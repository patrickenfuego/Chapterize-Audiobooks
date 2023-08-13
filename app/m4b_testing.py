from datetime import datetime, time
import subprocess
from pathlib import Path
import re
from pprint import pprint
from typing import TypeVar

PathLike = TypeVar('PathLike', Path, str, None)

def time_to_milliseconds(time_str: str):
    """Convert a time formatted string in the form `HH:MM:SS.MS` to milliseconds.

    :param time_str: The time formatted string to convert.
    :returns: The time in milliseconds
    """

    # Convert the time string to a time object
    time_obj = datetime.strptime(time_str, '%H:%M:%S.%f').time()

    # Convert the time object to milliseconds
    total_ms = ((time_obj.hour * 60 + time_obj.minute) * 60 + time_obj.second) * 1000 + time_obj.microsecond // 1000

    return total_ms


def read_cue_file(cue_path: Path) -> list[dict] | None:
    """Read audiobook timecodes from a cue file.

    Cue files can be created using the `-write_cue_file` argument. After creation, the cue file is
    used exclusively for reading timecodes unless an error occurs or the file is moved/renamed/deleted.

    :param cue_path: Path to cue file
    :return: List of timecodes in dictionary form
    """

    timecodes = []
    time_dict = {}

    with open(cue_path, 'r') as fp:
        content = [l.strip('\n') for l in fp.readlines()]

    for i, line in enumerate(content[1:]):
        try:
            if 'TITLE' in line:
                time_dict['chapter_type'] = re.search(r'TITLE\t"(.*)"', line)[1]
            if 'START' in line:
                time_dict['start'] = re.search(r'START\t(.+)', line)[1]
            if 'END' in line and i != len(content) - 1:
                time_dict['end'] = re.search(r'END\t+(.+)', line)[1]
        except (ValueError, IndexError) as e:
            print(f"[bold red]ERROR:[/] Failed to match line: [red]{e}[/]. Returning...")
            return None

        if 'TRACK' in content[i+1] and time_dict:
            timecodes.append(time_dict)
            time_dict = {}
        elif line == content[-1] and time_dict:
            timecodes.append(time_dict)

    if timecodes:
        return timecodes
    else:
        print(
            f"[bold red]ERROR:[/] Timecodes read from cue file cannot be empty. "
            "Timecodes will be parsed normally until the error is corrected."
        )
        return None


def get_duration(file):
    """Get the duration of an audio file using ffprobe.

    :param file: File to process
    :return: None if no output is produced, otherwise the duration in HH:MM:SS.MS format
    """

    args = ['ffprobe', '-i', file, '-show_entries', 'format=duration', '-sexagesimal',
            '-v', 'quiet', '-of', 'csv=p=0']
    cmd = subprocess.run(args, capture_output=True, universal_newlines=True)
    print("Result:\n", cmd)

    if cmd.stdout:
        return cmd.stdout.strip('\n')
    else:
        return None



def write_metadata_file(file: Path, timecodes: list[dict], metadata: dict):
    with open(file, 'w', encoding='utf8') as fp:
        fp.write(';FFMETADATA1\n')
        # Handle special case
        if 'album_artist' in metadata:
            if 'composer' in metadata:
                fp.write(f"album_artist={metadata['album_artist']}, {metadata['composer']}\n")
            else:
                fp.write(f"album_artist={metadata['album_artist']}\n")
        for key, value in metadata.items():
            if key == 'album_artist':
                continue
            fp.write(f"{key}={value}\n")

        for i, time in enumerate(timecodes):
            if i == len(timecodes) - 1:
                pass
            else:
                fp.writelines([
                '[CHAPTER]\n',
                'TIMEBASE=1/1000\n',
                f"START={time['start']}\n",
                f"END={time['end']}\n",
                f"title={time['chapter_type']}\n"
            ])

def append_metadata(meta_dict: dict, cover_art: str):
    meta_args = []

    if cover_art:
        cover_args = ['-i', cover_art]



def convert_m4b(path: Path,
                metadata_file: Path,
                title: str = None,
                cover_art: str | Path = None,
                bitrate: int = 64):

    # Set title and file name. If no title passed, use default
    if not title:
        title = 'output'
        print("[bold yellow]WARNING:[/] No title was specified. 'output.m4b' will be used")
    out = path / f'{title}.m4b'

    if cover_art:
        cargs1 = ['-i', cover_art]
        cargs2 = ['-map', '0:v', '-c:v', 'copy']
    else:
        cargs1 = cargs2 = []

    # Check for fdkaac
    cmd = subprocess.run(['ffmpeg'], capture_output=True, universal_newlines=True)
    codec = 'libfdk_aac' if '--enable-libfdk-aac' in cmd.stderr else 'aac'

    base = ['ffmpeg', '-hide_banner', '-i', metadata_file]
    # If mp3 is already split
    if path.is_dir():
        files = [str(f) for f in path.glob('*.mp3')]
        concat = f"concat:{'|'.join(files)}"
        args = [*base, '-i', concat, '-map_metadata', '1', '-c:a', codec,
                '-map', '0:a', *cargs2, '-b:a', f'{bitrate}k', '-f', 'mp4', out]
    # Single file
    else:
        args = [*base, '-i', path, *cargs1, '-map_metadata', '1', '-c:a', codec,
                '-map', '0:a', *cargs2, '-b:a', f'{bitrate}k', '-f', 'mp4', out]

    cmd = subprocess.run(args, capture_output=True)
    pprint(cmd)



if __name__ == '__main__':
    cue_p = Path(r"M:\Torrent Downloads\Lee Child [Jack Reacher 07] Persuader\Lee Child [Jack Reacher 07] Persuader.cue")
    abook = Path(r"M:\Torrent Downloads\Lee Child [Jack Reacher 07] Persuader\Lee Child [Jack Reacher 07] Persuader.mp3")
    chap_file = Path(r"M:\Torrent Downloads\Lee Child [Jack Reacher 07] Persuader\chapters.txt")
    duration = get_duration(abook)
    print(duration)

    # times = read_cue_file(cue_p)
    # print(times)
    #
    # times_ms = []
    #
    # for i, c in enumerate(times):
    #     if i == 0:
    #         new_dict = {'start': 0}
    #     else:
    #         new_dict = {'start': time_to_milliseconds(c['start'])}
    #
    #     if i == len(times) - 1:
    #         new_dict['end'] = time_to_milliseconds(get_duration(abook))
    #     else:
    #         new_dict['end'] = time_to_milliseconds(c['end'])
    #
    #     new_dict['chapter_type'] = c['chapter_type']
    #
    #     times_ms.append(new_dict)
    #
    # write_chapters(chap_file, times_ms)
    # test_path = Path(r"M:\Torrent Downloads\Lee Child [Jack Reacher 07] Persuader\join")
    # convert_m4b(test_path, chap_file)
    cmd = subprocess.run(['ffmpeg'], capture_output=True, universal_newlines=True)
    print(cmd.stderr)
    print(type(cmd.stderr))
    print('--enable-libfdk-aac' in cmd.stderr)



