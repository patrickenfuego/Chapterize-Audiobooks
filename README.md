# Chapterize-Audiobooks

Split a single, monolithic mp3 audiobook file into chapters using Machine Learning and ffmpeg.

## About

This is a simple command line utility that will chapterize your audiobooks for you. No longer will you have to
dissect a waveform to look for chapter breaks, or deal with all the annoyances that come with a single audiobook
file.

The script utilizes the `vosk-api` machine learning library which performs a speech-to-text conversion on the
audiobook file, generating timestamps throughout which are stored as a srt (subrip) file. The file is then parsed,
searching for phrases like "prologue", "chapter", and "epilogue", which are used as chapter markers in the generated
chapter files.

The script will also parse metadata from the source file along with the cover art (if present) and copy it into each
chapter file automatically. There are CLI parameters you can use to pass your own metadata, which always take
precedence over the fields extracted from the file (if there is a conflict).

This script is still in alpha, and thus there are bound to be some issues; I've noticed a few words
and phrases that have falsely generated chapter markers, which I'm currently compiling into an *ignore* list as I see
them. With that said, it's been remarkably accurate so far.

## Dependencies

- ffmpeg
- python 3.9+
  - Packages:
    - rich
    - vosk

To install python dependencies:

```shell
pip install -r requirements.txt
```

## Usage

```ruby
usage: chapterize_ab.py [-h] [--timecodes_file [TIMECODES_FILE]] [--cover_art [COVER_ART_PATH]]
                        [--author [AUTHOR]] [--title [TITLE]] [--genre [GENRE]] [--year [YEAR]]
                        [--comment [COMMENT]] [AUDIOBOOK_PATH]

positional arguments:

  AUDIOBOOK_PATH        Path to audiobook file. Required.
  
options:

  -h, --help            show this help message and exit
  --timecodes_file [TIMECODES_FILE], -tc [TIMECODES_FILE]
                        path to generated srt timecode file (if ran previously in a different directory).
  --cover_art [COVER_ART_PATH], -ca [COVER_ART_PATH]
                        path to cover art file. Optional.
  --author [AUTHOR], -a [AUTHOR]
                        audiobook author. Optional metadata field.
  --title [TITLE], -t [TITLE]
                        audiobook title. Optional metadata field.
  --genre [GENRE], -g [GENRE]
                        audiobook genre. Optional metadata field.
  --year [YEAR], -y [YEAR]
                        audiobook release year. Optional metadata field.
  --comment [COMMENT], -c [COMMENT]
                        audiobook comment. Optional metadata field.

```

