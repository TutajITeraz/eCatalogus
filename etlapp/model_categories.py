from collections import Counter


MODEL_CATEGORIES = {
    'Formulas': 'main',
    'TextStandarization': 'main',
    'EditionContent': 'main',
    'Sections': 'main',
    'ContentFunctions': 'main',
    'RiteNames': 'main',
    'Traditions': 'main',
    'LiturgicalGenres': 'main',
    'LiturgicalGenresNames': 'main',
    'Type': 'main',
    'SeasonMonth': 'main',
    'Week': 'main',
    'Day': 'main',
    'MassHour': 'main',
    'Layer': 'main',
    'Genre': 'main',
    'Topic': 'main',
    'Ceremony': 'main',
    'DecorationTypes': 'main',
    'DecorationTechniques': 'main',
    'Characteristics': 'main',
    'Subjects': 'main',
    'Colours': 'main',
    'FeastRanks': 'main',
    'BindingTypes': 'main',
    'BindingStyles': 'main',
    'BindingMaterials': 'main',
    'BindingDecorationTypes': 'main',
    'BindingComponents': 'main',
    'ScriptNames': 'main',
    'MusicNotationNames': 'main',
    'TimeReference': 'main',
    'Places': 'main',
    'Condition': 'ms',
    'Codicology': 'ms',
    'Layouts': 'ms',
    'Quires': 'ms',
    'Clla': 'ms',
    'Hands': 'shared',
    'Bibliography': 'shared',
    'Contributors': 'shared',
    'Watermarks': 'shared',
    'Manuscripts': 'ms',
    'Content': 'ms',
    'Calendar': 'ms',
    'Decoration': 'ms',
    'DecorationSubjects': 'ms',
    'DecorationColours': 'ms',
    'DecorationCharacteristics': 'ms',
    'ContentTopic': 'ms',
    'Binding': 'ms',
    'Origins': 'ms',
    'Provenance': 'ms',
    'Image': 'ms',
    'ManuscriptHands': 'ms',
    'ManuscriptWatermarks': 'ms',
    'ManuscriptBibliography': 'ms',
    'ManuscriptMusicNotations': 'ms',
    'ManuscriptGenres': 'ms',
    'ManuscriptBindingMaterials': 'ms',
    'ManuscriptBindingDecorations': 'ms',
    'ManuscriptBindingComponents': 'ms',
    'UserOpenAIAPIKey': 'local',
    'Profile': 'local',
    'AIQuery': 'local',
    'ImproveOurDataEntry': 'local',
    'Projects': 'main',
    'MSProjects': 'ms',
    'AttributeDebate': 'local',
    'DeletedRecord': 'local',
}


SYNC_CATEGORIES = {'main', 'shared', 'ms'}
SHARED_CATEGORIES = {'shared'}


def get_model_category(model_name):
    return MODEL_CATEGORIES.get(model_name, 'unassigned')


def summarize_categories(model_names):
    return Counter(get_model_category(model_name) for model_name in model_names)


def get_sync_model_names():
    return sorted(
        model_name
        for model_name, category in MODEL_CATEGORIES.items()
        if category in SYNC_CATEGORIES
    )


def get_shared_model_names():
    return sorted(
        model_name
        for model_name, category in MODEL_CATEGORIES.items()
        if category in SHARED_CATEGORIES
    )
