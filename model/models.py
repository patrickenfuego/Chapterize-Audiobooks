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

# Some false positive phrases/words that trigger a chapter marker...will need building over time
excluded_phrases_english = (
    'chapter and verse', 'chapters', 'this chapter', 'that chapter',
    'chapter of', 'in chapter', 'and chapter', 'chapter heading',
    'chapter head', 'chapter house', 'chapter book', 'a chapter',
    'chapter out', 'chapter in', 'particular chapter', 'spicy chapter',
    'before chapter'
)
