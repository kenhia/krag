# Malformed Python file for testing graceful fallback.
# This file has intentional syntax errors.

def valid_function():
    return "this is valid"

def broken_function(
    # Missing closing paren and colon
    x, y

class IncompleteClass:
    def method_one(self):
        return 1

    def method_two(self
        # Missing closing paren, colon, and body
