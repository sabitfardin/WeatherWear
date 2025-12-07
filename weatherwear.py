import requests
import matplotlib.pyplot as plt


# API endpoints (Open-Meteo)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


# Geocoding: city -> lat/lon

def geocode_city(city_name: str) -> dict:
    """
    Use Open-Meteo's free Geocoding API to convert a city name
    into latitude, longitude and some metadata.
    """
    params = {
        "name": city_name,
        "count": 1,
        "language": "en",
        "format": "json",
    }
    resp = requests.get(GEOCODING_URL, params=params, timeout=10)

    if resp.status_code != 200:
        raise ValueError(f"Geocoding error: {resp.status_code} - {resp.text}")

    data = resp.json()
    results = data.get("results")
    if not results:
        raise ValueError(f"No location found for '{city_name}'")

    first = results[0]
    return {
        "name": first.get("name"),
        "latitude": first.get("latitude"),
        "longitude": first.get("longitude"),
        "country": first.get("country"),
        "timezone": first.get("timezone"),
    }



def fetch_current_weather(lat: float, lon: float, units: str = "metric") -> dict:
    """
    Call Open-Meteo Forecast API and retrieve current weather variables.
    No API key is required.
    """
    # Map our units choice to Open-Meteo parameter values
    temperature_unit = "celsius" if units == "metric" else "fahrenheit"
    windspeed_unit = "kmh" if units == "metric" else "mph"

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "timezone": "auto",
        "temperature_unit": temperature_unit,
        "windspeed_unit": windspeed_unit,
    }

    resp = requests.get(FORECAST_URL, params=params, timeout=10)
    if resp.status_code != 200:
        raise ValueError(f"Weather API error: {resp.status_code} - {resp.text}")

    data = resp.json()
    current = data.get("current", {})
    if not current:
        raise ValueError("No current weather data returned.")

    return current



def describe_weather_code(code: int) -> str:
    """
    Map Open-Meteo WMO weather codes to a simple text description.
    """
    if code is None:
        return "unknown weather"

    # Based on WMO weather code groups (simplified)
    if code == 0:
        return "clear sky"
    if code in [1, 2, 3]:
        return "partly cloudy or overcast"
    if code in [45, 48]:
        return "foggy or misty"
    if code in [51, 53, 55, 56, 57]:
        return "drizzle or light rain"
    if code in [61, 63, 65, 66, 67, 80, 81, 82]:
        return "rainy"
    if code in [71, 73, 75, 77, 85, 86]:
        return "snowy"
    if code in [95, 96, 99]:
        return "thunderstorms"
    return "mixed or unknown conditions"

def fetch_forecast_5day(lat: float, lon: float, units: str = "metric"):
    """
    Fetch the next 5 days of forecast data from Open-Meteo
    for plotting temperature trends.
    """
    temperature_unit = "celsius" if units == "metric" else "fahrenheit"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto",
        "temperature_unit": temperature_unit,
    }

    resp = requests.get(FORECAST_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get("daily", {})


def create_temperature_chart(forecast_data, units: str = "metric"):
    """
    Generate a temperature trend line chart for presentation.
    Saves the chart as 'temperature_chart.png'.
    """
    dates = forecast_data.get("time", [])
    max_temps = forecast_data.get("temperature_2m_max", [])
    min_temps = forecast_data.get("temperature_2m_min", [])

    if not dates or not max_temps:
        print("Not enough forecast data to generate chart.")
        return

    plt.figure(figsize=(8, 5))
    plt.plot(dates, max_temps, marker="o", label="Max Temp")
    plt.plot(dates, min_temps, marker="o", label="Min Temp")

    unit_symbol = "°C" if units == "metric" else "°F"
    plt.title(f"5-Day Temperature Forecast")
    plt.xlabel("Date")
    plt.ylabel(f"Temperature ({unit_symbol})")
    plt.grid(True)
    plt.legend()

    plt.tight_layout()
    plt.savefig("temperature_chart.png")
    plt.close()

    print("Temperature chart saved as temperature_chart.png")


def analyze_weather(current: dict, units: str = "metric") -> dict:
    """
    Take the 'current' block from Open-Meteo and convert it into
    labeled conditions that our recommender can use.
    """
    temp = current.get("temperature_2m")
    feels_like = current.get("apparent_temperature")
    humidity = current.get("relative_humidity_2m")
    wind_speed = current.get("wind_speed_10m")
    precipitation = current.get("precipitation")
    code = current.get("weather_code")

    description = describe_weather_code(code)

    # Temperature label
    t = temp
    if t is None:
        temp_label = "unknown"
    elif t < -5:
        temp_label = "very cold"
    elif -5 <= t < 5:
        temp_label = "cold"
    elif 5 <= t < 15:
        temp_label = "cool"
    elif 15 <= t < 22:
        temp_label = "mild"
    elif 22 <= t < 28:
        temp_label = "warm"
    else:
        temp_label = "hot"

    # Flags
    if units == "metric":
        windy_threshold = 20  # km/h
    else:
        windy_threshold = 12  # mph, roughly

    is_windy = wind_speed is not None and wind_speed >= windy_threshold
    is_humid = humidity is not None and humidity >= 70
    is_rainy = (precipitation is not None and precipitation > 0) or "rain" in description
    is_snowy = "snow" in description

    return {
        "temp": temp,
        "feels_like": feels_like,
        "units": units,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "precipitation": precipitation,
        "weather_code": code,
        "description": description,
        "temp_label": temp_label,
        "is_windy": is_windy,
        "is_humid": is_humid,
        "is_rainy": is_rainy,
        "is_snowy": is_snowy,
    }


def recommend_clothing(analysis: dict, context: str) -> str:
    """
    Given analyzed weather and context ('indoor' or 'outdoor'),
    return a human-readable clothing recommendation.
    """
    temp_label = analysis["temp_label"]
    is_windy = analysis["is_windy"]
    is_humid = analysis["is_humid"]
    is_rainy = analysis["is_rainy"]
    is_snowy = analysis["is_snowy"]

    recs = []

    # Base layer based on temperature
    if temp_label == "very cold":
        recs.append("a heavy winter coat, thermal layers, gloves, and a warm hat")
    elif temp_label == "cold":
        recs.append("a warm jacket, sweater, and long pants")
    elif temp_label == "cool":
        recs.append("a light jacket or hoodie with long pants")
    elif temp_label == "mild":
        recs.append("a long-sleeve shirt or light sweater with jeans or chinos")
    elif temp_label == "warm":
        recs.append("a t-shirt or light top with breathable pants or shorts")
    elif temp_label == "hot":
        recs.append("a very light t-shirt and shorts or other breathable clothing")
    else:
        recs.append("comfortable layered clothing, as temperature is unclear")

    # Precipitation
    if is_rainy:
        recs.append("carry a waterproof jacket or umbrella")
    if is_snowy:
        recs.append("wear waterproof boots and an insulated jacket")

    # Wind & humidity adjustments
    if is_windy:
        recs.append("add a windbreaker or an extra layer to block the wind")
    if is_humid and temp_label in ["warm", "hot"]:
        recs.append("choose moisture-wicking fabrics to stay comfortable in the humidity")

    # Indoor vs outdoor context
    context = context.lower().strip()
    if context == "indoor":
        recs.append(
            "since you will be indoors, you can generally dress one level lighter "
            "than you would for staying outside for a long time."
        )
    elif context == "outdoor":
        recs.append(
            "since you will be outdoors, plan for slightly harsher conditions than the current reading."
        )
    else:
        recs.append("adjust for your personal comfort and activity level.")

    return " ".join(recs)



def format_weather_summary(location_info: dict, analysis: dict) -> str:
    """
    Create a readable weather summary string from location + analysis.
    """
    name = location_info.get("name")
    country = location_info.get("country")
    temp = analysis["temp"]
    feels_like = analysis["feels_like"]
    units = analysis["units"]
    humidity = analysis["humidity"]
    wind_speed = analysis["wind_speed"]
    description = analysis["description"]
    temp_label = analysis["temp_label"]

    unit_symbol = "°C" if units == "metric" else "°F"

    lines = [
        f"Weather summary for {name}, {country}:",
        f"  Condition     : {description} ({temp_label})",
        f"  Temperature   : {temp:.1f}{unit_symbol}" if temp is not None else "  Temperature   : N/A",
        f"  Feels like    : {feels_like:.1f}{unit_symbol}" if feels_like is not None else "  Feels like    : N/A",
        f"  Humidity      : {humidity}% " if humidity is not None else "  Humidity      : N/A",
        f"  Wind speed    : {wind_speed} " + ("km/h" if units == "metric" else "mph")
        if wind_speed is not None else "  Wind speed    : N/A",
    ]
    return "\n".join(lines)


# Main program


def main():
    print("=== WeatherWear (Open-Meteo Edition) ===\n")

    city = input("Enter your city name (e.g., Buffalo, London, Dhaka): ").strip()
    if not city:
        print("City name is required. Exiting.")
        return

    context = input("Are you going indoor or outdoor? (type 'indoor' or 'outdoor'): ").strip().lower()
    if context not in ["indoor", "outdoor"]:
        print("Context not recognized. Defaulting to 'outdoor'.")
        context = "outdoor"

    unit_choice = input("Use metric (Celsius) or imperial (Fahrenheit)? [metric/imperial, default=metric]: ").strip().lower()
    if unit_choice not in ["metric", "imperial"]:
        unit_choice = "metric"

    print("\nLooking up your location...\n")
    try:
        location_info = geocode_city(city)
    except Exception as e:
        print(f"Failed to resolve city: {e}")
        return

    print(
        f"Found: {location_info.get('name')}, {location_info.get('country')} "
        f"(lat={location_info.get('latitude')}, lon={location_info.get('longitude')})"
    )
    print("Fetching current weather...\n")

    try:
        current = fetch_current_weather(location_info["latitude"], location_info["longitude"], units=unit_choice)
    except Exception as e:
        print(f"Failed to fetch weather data: {e}")
        return

    analysis = analyze_weather(current, units=unit_choice)
    recommendation = recommend_clothing(analysis, context=context)

    print(format_weather_summary(location_info, analysis))
    print("\nClothing Recommendation:")
    print(recommendation)


    print("\nGenerating 5-day temperature chart for your presentation...")
    try:
        forecast_data = fetch_forecast_5day(
            location_info["latitude"],
            location_info["longitude"],
            units=unit_choice
        )
        create_temperature_chart(forecast_data, units=unit_choice)
    except Exception as e:
        print(f"Could not generate temperature chart: {e}")
    # ---------------------------------------------------------

    print("\nThank you for using WeatherWear!")



if __name__ == "__main__":
    main()
