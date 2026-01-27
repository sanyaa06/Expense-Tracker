from transformers import pipeline

classifier=pipeline(

    "zero-shot-classification",
    model="facebook/bart-large-mnli"

)

INTENT_LABELS = [
    "TOTAL_EXPENSE",
    "CATEGORY_EXPENSE",
    "LAST_EXPENSE",
    "SAVING_ADVICE",
    "GENERAL_CHAT"
]

def intent_detector(message):
    result=classifier(message, INTENT_LABELS)
    return result["labels"]