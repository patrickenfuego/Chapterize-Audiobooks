<a href="https://github.com/patrickenfuego/Chapterize-Audiobooks"><img alt="GitHub release (latest SemVer)" src="https://img.shields.io/github/v/release/patrickenfuego/Chapterize-Audiobooks"><a/>
<a href="https://github.com/patrickenfuego/Chapterize-Audiobooks"><img alt="python" src="https://img.shields.io/badge/python-v3.10%2B-blue"><a/>
<a href="https://github.com/patrickenfuego/Chapterize-Audiobooks"><img src="https://img.shields.io/badge/platform-win | linux | mac-eeeeee"><a/>

# Chapterize-Audiobooks

Split a single, monolithic mp3 audiobook file into chapters using Machine Learning and ffmpeg.

![demo](https://user-images.githubusercontent.com/47511320/196572033-80cfe70c-eb57-4789-a7be-fcb2a03f18c5.gif)

---

## Table of Contents

- [Chapterize-Audiobooks](#chapterize-audiobooks)
  - [Table of Contents](#table-of-contents)
  - [About](#about)
  - [Dependencies](#dependencies)
    - [ffmpeg](#ffmpeg)
  - [Supported Languages and Models](#supported-languages-and-models)
  - [Usage](#usage)
    - [Examples](#examples)
  - [Improvement](#improvement)
  - [Known Issues](#known-issues)
    - [Access Denied Error on Windows](#access-denied-error-on-windows)

---

## About

This is a simple command line utility that will chapterize your mp3 audiobooks for you. No longer will you have to dissect a waveform to look for chapter breaks, or deal with all the annoyances that come with a single audiobook file. You can use this as an intermediary step for creating m4b files, or keep the files the way they are.

The script utilizes the `vosk-api` machine learning library which performs a speech-to-text conversion on the audiobook file, generating timestamps throughout which are stored in a srt (subrip) file. The file is then parsed, searching for phrases like "prologue", "chapter", and "epilogue", which are used as separators for the generated chapter files.

The script will also parse metadata from the source file along with the cover art (if present) and copy it into each chapter file automatically. There are CLI parameters you can use to pass your own ID3-compliant metadata properties, too, which always take precedence over the fields extracted from the file (if there is a conflict). Otherwise, the tags will be combined.

---

## Dependencies

- [ffmpeg](https://ffmpeg.org/)
- [python](https://www.python.org/downloads/) 3.10+
  - Packages:
    - [rich](https://github.com/Textualize/rich)
    - [vosk](https://github.com/alphacep/vosk-api)
    - [requests](https://requests.readthedocs.io/en/latest/) (if you want to download models)

To install python dependencies, open a command shell and type the following:

> NOTE: If you're on Linux, you might need to use `pip3` instead

```bash
# Using the requirements file (recommended)
pip install -r requirements.txt
# Manually installing packages
pip install vosk rich requests
```

### ffmpeg

It is recommended that you add ffmpeg to your system PATH so you don't have to run the script from the same directory. How you do this depends on your Operating System; consult your OS documentation (if you aren't familiar with the process, it's super easy. Just Google it).

Here is a quick example for Windows using PowerShell (it can be done via GUI, too):

```powershell
# Whatever the path is to your ffmpeg install
$ffmpeg = 'C:\Users\SomeUser\Software\ffmpeg.exe'
$newPath = $env:PATH + ";$ffmpeg"
[Environment]::SetEnvironmentVariable('PATH', $newPath, 'User')
```

Here is a quick example using bash:

```bash
# Set this equal to wherever ffmpeg is
ffmpeg="/home/someuser/software/ffmpeg"
# If you're using zsh, replace with .zshrc
echo "export PATH=${ffmpeg}:${PATH}" >> ~/.bashrc
```

If you don't want to deal with all that, you can add the path of ffmpeg to the `defaults.toml` file included with the repository - copy and paste the full path and set it equal to the `ffmpeg_path` option **using single quotes** `''`:

```toml
# Specfying the path to ffmpeg manually
ffmpeg_path='C:\Users\SomeUser\Software\ffmpeg.exe'
# If ffmpeg is added to PATH, leave the file like this
ffmpeg_path='ffmpeg'
```

---

## Supported Languages and Models

> **NOTE**: You can set a default language and model size in the defaults.toml file included with the repository

The `vosk-api` provides models in several languages. By default, only the small 'en-us' model is provided with this repository, but you can download additional models in several languages using the script's `--download_model`/`-dm` parameter, which accepts arguments `small` and `large` (if nothing is passed, it defaults to `small`); if the model isn't English, you must also specify a language using `--language`/`-l` parameter. See [Usage](#usage) for more info.

Not all models are supported, but you can download additional models manually from [the vosk website](https://alphacephei.com/vosk/models) (and other sources listed on the site). Simply replace the existing model inside the `/model` directory with the one you wish to use.

The following is a list of models which can be downloaded using the `--download_model` parameter of the script:

> You can use either the **Language** or **Code** fields to specify a model

| **Language**    | **Code** | **Small** | **Large** |
|-----------------|----------|-----------|-----------|
| English (US)    | en-us    | ✓         | ✓         |
| English (India) | en-in    | ✓         | ✓         |
| Chinese         | cn       | ✓         | ✓         |
| Russian         | ru       | ✓         | ✓         |
| French          | fr       | ✓         | ✓         |
| German          | de       | ✓         | ✓         |
| Spanish         | es       | ✓         | ✓         |
| Portuguese      | pt       | ✓         | ✓         |
| Greek           | el       | ✕         | ✓         |
| Turkish         | tr       | ✕         | ✓         |
| Vietnamese      | vn       | ✓         | ✕         |
| Italian         | it       | ✓         | ✓         |
| Dutch           | nl       | ✓         | ✕         |
| Catalan         | ca       | ✓         | ✕         |
| Arabic          | ar       | ✕         | ✓         |
| Farsi           | fa       | ✓         | ✓         |
| Filipino        | tl-ph    | ✕         | ✓         |
| Kazakh          | kz       | ✓         | ✓         |
| Japanese        | ja       | ✓         | ✓         |
| Ukrainian       | uk       | ✓         | ✓         |
| Esperanto       | eo       | ✓         | ✕         |
| Hindi           | hi       | ✓         | ✓         |
| Czech           | cs       | ✓         | ✕         |
| Polish          | pl       | ✓         | ✕         |

The model used for speech-to-text the conversion is fairly dependent on the quality of the audio. The model included in this repo is meant for small distributions on mobile systems, as it is the only one that will fit in a GitHub repository. If you aren't getting good results, you might want to consider using a larger model (if one is available).

---

## Usage

```ruby
usage: chapterize_ab.py [-h] or [--help]

usage: chapterize_ab.py [-ll] or [--list_languages]

usage: chapterize_ab.py [AUDIOBOOK_PATH] [--timecodes_file [TIMECODES_FILE]] [--language [LANGUAGE]]
                        [--download_model [{small,large}]] [--narrator [NARRATOR]] [--comment [COMMENT]]
                        [--model [{small,large}]] [--cover_art [COVER_ART_PATH]] [--author [AUTHOR]]
                        [--year [YEAR]] [--title [TITLE]] [--genre [GENRE]]

positional arguments:

  AUDIOBOOK_PATH          path to audiobook mp3 file. required.
  
optional argument flags:

  -h, --help              show this help message and exit.
  -ll, --list_languages   list supported languages and exit.
  
optional arguments:
  
  --timecodes_file, -tc [TIMECODES_FILE]
  DESCRIPTION:            optional path to an existing srt timecode file in a different directory.
                        
  --language, -l [LANGUAGE]
  DESCRIPTION:            model language to use. requires a supported model ('en-us' is provided).
  
  --model, -m [{small,large}]
  DESCRIPTION:            model type to use if multiple models are available. default is small.
  
  --download_model, -dm [{small,large}]
  DESCRIPTION:            download the model archive specified in the --language parameter     
                        
  --cover_art, -ca [COVER_ART_PATH]
  DESCRIPTION:            path to cover art file. Optional.
                        
  --author, -a [AUTHOR]
  DESCRIPTION:            audiobook author. Optional metadata field.

   --narrator, -n [NARRATOR]
  DESCRIPTION:            audiobook narrator (should be compatible with most players). Optional metadata field.
                        
  --title, -t [TITLE]
  DESCRIPTION:            audiobook title. Optional metadata field.
                        
  --genre, -g [GENRE]
  DESCRIPTION:            audiobook genre. Optional metadata field.
                        
  --year, -y [YEAR]
  DESCRIPTION:            audiobook release year. Optional metadata field.
                        
  --comment, -c [COMMENT]
  DESCRIPTION:            audiobook comment. Optional metadata field.

```

### Examples

```bash
# Adding the title and genre metadata fields 
~$ python ./chapterize_ab.py '/path/to/audiobook/file.mp3' --title 'Game of Thrones' --genre 'Fantasy'
```

```powershell
# Adding an external cover art file (using shorthand flag -ca)
PS > python .\chapterize_ab.py 'C:\path\to\audiobook\file.mp3' -ca 'C:\path\to\cover_art.jpg'
```

```powershell
# Set model to use German as the language (requires a different model, see above)
PS > python .\chapterize_ab.py 'C:\path\to\audiobook\file.mp3' --language 'de'
```

```bash
# Download a different model (Italian large used here as an example)
~$ python ./chapterize_ab.py '/path/to/audiobook/file.mp3' --download_model 'large' --language 'italian'
```

---

## Improvement

This script is still in alpha, and thus there are bound to be some issues; I've noticed a few words
and phrases that have falsely generated chapter markers, which I'm currently compiling into an *ignore* list as I see
them. With that said, it's been remarkably accurate so far.

I encourage anyone who might use this to report any issues you find, particularly with false positive chapter markers.
The more false positives identified, the more accurate it will be!

---

## Known Issues

### Access Denied Error on Windows

Every once in a while when downloading a new model on Windows, it will throw an "Access Denied" exception after attempting to rename the extracted file. This isn't really a permissions issue, but rather a concurrency one. I've found that closing any app or Explorer window that might be related to Chapterize-Audiobooks usually fixes this problem. This seems to be a somewhat common issue with Python on Windows when renaming/deleting/moving files.
