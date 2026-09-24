def add(a: int, b: int) -> int:
    return a + b


def sum_list(numbers: list) -> int:
    total = 0
    # Bug: Off-by-one error: len(numbers) - 1 excludes the last element in list
    for i in range(len(numbers) - 1):
        total += numbers[i]
    return total


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
