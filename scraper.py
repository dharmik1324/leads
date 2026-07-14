import urllib.parse
import re
from playwright.sync_api import sync_playwright
from duckduckgo_search import DDGS

def find_emails(business_name, address, limit=3):
    """
    Search DuckDuckGo for the business name, address, and 'email' keywords
    to extract emails from search result snippets using regular expressions.
    """
    query = f'"{business_name}" "{address}" email'
    emails = set()
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=limit)
            if results:
                for r in results:
                    text_to_search = f"{r.get('title', '')} {r.get('body', '')}"
                    # General regex for finding email addresses
                    found = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_to_search)
                    for email in found:
                        email_lower = email.lower()
                        # Sanity checks: avoid common image file formats parsed as emails
                        if not email_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '@2x', '.css', '.js')):
                            emails.add(email_lower)
    except Exception:
        # Silently capture any network/DDG query limits and proceed
        pass
    return list(emails)

def get_business_name_element(page):
    """
    Finds the actual business name h1 element in the details panel,
    ignoring the search list header h1 (which typically contains the word 'results').
    """
    try:
        h1s = page.locator('h1').all()
        if not h1s:
            return None
        if len(h1s) == 1:
            text = h1s[0].text_content().strip().lower()
            if "results" in text:
                return None
            return h1s[0]
        for el in h1s:
            try:
                text = el.text_content().strip().lower()
                if "results" not in text and text != "":
                    return el
            except Exception:
                pass
    except Exception:
        pass
    return None

def extract_details(page, seen_websites=None, seen_names=None, log_callback=None):
    """
    Extracts name, phone, address and searches email for the currently loaded detail panel.
    Returns a dictionary of business lead info or None if it has a website.
    """
    if log_callback is None:
        log_callback = print
        
    try:
        # Get business name first to check seen_names
        name = ""
        name_el = get_business_name_element(page)
        if name_el and name_el.is_visible():
            name = name_el.text_content().strip()
        else:
            return None
            
        if seen_names is not None:
            if name in seen_names:
                log_callback(f"-> Already processed business '{name}'. Skipping...")
                return None
            seen_names.add(name)

        # Locate details panel container to restrict selectors
        details_panel = page
        try:
            # We want to find the div[role="main"] or div.m6QErb container that contains our h1 element
            # and is not the outer container holding the results feed.
            panels = page.locator('div[role="main"], div.m6QErb').all()
            found_panel = False
            for p in panels:
                if p.is_visible():
                    # Check if the business name h1 is inside this panel
                    h1_els = p.locator('h1').all()
                    for h1_el in h1_els:
                        try:
                            h1_text = h1_el.text_content().strip()
                            if h1_text == name:
                                # Ensure it's not the outer page/search container (must not contain the results feed)
                                if p.locator('div[role="feed"]').count() == 0:
                                    details_panel = p
                                    found_panel = True
                                    break
                        except Exception:
                            pass
                    if found_panel:
                        break
                        
            # If not found by h1 name matching, fall back to checking for copy address/phone buttons
            if not found_panel:
                for p in panels:
                    if p.is_visible():
                        if p.locator('button[data-tooltip="Copy address"]').count() > 0 or p.locator('button[data-tooltip="Copy phone number"]').count() > 0:
                            if p.locator('div[role="feed"]').count() == 0:
                                details_panel = p
                                break
        except Exception:
            pass

        # Check for website indicators in the detailed view
        has_website = False
        website_url = ""
        
        def is_google_url(url):
            if not url:
                return False
            url_lower = url.lower()
            # Allow Google Sites (e.g. sites.google.com) as valid user-created websites
            if "sites.google.com" in url_lower:
                return False
            return "google." in url_lower or "gstatic." in url_lower or "ggpht." in url_lower
            
        # Indicator 1: data-tooltip="Open website" (could be a button or an anchor tag)
        website_el = details_panel.locator('*[data-tooltip="Open website"]').first
        if website_el.is_visible():
            href = website_el.get_attribute("href")
            if href and not is_google_url(href):
                has_website = True
                website_url = href
        
        # Indicator 2: data-item-id="authority" (could be a button or an anchor tag)
        if not has_website:
            website_el = details_panel.locator('*[data-item-id="authority"]').first
            if website_el.is_visible():
                href = website_el.get_attribute("href")
                if href and not is_google_url(href):
                    has_website = True
                    website_url = href
                
        # Indicator 3: General links containing http/https that aren't Google internal URLs
        if not has_website:
            links = details_panel.locator('a[href^="http"]').all()
            for link in links:
                href = link.get_attribute("href") or ""
                if not is_google_url(href):
                    has_website = True
                    website_url = href
                    break
                    
        if has_website:
            # Normalize website URL (lowercase, strip trailing slash) to prevent duplicates
            normalized_web = website_url.strip().lower()
            if normalized_web.endswith('/'):
                normalized_web = normalized_web[:-1]
                
            if seen_websites is not None:
                if normalized_web in seen_websites:
                    log_callback(f"-> Website already checked: {website_url}. Skipping...")
                    return None
                seen_websites.add(normalized_web)
                
            log_callback(f"-> Business has website: {website_url}. Skipping...")
            return None
            
        log_callback(f"-> Business has no website. Collecting lead '{name}'...")
        
        # Extract phone number
        phone = "Not listed"
        phone_el = details_panel.locator('button[data-tooltip="Copy phone number"]').first
        if phone_el.is_visible():
            aria = phone_el.get_attribute("aria-label")
            if aria and "Phone:" in aria:
                phone = aria.replace("Phone:", "").strip()
            else:
                phone = phone_el.text_content().strip() or phone
        else:
            phone_el2 = details_panel.locator('button[data-item-id^="phone:tel:"]').first
            if phone_el2.is_visible():
                aria = phone_el2.get_attribute("aria-label")
                if aria and "Phone:" in aria:
                    phone = aria.replace("Phone:", "").strip()
                else:
                    phone = phone_el2.text_content().strip() or phone
                    
        # Extract address
        address = "Not listed"
        address_el = details_panel.locator('button[data-tooltip="Copy address"]').first
        if address_el.is_visible():
            aria = address_el.get_attribute("aria-label")
            if aria and "Address:" in aria:
                address = aria.replace("Address:", "").strip()
            else:
                address = address_el.text_content().strip() or address
        else:
            address_el2 = details_panel.locator('button[data-item-id="address"]').first
            if address_el2.is_visible():
                aria = address_el2.get_attribute("aria-label")
                if aria and "Address:" in aria:
                    address = aria.replace("Address:", "").strip()
                else:
                    address = address_el2.text_content().strip() or address
                    
        log_callback(f"   Phone: {phone}")
        log_callback(f"   Address: {address}")
        
        # Query emails
        log_callback(f"   Searching for contact emails...")
        found_emails = find_emails(name, address)
        email_str = ", ".join(found_emails) if found_emails else "Not found"
        log_callback(f"   Emails: {email_str}")
        
        return {
            "Name": name,
            "Phone": phone,
            "Address": address,
            "Email": email_str,
            "Maps URL": page.url
        }
    except Exception as e:
        log_callback(f"Error extracting details: {e}")
        return None

def extract_unique_key(url):
    """
    Extract the unique business name token from the Google Maps place URL
    to prevent duplicate checks.
    E.g., 'https://www.google.com/maps/place/HRG+Construction/data=...'
    returns 'HRG+Construction'.
    """
    if not url:
        return ""
    try:
        # Try to extract the hex place ID (e.g., 0x3be04dec8170d7eb:0x4d6350f)
        match = re.search(r'0x[0-9a-fA-F]+:0x[0-9a-fA-F]+', url)
        if match:
            return match.group(0)
            
        if "/maps/place/" in url:
            parts = url.split("/maps/place/")
            if len(parts) > 1:
                sub_parts = parts[1].split("/")
                if len(sub_parts) > 0:
                    return sub_parts[0]
    except Exception:
        pass
    return url

def scrape_maps_leads(query, max_results=20, log_callback=None):
    """
    Search Google Maps for the query, and inspect listings sequentially.
    Keep searching, checking, and scrolling until we have successfully collected
    max_results leads that do not have websites, or we reach the end of the search results.
    """
    if log_callback is None:
        log_callback = print
        
    leads = []
    checked_urls = set()
    seen_websites = set()
    seen_names = set()
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/maps/search/{encoded_query}"
    
    log_callback("Starting browser automation...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        # Block images, media, and fonts to speed up page loading significantly
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
        
        log_callback(f"Opening Google Maps search URL: {url}")
        page.goto(url)
        page.wait_for_timeout(3000)
        
        # Check if Google Maps redirected directly to a single business page
        name_el = get_business_name_element(page)
        if name_el and name_el.is_visible() and not page.locator('div[role="feed"]').is_visible() and not page.locator('div.m6QErb[aria-label*="Results for"]').is_visible():
            log_callback("Direct single listing detail page loaded.")
            lead = extract_details(page, seen_websites=seen_websites, seen_names=seen_names, log_callback=log_callback)
            if lead:
                leads.append(lead)
            browser.close()
            return leads

        # Find results sidebar
        sidebar = page.locator('div[role="feed"]')
        if not sidebar.is_visible():
            sidebar = page.locator('div.m6QErb[aria-label*="Results for"]')
            
        if not sidebar.is_visible():
            log_callback("Results feed container not found. Check search term.")
            browser.close()
            return leads

        # Loop until we have collected the target number of leads or run out of listings
        scroll_attempts_without_new_cards = 0
        
        while len(leads) < max_results:
            # Get current listings in the sidebar
            cards = page.locator('a[href*="/maps/place/"]').all()
            
            # Find cards we haven't checked yet
            new_urls = []
            seen_in_batch = set()
            for card in cards:
                href = card.get_attribute("href")
                if href:
                    unique_key = extract_unique_key(href)
                    if unique_key and unique_key not in checked_urls and unique_key not in seen_in_batch:
                        new_urls.append((href, unique_key))
                        seen_in_batch.add(unique_key)
            
            if not new_urls:
                # No unchecked listings visible, scroll down the sidebar container
                log_callback("Scrolling sidebar to load more listings...")
                last_height = sidebar.evaluate('(el) => el.scrollHeight')
                sidebar.evaluate('(el) => el.scrollTop = el.scrollHeight')
                page.wait_for_timeout(3000)
                new_height = sidebar.evaluate('(el) => el.scrollHeight')
                
                # Check if we reached the absolute end of the scroll list
                if new_height == last_height:
                    scroll_attempts_without_new_cards += 1
                    if page.locator("text=You've reached the end of the list").is_visible() or scroll_attempts_without_new_cards >= 3:
                        log_callback("Reached the end of Google Maps results.")
                        break
                else:
                    scroll_attempts_without_new_cards = 0
                continue
                
            # Process the unchecked listings we found
            for card_url, unique_key in new_urls:
                if len(leads) >= max_results:
                    break
                    
                log_callback(f"Checking business {len(checked_urls)+1} (Found {len(leads)}/{max_results} website-less leads)...")
                checked_urls.add(unique_key)
                
                try:
                    # Get the current business name before clicking to detect when the detail panel actually changes
                    old_name = ""
                    try:
                        name_el = get_business_name_element(page)
                        if name_el and name_el.is_visible():
                            old_name = name_el.text_content().strip()
                    except Exception:
                        pass
                        
                    # Resolve card element dynamically to prevent stale references
                    # Strip any query parameters from card_url to make sure we match the exact DOM href
                    clean_url = card_url.split('?')[0]
                    path_index = clean_url.find("/maps/place/")
                    if path_index != -1:
                        relative_path = clean_url[path_index:]
                        card = page.locator(f'a[href*="{relative_path}"]').first
                    else:
                        card = page.locator(f'a[href*="{unique_key}"]').first
                    
                    # Scroll card into view and click it to open details panel
                    card.scroll_into_view_if_needed()
                    try:
                        card.click(timeout=3000)
                    except Exception:
                        try:
                            # Javascript fallback click
                            page.evaluate('(el) => el.click()', card)
                        except Exception:
                            card.click(force=True, timeout=3000)
                        
                    # Wait for the panel details to update (h1 changes and is not old_name)
                    panel_loaded = False
                    for _ in range(25):  # Poll every 200ms for up to 5 seconds
                        page.wait_for_timeout(200)
                        try:
                            new_name_el = get_business_name_element(page)
                            if new_name_el and new_name_el.is_visible():
                                new_name = new_name_el.text_content().strip()
                                if new_name and new_name != old_name:
                                    panel_loaded = True
                                    break
                        except Exception:
                            pass
                            
                    if not panel_loaded:
                        log_callback("-> Details panel did not update in time. Skipping to avoid duplicate data...")
                        continue
                    
                    lead = extract_details(page, seen_websites=seen_websites, seen_names=seen_names, log_callback=log_callback)
                    if lead:
                        leads.append(lead)
                        log_callback(f"🎉 Lead added! Total: {len(leads)}/{max_results}")
                except Exception as e:
                    log_callback(f"Error checking listing: {e}")
                    
        browser.close()
        
    return leads
