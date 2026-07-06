def calculate_total(data):
    total = 0
    for item in data:
        # Fix: Use .get() to safely access 'amount' and default to 0 if missing
        total += item.get('amount', 0)
    return total

# Example usage (inferred from stack trace to match the crash context)
# The actual 'data' variable content might vary, but this change fixes the function.
data = [
    {'item_name': 'Laptop', 'amount': 1200},
    {'item_name': 'Mouse', 'amount': 25},
    {'item_name': 'Keyboard', 'value': 75} # This item would have caused the KeyError
]

result = calculate_total(data)
print(f"Total: {result}")
