"""Runtime string localization (entity names, device info, danger/problem text).

Home Assistant's built-in translation system (strings.json / translations/*.json)
only covers config/options flow text. Entity names, device info, and the
danger-level / avalanche-problem display text are set directly by this
integration's Python code and are not covered by that mechanism, so we do our
own minimal lookup here, keyed by hass.config.language. Falls back to English
for any language we don't have strings for.

Danger-level and problem-type labels follow the official multilingual EAWS
(European Avalanche Warning Services) terminology used across Alpine avalanche
bulletins, matching how the SLF itself publishes its DE/FR/IT bulletins.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant

SUPPORTED_LANGUAGES = ("de", "en", "fr", "it")

STRINGS: dict[str, dict[str, str]] = {
    "device_name": {
        "de": "SLF Lawinenbulletin ({name})",
        "en": "Swiss Avalanche Bulletin ({name})",
        "fr": "Bulletin d'avalanches Suisse ({name})",
        "it": "Bollettino valanghe Svizzera ({name})",
    },
    "manufacturer": {
        "de": "WSL-Institut für Schnee- und Lawinenforschung SLF",
        "en": "WSL Institute for Snow and Avalanche Research SLF",
        "fr": "Institut pour l'étude de la neige et des avalanches SLF (WSL)",
        "it": "Istituto per lo studio della neve e delle valanghe SLF (WSL)",
    },
    "model": {
        "de": "Lawinenbulletin",
        "en": "Avalanche Bulletin",
        "fr": "Bulletin d'avalanches",
        "it": "Bollettino valanghe",
    },
    "danger_level_sensor_name": {
        "de": "Lawinen-Gefahrenstufe",
        "en": "Avalanche Danger Level",
        "fr": "Degré de danger d'avalanche",
        "it": "Grado di pericolo valanghe",
    },
    "region_sensor_name": {
        "de": "Lawinen-Warnregion",
        "en": "Avalanche Warning Region",
        "fr": "Région d'avertissement d'avalanche",
        "it": "Regione di allerta valanghe",
    },
    "problem_sensor_name": {
        "de": "Lawinenproblem {n}",
        "en": "Avalanche Problem {n}",
        "fr": "Problème d'avalanche {n}",
        "it": "Problema valanghe {n}",
    },
}

# CAAML dangerRating mainValue -> localized EAWS danger-level text.
DANGER_LEVEL_TEXT: dict[str, dict[str, str]] = {
    "de": {
        "low": "Gering",
        "moderate": "Mässig",
        "considerable": "Erheblich",
        "high": "Gross",
        "very_high": "Sehr gross",
    },
    "en": {
        "low": "Low",
        "moderate": "Moderate",
        "considerable": "Considerable",
        "high": "High",
        "very_high": "Very High",
    },
    "fr": {
        "low": "Faible",
        "moderate": "Limité",
        "considerable": "Marqué",
        "high": "Fort",
        "very_high": "Très fort",
    },
    "it": {
        "low": "Debole",
        "moderate": "Moderato",
        "considerable": "Marcato",
        "high": "Forte",
        "very_high": "Molto forte",
    },
}

# CAAML avalancheProblem problemType -> localized EAWS avalanche-problem text.
PROBLEM_TYPE_TEXT: dict[str, dict[str, str]] = {
    "de": {
        "new_snow": "Neuschnee",
        "wind_slab": "Triebschnee",
        "persistent_weak_layers": "Altschnee",
        "wet_snow": "Nassschnee",
        "gliding_snow": "Gleitschnee",
        "favourable_situation": "Günstige Situation",
        "cornices": "Wechten",
        "no_distinct_problem": "Kein spezielles Problem",
    },
    "en": {
        "new_snow": "New Snow",
        "wind_slab": "Wind-Drifted Snow",
        "persistent_weak_layers": "Persistent Weak Layers",
        "wet_snow": "Wet Snow",
        "gliding_snow": "Gliding Snow",
        "favourable_situation": "Favourable Situation",
        "cornices": "Cornices",
        "no_distinct_problem": "No Distinct Avalanche Problem",
    },
    "fr": {
        "new_snow": "Neige fraîche",
        "wind_slab": "Neige soufflée",
        "persistent_weak_layers": "Couches fragiles persistantes",
        "wet_snow": "Neige mouillée",
        "gliding_snow": "Avalanches de glissement",
        "favourable_situation": "Situation favorable",
        "cornices": "Corniches",
        "no_distinct_problem": "Aucun problème d'avalanche distinct",
    },
    "it": {
        "new_snow": "Neve fresca",
        "wind_slab": "Neve ventata",
        "persistent_weak_layers": "Strati deboli persistenti",
        "wet_snow": "Neve bagnata",
        "gliding_snow": "Valanghe di slittamento",
        "favourable_situation": "Situazione favorevole",
        "cornices": "Cornici",
        "no_distinct_problem": "Nessun problema di valanghe particolare",
    },
}


def get_language(hass: HomeAssistant) -> str:
    lang = (hass.config.language or "en").lower().split("-")[0]
    return lang if lang in SUPPORTED_LANGUAGES else "en"


def t(key: str, hass: HomeAssistant, **kwargs) -> str:
    """Look up a localized string by key, formatted with kwargs."""
    lang = get_language(hass)
    template = STRINGS.get(key, {}).get(lang) or STRINGS.get(key, {}).get("en") or key
    return template.format(**kwargs) if kwargs else template


def danger_level_text(main_value: str | None, hass: HomeAssistant) -> str | None:
    """Translate a raw CAAML dangerRating mainValue for display."""
    if not main_value:
        return None
    lang = get_language(hass)
    table = DANGER_LEVEL_TEXT.get(lang, DANGER_LEVEL_TEXT["en"])
    return table.get(main_value, main_value)


def problem_type_text(problem_type: str | None, hass: HomeAssistant) -> str | None:
    """Translate a raw CAAML avalancheProblem problemType for display."""
    if not problem_type:
        return None
    lang = get_language(hass)
    table = PROBLEM_TYPE_TEXT.get(lang, PROBLEM_TYPE_TEXT["en"])
    return table.get(problem_type, problem_type)
