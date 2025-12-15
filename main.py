import json
import asyncio
import re
import os
import time
import math
from dotenv import load_dotenv
import google.generativeai as genai
from playwright.async_api import async_playwright


class GoogleMapsScraper:
    def __init__(self):
        self.intercepted_reviews = []

    async def handle_response(self, response):
        url = response.url
        if "listugcposts" in url or "review/list" in url:
            try:
                text = await response.text()
                clean_json = text.replace(")]}'", "").strip()
                
                if len(clean_json) > 1500:
                    data = json.loads(clean_json)
                    self.intercepted_reviews.append(data)
                    print(f"Network: Captured review data batch. Total batches: {len(self.intercepted_reviews)}")
            except:
                pass

    async def scrape(self, url, max_reviews=None):
        self.intercepted_reviews = []
        start_time = time.time()
        print(f"[{time.time() - start_time:.2f}s] Initializing scraper process for {url} (Max reviews: {max_reviews})")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, 
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                viewport={'width': 1366, 'height': 768},
                locale="en-US", 
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            await page.route("**/*", lambda route: route.abort() 
                if route.request.resource_type in ["image", "media"] or "/maps/vt" in route.request.url 
                else route.continue_())

            page.on("response", self.handle_response)

            print(f"[{time.time() - start_time:.2f}s] Navigating to target URL.")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            print(f"[{time.time() - start_time:.2f}s] DOM loaded. Checking for dynamic content...")
            try:
                print(f"[{time.time() - start_time:.2f}s] Waiting for review content...")
                await page.wait_for_selector('div[data-review-id]', state="attached", timeout=15000)
                print(f"[{time.time() - start_time:.2f}s] Review content detected.")
            except Exception as e:
                print(f"  Warning: Reviews did not appear within timeout. Continuing anyway.")

            print(f"[{time.time() - start_time:.2f}s] Initiating scroll sequence to load reviews.")
            scroll_start_time = time.time()
            
            try:
                await page.hover('div[role="feed"], .m6QErb[aria-label]')
            except:
                pass

            no_new_data_counter = 0
            last_batch_count = 0
            
            # Scroll logic setup
            max_loops = 1000 # Safety cap
            
            if max_reviews:
                print(f"  Logic: Scrape limited to approximately {max_reviews} reviews.")
            
            print(f"  Logic: Starting scroll sequence in infinite mode (stops on no new data).")
            last_batch_time = time.time()

            for i in range(max_loops):
                await page.mouse.wheel(0, 8000)
                await asyncio.sleep(0.1) # Wait for render, tweak if it breaks

                current_count = len(self.intercepted_reviews)
                
                if current_count > last_batch_count:
                    new_batches = current_count - last_batch_count
                    time_since_last = time.time() - last_batch_time
                    print(f"  Performance: Acquired {new_batches} new batches in {time_since_last:.2f}s. Total: {current_count}")
                    no_new_data_counter = 0
                    last_batch_time = time.time()
                else:
                    no_new_data_counter += 1
                
                last_batch_count = current_count
                
                if max_reviews and (len(self.intercepted_reviews) * 10) >= max_reviews:
                     print(f"  Stop Condition: Reached requested limit of ~{max_reviews} reviews. Concluding scroll.")
                     break

                if no_new_data_counter >= 50:
                    print(f"  Stop Condition: No new data received after 50 attempts (approx 5s). Concluding scroll.")
                    break

            scroll_end_time = time.time()
            print(f"[{time.time() - start_time:.2f}s] Scroll sequence complete. Duration: {scroll_end_time - scroll_start_time:.2f}s.")

            await browser.close()

        print(f"Processing {len(self.intercepted_reviews)} captured data batches...")
        cleaned_reviews = []
        
        def extract_reviews_from_json(node):
            if isinstance(node, list):
                if len(node) > 3 and isinstance(node[0], str) and node[0].startswith("Ch") and isinstance(node[1], list):
                    try:
                        review = {
                            "id": node[0],
                            "name": node[1][4][5][0] if (len(node[1]) > 4) else "Unknown",
                            "date": node[1][6] if (len(node[1]) > 6) else "Unknown",
                            "rating": node[2][0][0] if (len(node) > 2 and node[2]) else 0,
                            "text": None
                        }
                        if len(node) > 2 and len(node[2]) > 15 and node[2][15]:
                            review["text"] = node[2][15][0][0]
                        elif len(node) > 2 and len(node[2]) > 16 and node[2][16]:
                            review["text"] = node[2][16][0][0]
                            
                        cleaned_reviews.append(review)
                    except:
                        pass
                for item in node:
                    extract_reviews_from_json(item)
            elif isinstance(node, dict):
                for key in node:
                    extract_reviews_from_json(node[key])

        for batch in self.intercepted_reviews:
            extract_reviews_from_json(batch)

        unique_reviews = {r['id']: r for r in cleaned_reviews}.values()
        print(f"Successfully extracted {len(unique_reviews)} unique reviews.")
        
        return list(unique_reviews)