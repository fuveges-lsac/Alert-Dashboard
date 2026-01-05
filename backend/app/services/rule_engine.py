import re
from datetime import datetime
from typing import Dict, Any, List

def match_condition(alert: Dict, condition: Dict) -> bool:
    field, operator, value = condition.get("field"), condition.get("operator"), condition.get("value")
    alert_value = alert.get(field, "")
    if operator == "equals":
        return str(alert_value).lower() == str(value).lower()
    elif operator == "contains":
        return str(value).lower() in str(alert_value).lower()
    elif operator == "regex":
        return bool(re.search(value, str(alert_value), re.IGNORECASE))
    return False

def match_conditions(alert: Dict, conditions: List[Dict]) -> bool:
    return all(match_condition(alert, c) for c in conditions)

def process_alert(alert: Dict, rules: List[Dict]) -> Dict:
    result = {"alert": alert.copy(), "actions_taken": [], "suppressed": False, "routed_to": None}
    for rule in sorted(rules, key=lambda r: r.get("priority", 0)):
        if not rule.get("enabled", True) or not match_conditions(alert, rule.get("conditions", [])):
            continue
        for action in rule.get("actions", []):
            if action.get("type") == "suppress":
                result["suppressed"] = True
                result["actions_taken"].append(f"Suppressed by: {rule['name']}")
        if result["suppressed"]:
            break
    return result
