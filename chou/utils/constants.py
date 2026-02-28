"""
Constants and configuration for Chou
"""

# Ordinal number to integer mapping for conference editions
ORDINAL_MAP = {
    'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
    'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
    'eleventh': 11, 'twelfth': 12, 'thirteenth': 13, 'fourteenth': 14, 'fifteenth': 15,
    'sixteenth': 16, 'seventeenth': 17, 'eighteenth': 18, 'nineteenth': 19, 'twentieth': 20,
    'twenty-first': 21, 'twenty-second': 22, 'twenty-third': 23, 'twenty-fourth': 24, 'twenty-fifth': 25,
    'twenty-sixth': 26, 'twenty-seventh': 27, 'twenty-eighth': 28, 'twenty-ninth': 29, 'thirtieth': 30,
    'thirty-first': 31, 'thirty-second': 32, 'thirty-third': 33, 'thirty-fourth': 34, 'thirty-fifth': 35,
    'thirty-sixth': 36, 'thirty-seventh': 37, 'thirty-eighth': 38, 'thirty-ninth': 39, 'fortieth': 40,
    'forty-first': 41, 'forty-second': 42, 'forty-third': 43, 'forty-fourth': 44, 'forty-fifth': 45,
}

# Common academic conference/venue abbreviations
CONFERENCE_NAMES = [
    'AAAI', 'IJCAI', 'NeurIPS', 'NIPS', 'ICML', 'ICLR', 'CVPR', 'ICCV', 'ECCV',
    'ACL', 'EMNLP', 'NAACL', 'COLING', 'SIGIR', 'WWW', 'KDD', 'ICDE', 'VLDB',
    'SIGMOD', 'PODS', 'CIKM', 'WSDM', 'RecSys', 'UAI', 'AISTATS', 'COLT',
    'ICRA', 'IROS', 'RSS', 'CoRL', 'MICCAI', 'ISBI', 'IPMI',
    'CHI', 'UIST', 'IUI', 'CSCW', 'UbiComp', 'MobiCom', 'MobiSys',
    'OSDI', 'SOSP', 'NSDI', 'EuroSys', 'ASPLOS', 'ISCA', 'MICRO', 'HPCA',
    'CCS', 'Oakland', 'USENIX', 'NDSS', 'CRYPTO', 'EUROCRYPT',
    'SIGGRAPH', 'EuroGraphics', 'ACM MM', 'ICME', 'ICASSP',
    'INTERSPEECH', 'ICPR', 'BMVC', 'WACV', 'ACCV', 'ACMMM',
]

# Chinese numeral to digit mapping
CHINESE_DIGIT_MAP = {
    '零': 0, '〇': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5,
    '陆': 6, '柒': 7, '捌': 8, '玖': 9, '拾': 10,
}

# Special characters to remove from author names
AUTHOR_SPECIAL_CHARS = [
    '*', '∗', '⁎', '✱', '＊',  # asterisks
    '†', '‡', '§', '¶', '∥',   # footnote markers
    '¹', '²', '³', '⁴', '⁵', '⁶', '⁷', '⁸', '⁹', '⁰',  # superscript numbers
    '₁', '₂', '₃', '₄', '₅', '₆', '₇', '₈', '₉', '₀',  # subscript numbers
    '①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨',  # circled numbers
    '♠', '♣', '♦', '♥', '★', '☆',  # other markers
]

# Invalid characters for filenames
INVALID_FILENAME_CHARS = '<>:"/\\|?*'

# Maximum filename length
MAX_FILENAME_LENGTH = 200

# Header patterns to skip when parsing
HEADER_PATTERNS = [
    r'AAAI',
    r'Conference',
    r'Association for',
    r'Artificial Intelligence',
    r'Copyright',
    r'www\.',
    r'https?://',
    r'ScienceDirect',
    r'Elsevier',
    r'Springer',
    r'journal\s+homepage',
    r'Contents\s+lists?\s+available',
    r'Check\s+for',
    r'^\s*updates?\s*$',
    r'ARTICLE\s+INFO',
    r'Keywords?:',
]

# Default fallback year
DEFAULT_YEAR = 2024
