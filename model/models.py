models_small = (
    'vosk-model-small-en-us-0.15',
    'vosk-model-small-en-in-0.4',
    'vosk-model-small-cn-0.22',
    'vosk-model-small-ru-0.22',
    'vosk-model-small-fr-0.22',
    'vosk-model-small-de-0.15',
    'vosk-model-small-es-0.42',
    'vosk-model-small-pt-0.3',
    'vosk-model-small-tr-0.3',
    'vosk-model-small-vn-0.3',
    'vosk-model-small-it-0.22',
    'vosk-model-small-nl-0.22',
    'vosk-model-small-ca-0.4',
    'vosk-model-small-fa-0.5',
    'vosk-model-small-uk-v3-small',
    'vosk-model-small-kz-0.15',
    'vosk-model-small-ja-0.22',
    'vosk-model-small-eo-0.42',
    'vosk-model-small-hi-0.22',
    'vosk-model-small-cs-0.4-rhasspy',
    'vosk-model-small-pl-0.22'
)

models_large = (
    'vosk-model-en-us-0.22',
    'vosk-model-en-in-0.5',
    'vosk-model-cn-0.22',
    'vosk-model-ru-0.22',
    'vosk-model-fr-0.22',
    'vosk-model-de-0.21',
    'vosk-model-es-0.42',
    'vosk-model-pt-fb-v0.1.1-20220516_2113',
    'vosk-model-el-gr-0.7',
    'vosk-model-it-0.22',
    'vosk-model-ar-0.22-linto-1.1.0',
    'vosk-model-fa-0.5',
    'vosk-model-tl-ph-generic-0.6',
    'vosk-model-uk-v3',
    'vosk-model-kz-0.15',
    'vosk-model-ja-0.22',
    'vosk-model-hi-0.22'
)

# Model language name to language code mapping
model_languages = {
    'English': 'en-us',
    'English (US)': 'en-us',
    'English US': 'en-us',
    'English (India)': 'en-in',
    'English India': 'en-in',
    'Chinese': 'cn',
    'Russian': 'ru',
    'French': 'fr',
    'German': 'de',
    'Spanish': 'es',
    'Portuguese': 'pt',
    'Greek': 'el',
    'Turkish': 'tr',
    'Vietnamese': 'vn',
    'Italian': 'it',
    'Dutch': 'nl',
    'Catalan': 'ca',
    'Arabic': 'ar',
    'Farsi': 'fa',
    'Filipino': 'tl-ph',
    'Kazakh': 'kz',
    'Japanese': 'ja',
    'Ukrainian': 'uk',
    'Esperanto': 'eo',
    'Hindi': 'hi',
    'Czech': 'cs',
    'Polish': 'pl'
}


'''
    Language Features
    
    Excluded phrases and chapter markers
'''

# Signal phrases for chapter markers
_markers_english = ('prologue', 'chapter', 'epilogue')
_markers_german = ('prolog', 'kapitel', 'epilog')

# Some false positive phrases/words that trigger a chapter marker...will need building over time
_excluded_phrases_english = (
    'chapter and verse', 'chapters', 'this chapter', 'that chapter',
    'chapter of', 'in chapter', 'and chapter', 'chapter heading',
    'chapter head', 'chapter house', 'chapter book', 'a chapter',
    'chapter out', 'chapter in', 'particular chapter', 'spicy chapter',
    'before chapter', 'main chapter', 'final chapter', 'concluding chapter',
    'glorious chapter', 'next chapter', 'chapter asking', 'matthew chapter',
    'forgotten chapter', 'last chapter', 'chapter room', 'the chapter',
    'prologue to', 'from prologue', 'epilogue to', 'from epilogue'
)

_excluded_phrases_german = (
    'der kapitelsaal', 'das schlusskapitel', 'das hauptkapitel', 'dieses kapitel',
    'das schlusskapitel', 'die kapitelüberschrift', 'ein kapitel'
)



def get_lang_from_code(lang: str) -> str:
    """Convert language code to friendly language string.

    :param lang: Language code to convert
    :return: Friendly language name
    """

    lang_str = list(filter(lambda l: model_languages[l] == lang, model_languages))[0].lower()
    return lang_str


def get_language_features(lang: str) -> tuple[tuple, tuple] | tuple[None, None]:
    """Return excluded phrases and chapter markers for the specified language.

    Module helper function to dynamically return language features based on the language passed by the user.
    If no excluded phrases or markers are defined for the specified language, None is returned.

    :param lang: Language code
    :return: Tuple containing excluded phrases and markers for lang or None
    """

    module_vars = globals()

    try:
        lang_str = get_lang_from_code(lang)
        return module_vars[f'_excluded_phrases_{lang_str}'], module_vars[f'_markers_{lang_str}']
    except (KeyError, IndexError):
        return None, None
