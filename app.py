from flask import Flask, render_template, request, jsonify
import asyncio
import scrape_redfin
import random, re
import requests

app = Flask(__name__)
scrape_progress = {"page": 0, "total_cards": 0, "scraped_cards": 0}


def get_lat_lon(address):
    """
    Get latitude and longitude for a given address using OpenStreetMap's Nominatim API.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": "GeoLocatorApp/1.0 (contact: your_email@example.com)"}

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data:
            lat = data[0]["lat"]
            lon = data[0]["lon"]
            return float(lat), float(lon)
        else:
            print("No results found for this address.")
            return None, None
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None, None


async def scrape_with_progress(target_address):
    results = []
    target_lat, target_lon = get_lat_lon(target_address)

    match = re.findall(r"\b\d{5}\b", target_address)
    zipcode = match[-1] if match else "90034"

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(
            user_agent=f"Mozilla/5.0 AppleWebKit/537.36 Chrome/{random.randint(100,115)}"
        )
        page = await context.new_page()
        url = f"https://www.redfin.com/zipcode/{zipcode}/filter/open-house=anytime,school-types=elementary+middle+high"
        print(target_lat, target_lon)
        print(url)
        await page.goto(url, timeout=10000)

        page_number = 0
        scrape_progress["scraped_cards"] = 0
        scrape_progress["total_cards"] = 0
        while True:
            page_number += 1
            scrape_progress["page"] = page_number
            print(f"[CMD] Scraping page {page_number}...")
            cards = await scrape_redfin.scroll_until_loaded(page)
            scrape_progress["total_cards"] = len(cards)
            for card in cards:
                data = await scrape_redfin.scrape_card(card, target_lat, target_lon)
                if data:
                    results.append(data)
                    scrape_progress["scraped_cards"] += 1
            next_btn = await page.query_selector('button[data-rf-test-name="pagination-next"]')
            if next_btn:
                if await next_btn.get_attribute("disabled"):
                    break
                await next_btn.click()
                await asyncio.sleep(random.uniform(2, 4))
            else:
                break
        await browser.close()

    # ✅ return a dictionary, not just the list
    return {"results": results, "has_location": target_lat is not None and target_lon is not None}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/start_scrape", methods=["POST"])
def start_scrape():
    scrape_progress["page"] = 0
    data = request.json
    target_address = data.get("target_address", "")
    if not target_address:
        return jsonify({"error": "Please provide target_address"}), 400
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # ✅ run and get structured result
        output = loop.run_until_complete(scrape_with_progress(target_address))
        return jsonify(output)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/progress")
def progress():
    return jsonify(scrape_progress)


if __name__ == "__main__":
    # 监听所有网卡，局域网可访问
    app.run(host="0.0.0.0", port=5000, debug=True)


