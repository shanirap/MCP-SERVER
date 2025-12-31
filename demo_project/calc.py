def add(a: int, b: int) -> int:
    return a + b

def divide(a: int, b: int) -> float:
    # BUG: should raise on b==0, but currently returns 0
    if b == 0:
        return 0
    return a / b
