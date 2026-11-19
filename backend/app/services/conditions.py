"""Shared user conditions. Monetary limits are never inferred from price levels."""
from __future__ import annotations

import re
from ..schemas import MoneyLimit, UserConditions


CATEGORY_TERMS = {
    "cafe": r"kafe|cafe|kahveci", "restaurant": r"restoran|lokanta",
    "park": r"park", "museum": r"muze", "library": r"kutuphane",
}
FEATURE_LABELS = {"quiet": "Sessizlik", "accessible": "Erişilebilirlik", "alcohol_free": "Alkolsüz mekân"}
NUMBER_WORDS = {"iki": 2, "uc": 3, "dort": 4, "bes": 5, "alti": 6, "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10, "on bir": 11, "on iki": 12}


def folded(text: str) -> str:
    return text.translate(str.maketrans("İıŞşĞğÜüÖöÇç", "iiSsGgUuOoCc")).lower()


def new_topic(text: str) -> bool:
    return bool(re.match(r"\s*(?:yeni (?:bir )?(?:konu|bulusma|plan)|bastan basla|oncekini unut)\b", folded(text)))


def explicit_group_size(text: str) -> int | None:
    source = folded(text)
    words = "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))
    match = re.search(rf"\b(\d{{1,2}}|{words})\s+(?:kisi(?:yiz)?|arkadas(?:iz)?)\b", source)
    if not match:
        return None
    return int(match[1]) if match[1].isdigit() else NUMBER_WORDS[match[1]]


def explicit_criteria(text: str) -> dict[str, float]:
    """Reconcile unambiguous priority clauses, never short-circuit the whole request."""
    result = {}
    terms = {"rating": r"puan|kalite|yildiz", "cost": r"fiyat|ucret|maliyet", "proximity": r"yakinlik|mesafe|yakin"}
    source = folded(text)
    # An explicit numeric weight may be in the next clause. Do not replace it with 70.
    numeric_weights = bool(re.search(r"agirli\w*\s*(?:%|yuzde\s*)?\d|(?:%|yuzde\s*)\d", source))
    for clause in re.split(r"[;!?]|\.(?!\d)|,(?!\d)|\bama\b|\bve\b", source):
        if re.search(r"kisi\s*\d|\bbana\b|\bbenim\b", clause):
            continue
        mentioned = [key for key, term in terms.items() if re.search(term, clause)]
        if len(mentioned) != 1 or not re.search(r"onemli|oncelik|on plana|agirli\w*", clause):
            continue
        numeric = re.search(r"(?:%|yuzde\s+)(\d+(?:[.,]\d+)?)", clause)
        if numeric:
            value = float(numeric[1].replace(",", "."))
            if not 0 <= value <= 100:
                raise ValueError("Kriter ağırlığı 0 ile 100 arasında olmalıdır.")
        elif re.search(r"\d|iki kat|uc kat|yarisi|iki misli", clause) or numeric_weights:
            # Leave relative/numeric changes to the validated model edit, not the preset.
            continue
        elif re.search(r"olmasin|degil|onemsiz", clause):
            value = 10
        else:
            value = 70
        key = mentioned[0]
        if key in result and result[key] != value:
            raise ValueError("Aynı kriter için çelişen öncelikler var; hangisini kullanacağınızı belirtin.")
        result[key] = value
    return result


def read_conditions(text: str, current: UserConditions) -> tuple[UserConditions, list[str]]:
    """Only explicit, bounded edits; ambiguous or conflicting limits ask a question."""
    result = current.model_copy(deep=True)
    source = folded(text)
    questions = []
    amounts = re.findall(r"(?<![\d.,])([\d]+(?:[.,]\d+)*)\s*(?:tl\b|lira\b|₺)", source)
    if amounts:
        def amount(value):
            if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", value):
                value = value.replace(".", "").replace(",", ".")
            else:
                value = value.replace(",", ".")
            return float(value)
        try:
            numbers = {amount(value) for value in amounts}
        except ValueError:
            numbers = set()
        per_person = bool(re.search(r"kisi\s*basi|kisi\s*basina|her birimiz|adam basi", source))
        group = bool(re.search(r"toplam|hepimiz icin|grup butcesi", source))
        if len(numbers) != 1 or per_person == group:
            questions.append("Bütçe kişi başına mı, tüm grup için toplam mı? Tek bir TL sınırı belirtin.")
        elif not 0 < next(iter(numbers)) <= 10_000_000:
            questions.append("Bütçe sıfırdan büyük ve geçerli bir TL tutarı olmalı.")
        else:
            result.budget_limit = MoneyLimit(amount=next(iter(numbers)), scope="per_person" if per_person else "group")
    elif re.search(r"butce (?:sinirini )?(?:kaldir|sil)|butce siniri olmasin", source):
        result.budget_limit = None

    for category, terms in CATEGORY_TERMS.items():
        list_terms = "|".join(CATEGORY_TERMS.values())
        pattern = rf"\b(?:{terms})\w*(?:\s*(?:,|ve|veya)\s*(?:{list_terms})\w*)*\s+(?:olmasin|istemiyorum|haric|disinda|istemeyiz)\b"
        if re.search(pattern, source) and category not in result.excluded_categories:
            result.excluded_categories.append(category)
        if re.search(rf"\b(?:{terms})\w*\s+(?:olabilir|dahil olsun)\b", source):
            result.excluded_categories = [item for item in result.excluded_categories if item != category]
    features = {
        "quiet": r"(?:mutlaka|kesinlikle|zorunlu).{0,20}(?:sessiz|sakin)|sessiz\w*.{0,15}(?:sart|zorunlu)",
        "accessible": r"tekerlekli sandalye|engelli erisimi|erisilebilir\w* (?:sart|zorunlu)",
        "alcohol_free": r"alkolsuz|alkol olmasin",
    }
    for feature, pattern in features.items():
        subject = {"quiet": r"sessiz\w*|sakin\w*", "accessible": r"erisilebilir\w*|engelli erisimi", "alcohol_free": r"alkolsuz\w*"}[feature]
        if re.search(rf"(?:{subject}).{{0,20}}(?:sart|zorunlu) degil", source):
            result.required_features = [item for item in result.required_features if item != feature]
            continue
        if re.search(rf"(?:{subject})\s+(?:olmasin|istemiyorum)", source):
            questions.append(f"{FEATURE_LABELS[feature]} koşulunu kaldırmak mı istiyorsunuz? Mevcut koşul değiştirilmedi.")
            continue
        if re.search(pattern, source) and feature not in result.required_features:
            result.required_features.append(feature)
    return result, questions


def condition_warnings(conditions: UserConditions) -> list[str]:
    warnings = []
    if conditions.budget_limit:
        warnings.append("TL bütçesi korundu. Google fiyat seviyesi gerçek TL tutarı değildir; fiyat verisi olmadan bütçe uyumu doğrulanamaz.")
    if conditions.required_features:
        labels = ", ".join(FEATURE_LABELS[item] for item in conditions.required_features)
        warnings.append(f"{labels}: mevcut veri kaynağında doğrulanmıyor. Zorunlu koşul kaldırılmadı.")
    return warnings
