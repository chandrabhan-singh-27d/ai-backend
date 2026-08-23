import math


def calculate(expression: str) -> str:
    allowed = {"sqrt": math.sqrt, "abs": abs, "round": round}

    try:
        result = eval(expression, {"__builtins__": {}}, allowed)
        return str(result)
    except Exception as e:
        return f"Error: {e}"
