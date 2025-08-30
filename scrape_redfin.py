import asyncio
import json
import random
from math import radians, cos, sin, asin, sqrt
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# This function calculates the distance between two points on Earth using the Haversine formula.
# It is used to calculate the distance of each house from a target location, if provided.
def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two points on Earth.
    """
    R = 3958.8  # Earth's radius in miles
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    lat1 = radians(lat1)
    lat2 = radians(lat2)
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))
    return R * c

# These functions simulate human-like interaction with the webpage to avoid detection by anti-scraping measures.
# They add randomness to the scrolling and mouse movements.
async def human_scroll(page, steps=5):
    """
    Simulates human-like scrolling.
    """
    for _ in range(steps):
        distance = random.randint(100, 400)
        print(f"[CMD] Scrolling by {distance} pixels")
        await page.evaluate(f"window.scrollBy(0,{distance});")
        await asyncio.sleep(random.uniform(0.5, 1.5))

async def human_move_mouse(page, steps=5):
    """
    Simulates human-like mouse movements.
    """
    for _ in range(steps):
        x = random.randint(0, 800)
        y = random.randint(0, 600)
        print(f"[CMD] Moving mouse to ({x},{y})")
        await page.mouse.move(x, y, steps=random.randint(5, 15))
        await asyncio.sleep(random.uniform(0.2, 0.6))

async def scroll_until_loaded(page, max_scrolls=10):
    """
    Scrolls the page until no new house cards are loaded or max scrolls is reached.
    """
    prev_count = 0
    for i in range(max_scrolls):
        await human_scroll(page, 3)
        await human_move_mouse(page, 3)
        await asyncio.sleep(random.uniform(1, 2))
        
        # Use a more specific selector to find house cards
        cards = await page.query_selector_all('div.HomeCardContainer')
        print(f"[CMD] After scroll {i + 1}, found {len(cards)} cards")
        
        if len(cards) == prev_count:
            break
        prev_count = len(cards)

    return cards

# This is the core scraping function. It extracts data from a single house card.
async def scrape_card(card, target_lat=None, target_lon=None):
    """
    Extracts structured data from a single house card element.
    """
    try:
        await card.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.5, 1.0))
        
        async def get_text(selector, attr='text'):
            el = await card.query_selector(selector)
            if el:
                if attr == 'text':
                    return await el.inner_text()
                elif attr == 'attribute':
                    return await el.get_attribute('content')
            return ''

        # Use more robust selectors based on the provided HTML
        address = await get_text('div.bp-Homecard__Address')
        price = await get_text('span.bp-Homecard__Price--value')
        beds = await get_text('span.bp-Homecard__Stats--beds')
        baths = await get_text('span.bp-Homecard__Stats--baths')
        sqft = await get_text('span.bp-Homecard__LockedStat--value')
        open_house = await get_text('span.Badge--open-house')

        # The HTML also contains structured data in JSON-LD format which is very reliable.
        # Let's extract information from there first.
        data_from_json = {}
        script_tag = await card.query_selector('script[type="application/ld+json"]')
        if script_tag:
            try:
                js = json.loads(await script_tag.inner_text())
                if isinstance(js, list):
                    js = js[0]
                
                # Extract address from JSON-LD
                address_json = js.get('address', {})
                data_from_json['address'] = f"{address_json.get('streetAddress', '')}, {address_json.get('addressLocality', '')}, {address_json.get('addressRegion', '')} {address_json.get('postalCode', '')}"
                
                # Extract price from JSON-LD
                offers = js.get('offers', {})
                data_from_json['price'] = f"${offers.get('price', '')}" if offers.get('price') else 'Price not found'

            except Exception as e:
                print(f"[CMD] Error parsing JSON-LD: {e}")

        # The HTML structure has the address and price repeated in a different element, so we can use that for validation or as a fallback.
        # The price is also sometimes available from the `offers` schema.
        if not address or 'Address not found' in address:
            address = data_from_json.get('address', 'Address not found')
        
        if not price or 'Price not found' in price:
            price = data_from_json.get('price', 'Price not found')
        
        # Extract beds and baths from a single string if separate spans are not found.
        if not beds or not baths:
            stats_text = await get_text('div.bp-Homecard__Stats')
            if stats_text:
                stats_parts = stats_text.split('•')
                beds_match = next((part for part in stats_parts if 'bed' in part), '')
                baths_match = next((part for part in stats_parts if 'bath' in part), '')
                beds = beds_match.strip() if beds_match else 'Beds not found'
                baths = baths_match.strip() if baths_match else 'Baths not found'

        # Extract lot size and garage info from KeyFactsExtension
        lot = await get_text('div.KeyFactsExtension', 'text="sq ft lot"')
        garage = await get_text('div.KeyFactsExtension', 'text="garage spots"')
        walk_score = await get_text('div.KeyFactsExtension', 'text="walkable"')

        latitude, longitude = None, None
        if script_tag:
            try:
                js = json.loads(await script_tag.inner_text())
                if isinstance(js, list):
                    js = js[0]
                geo = js.get('geo', {})
                latitude = geo.get('latitude')
                longitude = geo.get('longitude')
            except (json.JSONDecodeError, AttributeError):
                pass

        distance_mile = ''
        if latitude and longitude and target_lat and target_lon:
            distance_mile = round(haversine(target_lat, target_lon, latitude, longitude), 2)

        print(f"[CMD] Scraped card: {address} | Price: {price} | Distance: {distance_mile}")
        return {
            'address': address,
            'price': price,
            'beds': beds.replace('beds', '').strip(),
            'baths': baths.replace('baths', '').strip(),
            'sqft': sqft,
            'lot': lot,
            'garage': garage,
            'walk_score': walk_score,
            'open_house': open_house,
            'latitude': latitude,
            'longitude': longitude,
            'distance_mile': distance_mile
        }
    except Exception as e:
        print(f"[CMD] Error scraping card: {e}")
        return None

# This is the main function that coordinates the scraping process.
async def main():
    target_url = "https://www.redfin.com/zipcode/90034/filter/open-house=anytime,school-types=elementary+middle+high"
    target_lat = 34.0205  # Latitude for the center of 90034
    target_lon = -118.4069 # Longitude for the center of 90034
    
    print(f"Starting scraper for {target_url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Set a User-Agent header to mimic a regular browser and avoid being blocked.
        await page.set_extra_http_headers({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'})
        
        await page.goto(target_url, wait_until='networkidle')
        await asyncio.sleep(random.uniform(5, 10)) # Wait a bit for the page to load completely

        # This section is the core of the scraping logic. It finds all the house cards and processes them one by one.
        house_cards = await scroll_until_loaded(page)
        scraped_data = []

        if not house_cards:
            print("No house cards found on the page.")
        else:
            print(f"Found {len(house_cards)} house cards to scrape. Starting now...")
            for card in house_cards:
                data = await scrape_card(card, target_lat=target_lat, target_lon=target_lon)
                if data:
                    scraped_data.append(data)
        
        await browser.close()
    
    print("\n\n--- Scraping Complete ---")
    if scraped_data:
        print(f"Successfully scraped {len(scraped_data)} houses.")
        # Save the scraped data to a JSON file.
        with open('redfin_open_houses.json', 'w') as f:
            json.dump(scraped_data, f, indent=4)
        print("Data saved to redfin_open_houses.json")
    else:
        print("No data was scraped.")

# Run the main function.
if __name__ == '__main__':
    asyncio.run(main())
