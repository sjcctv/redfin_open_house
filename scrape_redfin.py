import asyncio
import json, random, re
from math import radians, cos, sin, asin, sqrt
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    lat1 = radians(lat1)
    lat2 = radians(lat2)
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2*asin(sqrt(a))
    return R*c

async def human_scroll(page, steps=5):
    for _ in range(steps):
        distance=random.randint(100,400)
        print(f"[CMD] Scrolling by {distance} pixels")
        await page.evaluate(f"window.scrollBy(0,{distance});")
        await asyncio.sleep(random.uniform(0.5,1.5))

async def human_move_mouse(page, steps=5):
    for _ in range(steps):
        x=random.randint(0,800)
        y=random.randint(0,600)
        print(f"[CMD] Moving mouse to ({x},{y})")
        await page.mouse.move(x,y,steps=random.randint(5,15))
        await asyncio.sleep(random.uniform(0.2,0.6))

async def scroll_until_loaded(page, max_scrolls=10):
    prev_count=0
    for i in range(max_scrolls):
        await human_scroll(page,3)
        await human_move_mouse(page,3)
        await asyncio.sleep(random.uniform(1,2))
        cards = await page.query_selector_all('a.bp-Homecard')
        print(f"[CMD] After scroll {i+1}, found {len(cards)} cards")
        if len(cards)==prev_count: break
        prev_count=len(cards)
    return await page.query_selector_all('a.bp-Homecard')

async def scrape_card(card, target_lat=None, target_lon=None):
    try:
        await card.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.5,1.0))
        async def get_text(sel):
            return await sel.inner_text() if sel else ''
        address = await card.query_selector('div.bp-Homecard__Address')
        price = await card.query_selector('span.bp-Homecard__Price--value')
        beds = await card.query_selector('span.bp-Homecard__Stats--beds')
        baths = await card.query_selector('span.bp-Homecard__Stats--baths')
        sqft = await card.query_selector('span.bp-Homecard__LockedStat--value')
        lot = await card.query_selector('div.KeyFactsExtension >> text="sq ft lot"')
        garage = await card.query_selector('div.KeyFactsExtension >> text="garage"')
        walk_score = await card.query_selector('div.KeyFactsExtension >> text="Walk"')
        open_house = await card.query_selector('span.Badge--open-house')
        if not open_house: open_house = await card.query_selector('div.OpenHouseBadge')
        if not open_house:
            try: open_house = await card.wait_for_selector('span.Badge--open-house', timeout=3000)
            except PlaywrightTimeoutError: open_house=None

        latitude=None
        longitude=None
        script_tag = await card.query_selector('script[type="application/ld+json"]')
        if script_tag:
            try:
                js=json.loads(await script_tag.inner_text())
                if isinstance(js,list): js=js[0]
                geo=js.get("geo",{})
                latitude=geo.get("latitude")
                longitude=geo.get("longitude")
            except: pass

        distance_mile=''
        if latitude and longitude and target_lat and target_lon:
            distance_mile=round(haversine(target_lat,target_lon,latitude,longitude),2)

        print(f"[CMD] Scraped card: {await get_text(address)} | Distance: {distance_mile}")
        return {
            'address': await get_text(address),
            'price': await get_text(price),
            'beds': await get_text(beds),
            'baths': await get_text(baths),
            'sqft': await get_text(sqft),
            'lot': await get_text(lot),
            'garage': await get_text(garage),
            'walk_score': await get_text(walk_score),
            'open_house': await get_text(open_house),
            'latitude': latitude,
            'longitude': longitude,
            'distance_mile': distance_mile
        }
    except Exception as e:
        print("[CMD] Error scraping card:", e)
        return None
