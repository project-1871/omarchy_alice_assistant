"""Weather tool using Open-Meteo API (free, no API key)"""

import urllib.request
import urllib.parse
import json
from datetime import datetime
from tools.base import Tool
import config


class WeatherTool(Tool):
    name = "weather"
    description = "Get current weather and forecasts"
    triggers = [
        "weather", "temperature", "forecast", "rain", "snow",
        "how hot", "how cold", "will it rain", "will it snow",
        "what's it like outside", "do i need a jacket", "do i need an umbrella"
    ]

    # WMO Weather codes to descriptions
    WEATHER_CODES = {
        0: "clear sky",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "foggy",
        48: "depositing rime fog",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "dense drizzle",
        56: "light freezing drizzle",
        57: "dense freezing drizzle",
        61: "slight rain",
        63: "moderate rain",
        65: "heavy rain",
        66: "light freezing rain",
        67: "heavy freezing rain",
        71: "slight snow",
        73: "moderate snow",
        75: "heavy snow",
        77: "snow grains",
        80: "slight rain showers",
        81: "moderate rain showers",
        82: "violent rain showers",
        85: "slight snow showers",
        86: "heavy snow showers",
        95: "thunderstorm",
        96: "thunderstorm with slight hail",
        99: "thunderstorm with heavy hail",
    }

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        try:
            data = self._fetch_weather()
        except Exception as e:
            return f"Couldn't get weather data: {e}"

        # Determine what user wants
        if any(w in query_lower for w in ["forecast", "week", "next few days", "coming days"]):
            return self._format_forecast(data)
        elif any(w in query_lower for w in ["tomorrow"]):
            return self._format_tomorrow(data)
        elif any(w in query_lower for w in ["rain", "umbrella"]):
            return self._check_rain(data)
        elif any(w in query_lower for w in ["jacket", "cold", "warm"]):
            return self._check_temperature_advice(data)
        else:
            return self._format_current(data)

    def _fetch_weather(self) -> dict:
        """Fetch weather data from Open-Meteo API"""
        params = {
            "latitude": config.WEATHER_LAT,
            "longitude": config.WEATHER_LON,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": 5
        }
        url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)

        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode())

    def _get_condition(self, code: int) -> str:
        """Convert weather code to description"""
        return self.WEATHER_CODES.get(code, "unknown conditions")

    def _format_current(self, data: dict) -> str:
        """Format current weather conditions"""
        current = data["current"]
        temp = round(current["temperature_2m"])
        humidity = current["relative_humidity_2m"]
        wind = round(current["wind_speed_10m"])
        condition = self._get_condition(current["weather_code"])

        return (
            f"It's currently {temp} degrees in {config.WEATHER_CITY} with {condition}. "
            f"Humidity is {humidity}% and wind at {wind} km/h."
        )

    def _format_forecast(self, data: dict) -> str:
        """Format multi-day forecast"""
        daily = data["daily"]
        lines = [f"Forecast for {config.WEATHER_CITY}:"]

        for i in range(min(5, len(daily["time"]))):
            date = datetime.strptime(daily["time"][i], "%Y-%m-%d")
            day_name = date.strftime("%A")
            high = round(daily["temperature_2m_max"][i])
            low = round(daily["temperature_2m_min"][i])
            condition = self._get_condition(daily["weather_code"][i])
            rain_chance = daily["precipitation_probability_max"][i]

            lines.append(f"{day_name}: {high}/{low} degrees, {condition}, {rain_chance}% chance of rain.")

        return " ".join(lines)

    def _format_tomorrow(self, data: dict) -> str:
        """Format tomorrow's forecast"""
        daily = data["daily"]
        if len(daily["time"]) < 2:
            return "Can't get tomorrow's forecast."

        high = round(daily["temperature_2m_max"][1])
        low = round(daily["temperature_2m_min"][1])
        condition = self._get_condition(daily["weather_code"][1])
        rain_chance = daily["precipitation_probability_max"][1]

        return (
            f"Tomorrow in {config.WEATHER_CITY}: {high}/{low} degrees with {condition}. "
            f"{rain_chance}% chance of rain."
        )

    def _check_rain(self, data: dict) -> str:
        """Check if it will rain today"""
        daily = data["daily"]
        rain_chance = daily["precipitation_probability_max"][0]
        current_code = data["current"]["weather_code"]

        if current_code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
            return "It's already raining. Definitely grab an umbrella."
        elif rain_chance >= 70:
            return f"There's a {rain_chance}% chance of rain today. I'd take an umbrella."
        elif rain_chance >= 40:
            return f"There's a {rain_chance}% chance of rain. Maybe keep an umbrella handy."
        else:
            return f"Only {rain_chance}% chance of rain today. You should be fine without an umbrella."

    def _check_temperature_advice(self, data: dict) -> str:
        """Give advice based on temperature"""
        temp = data["current"]["temperature_2m"]

        if temp < 10:
            return f"It's {round(temp)} degrees. Definitely wear a jacket, it's cold out there."
        elif temp < 18:
            return f"It's {round(temp)} degrees. A light jacket would be a good idea."
        elif temp < 25:
            return f"It's {round(temp)} degrees. Nice and comfortable, no jacket needed."
        else:
            return f"It's {round(temp)} degrees. It's warm out, dress light."
