from typing import NamedTuple


class Country(NamedTuple):
    qid: str
    code: str
    name_ko: str


COUNTRIES = [
    Country("Q17", "JP", "일본"),
    Country("Q148", "CN", "중국"),
    Country("Q865", "TW", "대만"),
    Country("Q869", "TH", "태국"),
    Country("Q881", "VN", "베트남"),
    Country("Q928", "PH", "필리핀"),
    Country("Q252", "ID", "인도네시아"),
    Country("Q833", "MY", "말레이시아"),
    Country("Q334", "SG", "싱가포르"),
    Country("Q668", "IN", "인도"),
    Country("Q30", "US", "미국"),
    Country("Q16", "CA", "캐나다"),
    Country("Q96", "MX", "멕시코"),
    Country("Q155", "BR", "브라질"),
    Country("Q414", "AR", "아르헨티나"),
    Country("Q142", "FR", "프랑스"),
    Country("Q38", "IT", "이탈리아"),
    Country("Q29", "ES", "스페인"),
    Country("Q145", "GB", "영국"),
    Country("Q183", "DE", "독일"),
    Country("Q39", "CH", "스위스"),
    Country("Q40", "AT", "오스트리아"),
    Country("Q55", "NL", "네덜란드"),
    Country("Q31", "BE", "벨기에"),
    Country("Q41", "GR", "그리스"),
    Country("Q45", "PT", "포르투갈"),
    Country("Q34", "SE", "스웨덴"),
    Country("Q20", "NO", "노르웨이"),
    Country("Q189", "IS", "아이슬란드"),
    Country("Q213", "CZ", "체코"),
    Country("Q43", "TR", "튀르키예"),
    Country("Q79", "EG", "이집트"),
    Country("Q408", "AU", "호주"),
    Country("Q664", "NZ", "뉴질랜드"),
    Country("Q878", "AE", "아랍에미리트"),
]
