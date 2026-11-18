"""Explicit country aliases and ISO codes; never infer a country from a keyword."""
COUNTRY_CODES = dict(line.split('|') for line in '''United States|USA
China|CHN
United Kingdom|GBR
India|IND
South Korea|KOR
Germany|DEU
Canada|CAN
Japan|JPN
Singapore|SGP
Switzerland|CHE
Saudi Arabia|SAU
Mexico|MEX
France|FRA
Colombia|COL
Italy|ITA
Belgium|BEL
Netherlands|NLD
Brazil|BRA
Austria|AUT
Spain|ESP
Qatar|QAT
United Arab Emirates|ARE
Australia|AUS
Denmark|DNK
Taiwan|TWN
Greece|GRC
Portugal|PRT
Ireland|IRL
Hong Kong|HKG
Turkey|TUR
Sweden|SWE
Czech Republic|CZE
South Africa|ZAF
Israel|ISR
Argentina|ARG
Norway|NOR
Nigeria|NGA
Iran|IRN
Malaysia|MYS
Puerto Rico|PRI
Egypt|EGY
Pakistan|PAK
Thailand|THA
Poland|POL
Chile|CHL
Russia|RUS
Slovenia|SVN
Slovakia|SVK
Hungary|HUN
Ecuador|ECU
Kuwait|KWT
Finland|FIN
New Zealand|NZL
Bulgaria|BGR
Indonesia|IDN
Vietnam|VNM
Venezuela|VEN
Kazakhstan|KAZ
Philippines|PHL
Lebanon|LBN
Peru|PER
Tunisia|TUN
Jordan|JOR
Cyprus|CYP
Romania|ROU
Estonia|EST
Iraq|IRQ
Trinidad and Tobago|TTO
Ukraine|UKR
Ethiopia|ETH
Bangladesh|BGD
Oman|OMN
England|GBR
Luxembourg|LUX
Yemen|YEM
Morocco|MAR
Ghana|GHA
Algeria|DZA
British Virgin Islands|VGB
New Caledonia|NCL
Costa Rica|CRI
Iceland|ISL
Croatia|HRV
Palestine|PSE'''.splitlines())

ALIASES = {
    'usa': 'United States', 'us': 'United States', 'u.s.a.': 'United States',
    'u.s.': 'United States', 'united states of america': 'United States',
    'uk': 'United Kingdom', 'u.k.': 'United Kingdom', 'england': 'United Kingdom',
    'holland': 'Netherlands', 'pr china': 'China',
    'korea, republic of (south)': 'South Korea',
    'republic of korea': 'South Korea', 'hong kong, china': 'Hong Kong',
}
_NAMES = {name.casefold(): name for name in COUNTRY_CODES}


def normalize_country(name):
    name = name.strip()
    return ALIASES.get(name.casefold(), _NAMES.get(name.casefold(), name))


def country_counts(raw):
    """Preserve all source counts, summing aliases (including unknown locations)."""
    result = {}
    for name, count in raw.items():
        name = normalize_country(name) or 'Unknown'
        result[name] = result.get(name, 0) + int(count)
    return result
