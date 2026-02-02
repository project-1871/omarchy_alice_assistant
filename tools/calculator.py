"""Calculator tool - math and unit conversions"""

import re
import math
from tools.base import Tool


class CalculatorTool(Tool):
    name = "calculator"
    description = "Perform calculations and unit conversions"
    triggers = [
        "calculate", "what's", "what is", "how much is",
        "plus", "minus", "times", "divided", "percent",
        "convert", "to celsius", "to fahrenheit", "to kilometers",
        "to miles", "to kg", "to pounds", "square root", "sqrt"
    ]

    # Unit conversions
    CONVERSIONS = {
        ('km', 'miles'): lambda x: x * 0.621371,
        ('miles', 'km'): lambda x: x * 1.60934,
        ('kg', 'pounds'): lambda x: x * 2.20462,
        ('kg', 'lbs'): lambda x: x * 2.20462,
        ('pounds', 'kg'): lambda x: x / 2.20462,
        ('lbs', 'kg'): lambda x: x / 2.20462,
        ('celsius', 'fahrenheit'): lambda x: (x * 9/5) + 32,
        ('c', 'f'): lambda x: (x * 9/5) + 32,
        ('fahrenheit', 'celsius'): lambda x: (x - 32) * 5/9,
        ('f', 'c'): lambda x: (x - 32) * 5/9,
        ('meters', 'feet'): lambda x: x * 3.28084,
        ('feet', 'meters'): lambda x: x / 3.28084,
        ('cm', 'inches'): lambda x: x / 2.54,
        ('inches', 'cm'): lambda x: x * 2.54,
        ('liters', 'gallons'): lambda x: x * 0.264172,
        ('gallons', 'liters'): lambda x: x * 3.78541,
    }

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        try:
            # Check for unit conversion first
            conversion = self._try_conversion(query_lower)
            if conversion:
                return conversion

            # Check for percentage calculation
            percent = self._try_percentage(query_lower)
            if percent:
                return percent

            # Try to evaluate as math expression
            result = self._evaluate_math(query)
            if result is not None:
                return result

            return "I couldn't parse that calculation. Try something like 'what's 15 times 23' or 'convert 100 km to miles'."

        except Exception as e:
            return f"Calculation error: {e}"

    def _try_conversion(self, query: str) -> str | None:
        """Try to parse and perform unit conversion"""
        # Pattern: "convert X unit to unit" or "X unit to unit" or "X unit in unit"
        patterns = [
            r'convert\s+([\d.]+)\s*(\w+)\s*to\s*(\w+)',
            r'([\d.]+)\s*(\w+)\s+to\s+(\w+)',
            r'([\d.]+)\s*(\w+)\s+in\s+(\w+)',
            r'([\d.]+)\s*degrees?\s*(\w+)\s+(?:to|in)\s*(\w+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                value = float(match.group(1))
                from_unit = match.group(2).lower()
                to_unit = match.group(3).lower()

                # Look up conversion
                key = (from_unit, to_unit)
                if key in self.CONVERSIONS:
                    result = self.CONVERSIONS[key](value)
                    return f"{value} {from_unit} is {result:.2f} {to_unit}."

        return None

    def _try_percentage(self, query: str) -> str | None:
        """Handle percentage calculations"""
        # "X percent of Y" or "X% of Y"
        match = re.search(r'([\d.]+)\s*(?:percent|%)\s*of\s*([\d.]+)', query)
        if match:
            percent = float(match.group(1))
            value = float(match.group(2))
            result = (percent / 100) * value
            return f"{percent}% of {value} is {result:.2f}."

        # "what percent is X of Y"
        match = re.search(r'(?:what\s+)?percent(?:age)?\s+(?:is\s+)?([\d.]+)\s+of\s+([\d.]+)', query)
        if match:
            part = float(match.group(1))
            whole = float(match.group(2))
            result = (part / whole) * 100
            return f"{part} is {result:.1f}% of {whole}."

        return None

    def _evaluate_math(self, query: str) -> str | None:
        """Evaluate mathematical expression"""
        # Extract numbers and operators
        query_lower = query.lower()

        # Replace word operators with symbols
        expr = query_lower
        expr = re.sub(r'\bplus\b', '+', expr)
        expr = re.sub(r'\bminus\b', '-', expr)
        expr = re.sub(r'\btimes\b', '*', expr)
        expr = re.sub(r'\bmultiplied by\b', '*', expr)
        expr = re.sub(r'\bdivided by\b', '/', expr)
        expr = re.sub(r'\bover\b', '/', expr)
        expr = re.sub(r'\bto the power of\b', '**', expr)
        expr = re.sub(r'\bsquared\b', '**2', expr)
        expr = re.sub(r'\bcubed\b', '**3', expr)

        # Handle square root
        sqrt_match = re.search(r'(?:square root|sqrt)\s*(?:of\s*)?([\d.]+)', expr)
        if sqrt_match:
            value = float(sqrt_match.group(1))
            result = math.sqrt(value)
            return f"The square root of {value} is {result:.4f}."

        # Extract just the math expression
        # Keep only numbers, operators, parentheses, decimal points
        math_expr = re.sub(r'[^0-9+\-*/().^ ]', '', expr)
        math_expr = math_expr.replace('^', '**')
        math_expr = math_expr.strip()

        if not math_expr:
            return None

        # Safely evaluate
        try:
            # Only allow safe operations
            allowed = set('0123456789+-*/().** ')
            if not all(c in allowed for c in math_expr):
                return None

            result = eval(math_expr, {"__builtins__": {}}, {"math": math})

            # Format result
            if isinstance(result, float):
                if result == int(result):
                    return f"The answer is {int(result)}."
                else:
                    return f"The answer is {result:.4f}."
            return f"The answer is {result}."

        except:
            return None
