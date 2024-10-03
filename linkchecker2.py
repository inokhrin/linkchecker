import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import csv
import os
import pickle

def is_valid_url(url):
    """Check if the URL is valid and has a scheme and netloc."""
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)

def is_same_or_subpath(url, base_url):
    """Check if the URL belongs to the same base path or a subpath."""
    return url.startswith(base_url)

def is_html(response):
    """Check if the content type of the response is HTML."""
    content_type = response.headers.get('Content-Type', '')
    return "text/html" in content_type

def check_link(url):
    """Check if the link is working or broken."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return "Working"
        else:
            return "Broken"
    except requests.exceptions.RequestException:
        return "Broken"

def extract_menu_links(url):
    """Extract menu links from the main page."""
    try:
        response = requests.get(url)
        if not is_html(response):
            return set()

        soup = BeautifulSoup(response.text, "html.parser")
        links = set()

        nav_tags = soup.find_all("nav")
        for nav in nav_tags:
            for link in nav.find_all("a", href=True):
                full_url = urljoin(url, link["href"])
                if is_valid_url(full_url):
                    links.add(full_url)

        return links

    except requests.exceptions.RequestException as e:
        print(f"Error accessing {url}: {e}")
        return set()

def get_body_links(url, base_url, menu_links):
    """Retrieve links from the body of the web page if it's HTML, excluding menu links."""
    try:
        response = requests.get(url)
        
        if not is_html(response):
            return set()

        soup = BeautifulSoup(response.text, "html.parser")
        links = set()

        for link in soup.find_all("a", href=True):
            full_url = urljoin(url, link["href"])
            if is_valid_url(full_url) and full_url not in menu_links:
                links.add((url, full_url))  # Store (source_page, link) as a tuple

        return links

    except requests.exceptions.RequestException as e:
        print(f"Error accessing {url}: {e}")
        return set()

def save_state(visited_pages, links_to_crawl):
    """Save the current state of the crawl to a file."""
    with open('crawl_state.pkl', 'wb') as f:
        pickle.dump((visited_pages, links_to_crawl), f)

def load_state():
    """Load the saved state of the crawl from a file."""
    if os.path.exists('crawl_state.pkl'):
        with open('crawl_state.pkl', 'rb') as f:
            return pickle.load(f)
    return set(), set()

def crawl_website(start_url, base_url, csv_filename, record_only_broken):
    """Crawl the website, check all links, and save results to a CSV file."""
    visited_pages, links_to_crawl = load_state()
    
    # If starting fresh, add the start_url
    if not visited_pages and not links_to_crawl:
        links_to_crawl.add(start_url)

    # Extract and check menu links only once from the start page
    if not visited_pages:  # Only extract menu links at the beginning
        menu_links = extract_menu_links(start_url)
        menu_results = []

        for menu_link in menu_links:
            status = check_link(menu_link)
            menu_results.append((start_url, menu_link, status))
            print(f"{status}: {menu_link} (found in menu on {start_url})")

        with open(csv_filename, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Source Page", "Link URL", "Status"])
            for result in menu_results:
                if not record_only_broken or result[2] == "Broken":
                    writer.writerow(result)
    else:
        # If resuming, assume menu links have already been checked
        menu_links = set()

    count_links = 0

    while links_to_crawl:
        current_page = links_to_crawl.pop()

        if current_page not in visited_pages and is_same_or_subpath(current_page, base_url):
            visited_pages.add(current_page)
            print(f"Crawling and checking links on: {current_page}")

            page_links = get_body_links(current_page, base_url, menu_links)

            with open(csv_filename, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)

                for source_page, link_url in page_links:
                    # Skip links starting with "https://library2.utm.utoronto.ca/otra/reed/tagged-records"
                    if link_url.startswith("https://library2.utm.utoronto.ca/otra/reed/tagged-records"):
                        continue

                    status = check_link(link_url)
                    count_links += 1
                    print(f"{status}: {link_url} (found on {source_page})")

                    if not record_only_broken or status == "Broken":
                        writer.writerow([source_page, link_url, status])

                    if is_same_or_subpath(link_url, base_url) and link_url not in visited_pages:
                        links_to_crawl.add(link_url)

            # Save state after each page to handle interruptions
            save_state(visited_pages, links_to_crawl)

    print(f"Total number of links checked: {count_links}")

if __name__ == "__main__":
    start_url = "https://library2.utm.utoronto.ca/otra/reed/"
    base_url = "https://library2.utm.utoronto.ca/otra/reed/"
    csv_filename = "broken_links_report2.csv"
    record_only_broken = True  # Set to False if you want to record all links

    crawl_website(start_url, base_url, csv_filename, record_only_broken)
    print(f"Results saved to {csv_filename}")
