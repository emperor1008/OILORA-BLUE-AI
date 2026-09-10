"""
Oilora Blue AI — Conservative Location Normalization

Derives *country* from source location text only when the match is
unambiguous (a trailing state/territory code or a known country name token).
Nothing is geocoded and nothing is guessed: when no confident match exists the
value stays ``None`` so the UI can honestly say the source did not report it.

Reference data below is limited to official US state/territory abbreviations
and common official country names used to anchor the trailing-token match.
"""

from __future__ import annotations

# Official US state and territory abbreviations (USPS codes).
US_STATES: dict[str, str] = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
    "PR": "Puerto Rico",
    "GU": "Guam",
    "VI": "U.S. Virgin Islands",
    "AS": "American Samoa",
    "MP": "Northern Mariana Islands",
}

# Country names that commonly appear as the trailing token of a source location
# string. Matches are exact against whole trailing tokens (case-insensitive).
COUNTRY_NAMES: dict[str, str] = {
    "usa": "United States",
    "u.s.a.": "United States",
    "us": "United States",
    "u.s.": "United States",
    "united states": "United States",
    "canada": "Canada",
    "mexico": "Mexico",
    "brazil": "Brazil",
    "argentina": "Argentina",
    "uruguay": "Uruguay",
    "chile": "Chile",
    "peru": "Peru",
    "colombia": "Colombia",
    "venezuela": "Venezuela",
    "ecuador": "Ecuador",
    "panama": "Panama",
    "costa rica": "Costa Rica",
    "guatemala": "Guatemala",
    "honduras": "Honduras",
    "nicaragua": "Nicaragua",
    "el salvador": "El Salvador",
    "belize": "Belize",
    "cuba": "Cuba",
    "jamaica": "Jamaica",
    "haiti": "Haiti",
    "dominican republic": "Dominican Republic",
    "bahamas": "Bahamas",
    "trinidad and tobago": "Trinidad and Tobago",
    "barbados": "Barbados",
    "puerto rico": "Puerto Rico",
    "guam": "Guam",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "france": "France",
    "spain": "Spain",
    "italy": "Italy",
    "greece": "Greece",
    "portugal": "Portugal",
    "netherlands": "Netherlands",
    "belgium": "Belgium",
    "germany": "Germany",
    "denmark": "Denmark",
    "norway": "Norway",
    "sweden": "Sweden",
    "finland": "Finland",
    "iceland": "Iceland",
    "poland": "Poland",
    "russia": "Russia",
    "ukraine": "Ukraine",
    "turkey": "Türkiye",
    "morocco": "Morocco",
    "algeria": "Algeria",
    "tunisia": "Tunisia",
    "libya": "Libya",
    "egypt": "Egypt",
    "nigeria": "Nigeria",
    "angola": "Angola",
    "ghana": "Ghana",
    "senegal": "Senegal",
    "south africa": "South Africa",
    "kenya": "Kenya",
    "tanzania": "Tanzania",
    "mozambique": "Mozambique",
    "israel": "Israel",
    "saudi arabia": "Saudi Arabia",
    "kuwait": "Kuwait",
    "qatar": "Qatar",
    "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    "oman": "Oman",
    "yemen": "Yemen",
    "iran": "Iran",
    "iraq": "Iraq",
    "india": "India",
    "pakistan": "Pakistan",
    "bangladesh": "Bangladesh",
    "sri lanka": "Sri Lanka",
    "maldives": "Maldives",
    "myanmar": "Myanmar",
    "thailand": "Thailand",
    "vietnam": "Vietnam",
    "malaysia": "Malaysia",
    "singapore": "Singapore",
    "indonesia": "Indonesia",
    "philippines": "Philippines",
    "china": "China",
    "taiwan": "Taiwan",
    "japan": "Japan",
    "south korea": "South Korea",
    "korea": "South Korea",
    "australia": "Australia",
    "new zealand": "New Zealand",
    "papua new guinea": "Papua New Guinea",
    "fiji": "Fiji",
    "greenland": "Greenland",
    "kazakhstan": "Kazakhstan",
    "somalia": "Somalia",
    "djibouti": "Djibouti",
    "sudan": "Sudan",
}


def derive_country(location_text: str | None) -> str | None:
    """
    Return a confident country name parsed from source location text, or None.

    Strategy (conservative by design):
    1. A trailing `, XX` USPS state/territory code, or a trailing known
       state name, resolves to the United States.
    2. Otherwise the last 1-3 comma-separated trailing tokens are matched
       exactly (case-insensitive) against known country names.
    Nothing else is attempted; ambiguous text yields None (callers display
    "Not reported by the available source").
    """
    if not location_text or not location_text.strip():
        return None
    text = location_text.strip().rstrip(".,;")
    tokens = [t.strip() for t in text.split(",") if t.strip()]

    # 1) USPS code or spelled-out state as the final token.
    if tokens:
        last = tokens[-1].strip()
        if len(last) == 2 and last.isalpha():
            code = last.upper()
            if code in US_STATES:
                return "United States"
        if last.lower() in {name.lower() for name in US_STATES.values()}:
            return "United States"

    # 2) Known country token among the trailing tokens.
    for token in reversed(tokens[-3:]):
        key = token.lower().strip().rstrip(".")
        if key in COUNTRY_NAMES:
            return COUNTRY_NAMES[key]
    return None


def state_from_us_text(location_text: str | None) -> str | None:
    """Return the US state/territory name when the location text names one."""
    if not location_text:
        return None
    text = location_text.strip().rstrip(".,;")
    tokens = [t.strip() for t in text.split(",") if t.strip()]
    if not tokens:
        return None
    last = tokens[-1]
    if len(last) == 2 and last.isalpha() and last.upper() in US_STATES:
        return US_STATES[last.upper()]
    if last.lower() in {n.lower() for n in US_STATES.values()}:
        # Return the canonical spelling
        for name in US_STATES.values():
            if name.lower() == last.lower():
                return name
    return None
