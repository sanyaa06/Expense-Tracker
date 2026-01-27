import re

def parse_intent(message):
    msg = message.lower()

    categories = {
        "food": "Food",
        "travel": "Travel",
        "shopping": "Shopping",
        "bills": "Bills",
        "entertainment": "Entertainment",
        "groceries": "Groceries"
    }

    period = None
    if "today" in msg:
        period = "today"
    elif "month" in msg or "this month" in msg:
        period = "month"

    for key, value in categories.items():
        if key in msg:
            return {
                "intent": "CATEGORY_EXPENSE",
                "category": value,
                "period": period or "month"
            }

    if "total" in msg or "spent" in msg or "expense" in msg:
        return {
            "intent": "TOTAL_EXPENSE",
            "category": None,
            "period": period or "month"
        }

    if "save" in msg or "saving" in msg or "advice" in msg:
        return {
            "intent": "SAVING_ADVICE",
            "category": None,
            "period": None
        }

    return {
        "intent": "UNKNOWN",
        "category": None,
        "period": None
    }
