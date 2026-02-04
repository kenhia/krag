"""Sample Python file for testing text extraction and retrieval."""


def fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number using recursion.

    Args:
        n: The position in the Fibonacci sequence

    Returns:
        The nth Fibonacci number
    """
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


class DataProcessor:
    """Process and transform data for analysis."""

    def __init__(self, name: str):
        self.name = name
        self.processed_count = 0

    def process(self, data: list[int]) -> list[int]:
        """Process a list of integers by doubling each value."""
        self.processed_count += 1
        return [x * 2 for x in data]
