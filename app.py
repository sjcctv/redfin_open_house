from flask import Flask, render_template, request, jsonify
import asyncio
import scrape_redfin
import random, re

app=Flask(__name__)
scrape_progress={"page":0}

async def scrape_with_progress(target_address):
    results=[]
    target_lat,target_lon=34.0187882,-118.4141604
    match=re.search(r"\b\d{5}\b",target_address)
    zipcode=match.group(0) if match else "90034"
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=["--no-sandbox","--disable-setuid-sandbox"])
        context=await browser.new_context(user_agent=f"Mozilla/5.0 AppleWebKit/537.36 Chrome/{random.randint(100,115)}")
        page=await context.new_page()
        url=f"https://www.redfin.com/zipcode/{zipcode}/filter/open-house=anytime,school-types=elementary+middle+high"
        await page.goto(url,timeout=120000)
        page_number=0
        while True:
            page_number+=1
            scrape_progress["page"]=page_number
            print(f"[CMD] Scraping page {page_number}...")
            cards=await scrape_redfin.scroll_until_loaded(page)
            for card in cards:
                data=await scrape_redfin.scrape_card(card,target_lat,target_lon)
                if data: results.append(data)
            next_btn=await page.query_selector('button[data-rf-test-name="pagination-next"]')
            if next_btn:
                if await next_btn.get_attribute('disabled'): break
                await next_btn.click()
                await asyncio.sleep(random.uniform(2,4))
            else: break
        await browser.close()
    return results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_scrape',methods=['POST'])
def start_scrape():
    scrape_progress["page"]=0
    data=request.json
    target_address=data.get('target_address','')
    if not target_address: return jsonify({"error":"Please provide target_address"}),400
    try:
        loop=asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results=loop.run_until_complete(scrape_with_progress(target_address))
        return jsonify(results)
    except Exception as e:
        return jsonify({"error":str(e)}),500

@app.route('/progress')
def progress():
    return jsonify(scrape_progress)

if __name__=="__main__":
    # 监听所有网卡，局域网可访问
    app.run(host="0.0.0.0", port=5000, debug=True)


