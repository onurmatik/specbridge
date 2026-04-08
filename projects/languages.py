DEFAULT_PROJECT_SPEC_LANGUAGE = "en"

PROJECT_SPEC_LANGUAGE_CHOICES = (
    ("sq", "Albanian"),
    ("am", "Amharic"),
    ("ar", "Arabic"),
    ("hy", "Armenian"),
    ("bn", "Bengali"),
    ("bs", "Bosnian"),
    ("bg", "Bulgarian"),
    ("my", "Burmese"),
    ("ca", "Catalan"),
    ("zh", "Chinese"),
    ("hr", "Croatian"),
    ("cs", "Czech"),
    ("da", "Danish"),
    ("nl", "Dutch"),
    ("en", "English"),
    ("et", "Estonian"),
    ("fi", "Finnish"),
    ("fr", "French"),
    ("ka", "Georgian"),
    ("de", "German"),
    ("el", "Greek"),
    ("gu", "Gujarati"),
    ("hi", "Hindi"),
    ("hu", "Hungarian"),
    ("is", "Icelandic"),
    ("id", "Indonesian"),
    ("it", "Italian"),
    ("ja", "Japanese"),
    ("kn", "Kannada"),
    ("kk", "Kazakh"),
    ("ko", "Korean"),
    ("lv", "Latvian"),
    ("lt", "Lithuanian"),
    ("mk", "Macedonian"),
    ("ms", "Malay"),
    ("ml", "Malayalam"),
    ("mr", "Marathi"),
    ("mn", "Mongolian"),
    ("no", "Norwegian"),
    ("fa", "Persian"),
    ("pl", "Polish"),
    ("pt", "Portuguese"),
    ("pa", "Punjabi"),
    ("ro", "Romanian"),
    ("ru", "Russian"),
    ("sr", "Serbian"),
    ("sk", "Slovak"),
    ("sl", "Slovenian"),
    ("so", "Somali"),
    ("es", "Spanish"),
    ("sw", "Swahili"),
    ("sv", "Swedish"),
    ("tl", "Tagalog"),
    ("ta", "Tamil"),
    ("te", "Telugu"),
    ("th", "Thai"),
    ("tr", "Turkish"),
    ("uk", "Ukrainian"),
    ("ur", "Urdu"),
    ("vi", "Vietnamese"),
)

PROJECT_SPEC_LANGUAGE_LABELS = dict(PROJECT_SPEC_LANGUAGE_CHOICES)
PROJECT_SPEC_LANGUAGE_VALUES = frozenset(PROJECT_SPEC_LANGUAGE_LABELS)


def is_supported_project_spec_language(value: str | None) -> bool:
    return bool(value and value in PROJECT_SPEC_LANGUAGE_VALUES)


def project_spec_language_label(value: str | None) -> str:
    return PROJECT_SPEC_LANGUAGE_LABELS.get(
        value or "",
        PROJECT_SPEC_LANGUAGE_LABELS[DEFAULT_PROJECT_SPEC_LANGUAGE],
    )
