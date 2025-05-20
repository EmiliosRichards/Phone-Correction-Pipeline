import asyncio
import os
import re
import logging
import time
import hashlib # Added for hashing long filenames
from urllib.parse import urljoin, urlparse, urldefrag
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from bs4 import BeautifulSoup
from bs4.element import Tag # Added for type checking
import httpx # For asynchronous robots.txt checking
from urllib.robotparser import RobotFileParser
from typing import Set, Tuple, Optional, List, Dict, Any
# from datetime import datetime # No longer needed after commenting out _test_scraper

# Assuming config.py is in src.core
from ..core.config import AppConfig
from ..core.logging_config import setup_logging # For main app setup, or test setup

# Instantiate AppConfig for scraper_logic
# This assumes that when scraper_logic is imported and used,
# the .env file has been loaded appropriately by the main application entry point
# or by AppConfig itself.
config_instance = AppConfig()

# Setup logger for this module
logger = logging.getLogger(__name__)

def normalize_url(url: str) -> str:
    """
    Normalizes a URL to a canonical form.
    - Removes fragments.
    - Converts scheme and netloc to lowercase.
    - Removes 'www.' prefix from netloc.
    - Removes common index file names from path (e.g., /index.html -> /).
    - Removes trailing slash from path (unless path is just '/').
    - Sorts query parameters.
    """
    try:
        # Remove fragment first
        url_no_frag, _ = urldefrag(url)
        parsed = urlparse(url_no_frag)

        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        
        path = parsed.path
        # Remove common index files
        common_indexes = ['index.html', 'index.htm', 'index.php', 'default.html', 'default.htm', 'index.asp', 'default.asp']
        for index_file in common_indexes:
            if path.endswith(f'/{index_file}'):
                path = path[:-len(index_file)] # /path/to/index.html -> /path/to/
                break
        
        # Ensure path starts with / if there's a netloc and path is not empty and not already starting with /
        if netloc and path and not path.startswith('/'):
            path = '/' + path

        # Remove trailing slash if path is not just '/'
        if path != '/' and path.endswith('/'):
            path = path[:-1]
        
        # If path is empty after processing (e.g. http://domain.com/index.html became http://domain.com)
        # ensure it's at least '/' for consistency if there's a netloc
        if not path and netloc:
            path = '/'
        
        # Sort query parameters and filter out unwanted ones
        query = ''
        if parsed.query:
            params = parsed.query.split('&')
            # Define parameters to ignore (case-insensitive for parameter name)
            ignored_params = {'fallback'}
            
            filtered_params = []
            for p in params:
                if '=' in p:
                    param_name = p.split('=')[0].lower()
                    if param_name not in ignored_params:
                        filtered_params.append(p)
                else: # parameter without a value
                    if p.lower() not in ignored_params:
                        filtered_params.append(p)
            
            if filtered_params:
                query = '&'.join(sorted(filtered_params))

        return urlparse('')._replace(
            scheme=scheme,
            netloc=netloc,
            path=path,
            params=parsed.params, # Usually empty, part of path before query
            query=query,
            fragment='' # Explicitly empty
        ).geturl()
    except Exception as e:
        logger.error(f"Error normalizing URL '{url}': {e}. Returning original URL.", exc_info=True)
        return url # Fallback to original URL on error

# Helper function to create a safe filename from a URL or company name
def get_safe_filename(name_or_url: str, for_url: bool = False, max_len: int = 100) -> str:
    if for_url:
        logger.info(f"get_safe_filename (for_url=True): Input for filename generation='{name_or_url}'") # Elevated to INFO
    """
    Creates a filesystem-safe filename from a string.
    For URLs, it prioritizes a short, hash-based name to avoid path length issues.

    Args:
        name_or_url (str): The input string (company name or URL).
        for_url (bool): If True, generates a short, hash-based name for the URL.
        max_len (int): The target maximum length for the filename component.
                       This is more of a guideline, especially for hashed URLs.

    Returns:
        str: A filesystem-safe version of the input string.
    """
    original_input = name_or_url
    
    if for_url:
        # For URLs, always use a hash to keep it short and predictable in length.
        # Prefix with a very short, sanitized domain part for some readability if possible.
        parsed_original_url = urlparse(original_input)
        domain_part = re.sub(r'^www\.', '', parsed_original_url.netloc) # Remove www.
        domain_part = re.sub(r'[^\w-]', '', domain_part) # Keep only alphanumeric and hyphen from domain
        domain_prefix = domain_part[:15] # Max 15 chars from domain
        
        url_hash = hashlib.sha256(original_input.encode('utf-8')).hexdigest()[:16] # 16-char hash
        safe_name = f"{domain_prefix}_{url_hash}"
        # This will result in a name like "domaincom_abcdef1234567890" (approx 15 + 1 + 16 = 32 chars)
        # which is very safe for the URL component of a filename.
        # max_len for URLs will be mostly governed by this structure rather than aggressive truncation.
        logger.debug(f"Generated safe filename for URL '{original_input}': {safe_name}")
        return safe_name # Return directly, max_len is less critical here due to fixed hash length
    else:
        # For non-URLs (like company names)
        name_or_url = re.sub(r'^https?://', '', name_or_url) # Should not happen if for_url=False, but safe
        safe_name = re.sub(r'[^\w.-]', '_', name_or_url)
        return safe_name[:max_len] # Truncate company name if needed

async def fetch_page_content(page, url: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Asynchronously fetches the HTML content of a single web page using Playwright.

    Navigates to the given URL, waits for the DOM content to be loaded,
    and optionally waits for network idle.

    Args:
        page (playwright.async_api.Page): The Playwright Page object to use for navigation.
        url (str): The URL of the page to fetch.

    Returns:
        Tuple[Optional[str], Optional[int]]: A tuple containing:
            - str: The HTML content of the page if successful.
            - None: If fetching failed or an error occurred.
            And
            - int: The HTTP status code of the response if available.
            - Special negative int codes for specific errors:
                - -1: TimeoutError during navigation.
                - -2: DNS error (net::ERR_NAME_NOT_RESOLVED).
                - -3: Connection refused (net::ERR_CONNECTION_REFUSED).
                - -4: Other PlaywrightError.
                - -5: Unexpected generic exception.
            - None: If no response object was obtained.
    """
    logger.debug(f"Attempting to navigate to: {url}")
    try:
        response = await page.goto(url, timeout=config_instance.default_navigation_timeout, wait_until='domcontentloaded')
        if response:
            logger.debug(f"Successfully navigated to {url}, status: {response.status}")
            if response.ok:
                if config_instance.scraper_networkidle_timeout_ms > 0:
                    try:
                        logger.debug(f"Waiting for networkidle on {url} with timeout {config_instance.scraper_networkidle_timeout_ms}ms")
                        await page.wait_for_load_state('networkidle', timeout=config_instance.scraper_networkidle_timeout_ms)
                    except PlaywrightTimeoutError:
                        logger.warning(f"Timeout waiting for networkidle on {url} after {config_instance.scraper_networkidle_timeout_ms}ms, proceeding with DOM content.")
                else:
                    logger.debug(f"Skipping networkidle wait for {url} as timeout is set to 0 or less.")
                
                content = await page.content()
                return content, response.status
            else:
                logger.warning(f"HTTP error for {url}: {response.status} {response.status_text}")
                return None, response.status
        else:
            logger.error(f"Failed to get a response object for {url}")
            return None, None
    except PlaywrightTimeoutError:
        logger.error(f"Timeout error navigating to {url} after {config_instance.default_navigation_timeout / 1000}s")
        return None, -1
    except PlaywrightError as e:
        logger.error(f"Playwright error navigating to {url}: {e}")
        if "net::ERR_NAME_NOT_RESOLVED" in str(e):
            return None, -2 
        elif "net::ERR_CONNECTION_REFUSED" in str(e):
            return None, -3 
        return None, -4 
    except Exception as e:
        logger.error(f"Unexpected error fetching page {url}: {e}")
        return None, -5 

def extract_text_from_html(html_content: str) -> str:
    """
    Extracts and cleans visible text content from an HTML string.

    Uses BeautifulSoup to parse the HTML, removes script and style tags,
    and then extracts text. Multiple whitespace characters are condensed
    into single spaces.

    Args:
        html_content (str): The HTML content as a string.

    Returns:
        str: The extracted and cleaned plain text. Returns an empty string
             if the input HTML is empty or None.
    """
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    text = soup.get_text(separator=' ', strip=True)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def find_internal_links(html_content: str, base_url: str) -> Set[str]:
    """
    Finds internal links within HTML content that match configured keywords.

    Parses the HTML to find all 'a' tags with 'href' attributes.
    It resolves relative URLs to absolute URLs based on the `base_url`.
    A link is considered internal if its domain matches the `base_url`'s domain.
    It's considered relevant if the link text or the href itself contains
    any of the keywords specified in `config_instance.target_link_keywords`.

    Args:
        html_content (str): The HTML content to parse for links.
        base_url (str): The base URL of the page from which the HTML was fetched,
                        used to resolve relative links and determine domain.

    Returns:
        Set[str]: A set of unique, absolute internal URLs that match the criteria.
                  Returns an empty set if input HTML is empty or no relevant links are found.
    """
    if not html_content:
        return set()
    soup = BeautifulSoup(html_content, 'html.parser')
    internal_links = set()
    parsed_base_url = urlparse(base_url)
    for link in soup.find_all('a', href=True):
        # Ensure the link object is a Tag before accessing attributes like 'href' or 'get_text'.
        # This addresses Pylance concerns about 'link' potentially being PageElement/NavigableString.
        if not isinstance(link, Tag):
            logger.debug(f"Skipping element of type {type(link).__name__} in find_internal_links as it's not a Tag.")
            continue

        href_attr = link.get('href') # For Tag, .get('href') is appropriate.
                                     # For 'href' attribute, it's typically a str.
        
        current_href: Optional[str] = None
        if isinstance(href_attr, str):
            current_href = href_attr
        elif isinstance(href_attr, list) and href_attr and isinstance(href_attr[0], str):
            # If href_attr is a list of strings (unlikely for 'href' but possible), take the first one.
            current_href = href_attr[0]

        # Get link text safely
        link_text_content = link.get_text()
        if not isinstance(link_text_content, str): # Should be str, but defensive check
            link_text_content = ""
        link_text = link_text_content.lower().strip()

        # Check if keywords are in link_text
        text_keyword_found = any(keyword in link_text for keyword in config_instance.target_link_keywords)
        
        href_keyword_found = False
        # Only check href for keywords if current_href is a valid string
        if current_href:
            href_keyword_found = any(keyword in current_href.lower() for keyword in config_instance.target_link_keywords)

        # If neither text nor href (if valid) contains keywords, skip this link
        if not (text_keyword_found or href_keyword_found):
            continue

        # To form an absolute URL, we must have a valid current_href.
        # This handles cases where only text_keyword_found was true, but href itself is missing/invalid.
        if not current_href:
            continue
            
        # At this point, current_href is guaranteed to be a non-empty string.
        absolute_url_raw = urljoin(base_url, current_href)
        # Normalize before adding to set and for further checks
        normalized_link = normalize_url(absolute_url_raw)
        
        parsed_normalized_link = urlparse(normalized_link)
        # Compare netloc of normalized link with netloc of normalized base_url for consistency
        normalized_base_url_netloc = urlparse(normalize_url(base_url)).netloc

        if parsed_normalized_link.netloc == normalized_base_url_netloc:
            if parsed_normalized_link.scheme in ['http', 'https']:
                logger.info(f"find_internal_links: Raw='{absolute_url_raw}', Norm='{normalized_link}', Base='{base_url}' -> ADDING") # Elevated
                internal_links.add(normalized_link)
            else:
                logger.debug(f"find_internal_links: Raw='{absolute_url_raw}', Norm='{normalized_link}' -> SKIP (scheme)")
        else:
            logger.debug(f"find_internal_links: Raw='{absolute_url_raw}', Norm='{normalized_link}' -> SKIP (netloc)")
            
    logger.info(f"Found {len(internal_links)} relevant internal links (normalized) from {base_url}") # Already INFO
    return internal_links

async def is_allowed_by_robots(url: str, client: httpx.AsyncClient) -> bool:
    """
    Asynchronously checks if scraping the given URL is allowed by its robots.txt file.

    If `config_instance.respect_robots_txt` is False, this check is skipped and
    always returns True. Otherwise, it fetches and parses the robots.txt file
    from the URL's domain and checks if the `config_instance.robots_txt_user_agent`
    is permitted to fetch the given URL. Uses the provided httpx.AsyncClient.

    Args:
        url (str): The URL to check against robots.txt.
        client (httpx.AsyncClient): An active httpx client instance.

    Returns:
        bool: True if scraping is allowed (or if robots.txt check is disabled,
              robots.txt not found, or an error occurs fetching/parsing it).
              False if robots.txt explicitly disallows scraping for the user-agent.
    """
    if not config_instance.respect_robots_txt:
        logger.debug("robots.txt check is disabled.")
        return True
    
    parsed_url = urlparse(url)
    robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
    rp = RobotFileParser()
    # rp.set_url(robots_url) # Not strictly necessary if we pass content directly to parse()

    try:
        logger.debug(f"Fetching robots.txt from: {robots_url}")
        response = await client.get(robots_url, timeout=10, headers={'User-Agent': config_instance.robots_txt_user_agent})
        
        if response.status_code == 200:
            logger.debug(f"Successfully fetched robots.txt for {url}, status: {response.status_code}")
            rp.parse(response.text.splitlines())
        elif response.status_code == 404:
            logger.debug(f"robots.txt not found at {robots_url} (status 404), assuming allowed.")
            return True
        else:
            logger.warning(f"Failed to fetch robots.txt from {robots_url}, status: {response.status_code}. Assuming allowed.")
            return True
    except httpx.RequestError as e:
        logger.warning(f"httpx.RequestError fetching robots.txt from {robots_url}: {e}. Assuming allowed.")
        return True
    except Exception as e: # Catch any other unexpected errors during robots.txt processing
        logger.error(f"Unexpected error processing robots.txt for {robots_url}: {e}. Assuming allowed.", exc_info=True)
        return True

    allowed = rp.can_fetch(config_instance.robots_txt_user_agent, url)
    if not allowed:
        logger.info(f"Scraping disallowed by robots.txt for URL: {url} (User-agent: {config_instance.robots_txt_user_agent})")
    else:
        logger.debug(f"Scraping allowed by robots.txt for URL: {url}")
    return allowed

async def scrape_website(
    given_url: str,
    output_dir_for_run: str,
    company_name_or_id: str,
    globally_processed_urls: Set[str]
) -> Tuple[List[Tuple[str, str]], str, Optional[str]]:
    """
    Asynchronously scrapes a website starting from a given URL to extract text content.
    Uses and updates a globally managed set of processed URLs to prevent re-scraping
    common pages linked from different initial company URLs.

    It first checks `robots.txt` if enabled. It then navigates to the `given_url`,
    extracts its text content, and optionally finds and scrapes relevant internal
    pages up to `config_instance.max_depth_internal_links`. Text from each
    successfully scraped page is saved to a separate file.

    Args:
        given_url (str): The initial URL of the website to scrape. Must start
                         with 'http://' or 'https://'.
        output_dir_for_run (str): The base directory path for the current pipeline run.
                                  A subdirectory for scraped content, and then another
                                  for individual pages, will be created within this path.
        company_name_or_id (str): A name or identifier for the company/website being
                                  scraped, used for generating safe filenames.
        globally_processed_urls (Set[str]): A set of URLs that have already been processed
                                           in the broader pipeline run, to avoid redundant
                                           scraping of the same canonical sites.

    Returns:
        Tuple[List[Tuple[str, str]], str, Optional[str]]: A tuple containing:
            - List[Tuple[str, str]]: A list of (file_path, source_url) tuples for each
                                     successfully scraped page.
            - str: A status string indicating the outcome (e.g., "Success", "TimeoutError").
            - Optional[str]: The final canonical URL of the entry point after all redirects,
                             or None if the initial navigation failed.
                - "Success": Scraping completed and at least one page's content saved.
                - "InvalidURL": The provided `given_url` was invalid.
                - "RobotsDisallowed": Scraping was disallowed by `robots.txt`.
                - "TimeoutError": Playwright timeout fetching the initial URL.
                - "DNSError": DNS resolution failed for the initial URL.
                - "ConnectionRefused": Connection was refused for the initial URL.
                - "PlaywrightError": Other Playwright error for the initial URL.
                - "HTTPError_XXX": HTTP error (XXX is status code) for initial URL.
                - "GenericScrapeError": A generic error during scraping.
                - "NoStatusFromServer": No HTTP status obtained for initial URL.
                - "UnknownScrapeErrorCode": An unknown error code from fetch_page_content.
                - "FileSaveError": An IOError occurred while saving the content.
                - "NoContentScraped": Scraping seemed to work but no text content was extracted.
                - "GeneralScrapingError_ExceptionName": A general exception occurred.
                - "UnexpectedScraperFailure": An unexpected failure point was reached.

    Raises:
        Logs various informational, warning, and error messages throughout the process.
        Handles Playwright exceptions, requests exceptions, and IOErrors internally.
    """
    start_time = time.time()
    final_canonical_entry_url: Optional[str] = None # Initialize here
    logger.info(f"Starting scrape for URL: {given_url} (Company: {company_name_or_id})")

    # URL validation is now expected to happen in the calling function (e.g., main_pipeline.py)
    # This function assumes given_url is already processed and validated.

    normalized_given_url = normalize_url(given_url)
    logger.info(f"Original given_url: '{given_url}', Normalized to: '{normalized_given_url}'")

    if not normalized_given_url or not isinstance(normalized_given_url, str) or not normalized_given_url.startswith(('http://', 'https://')):
        logger.warning(f"Scraper received an invalid or improperly formatted URL after normalization: {normalized_given_url} (original: {given_url})")
        return [], "InvalidURL", None

    # Create httpx client session to be used for robots.txt
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        if not await is_allowed_by_robots(normalized_given_url, client):
            return [], "RobotsDisallowed", None # Return None for canonical if disallowed

    # Directory for storing individual page content files
    # Parent: output_dir_for_run / config_instance.scraped_content_subdir
    # Child: individual_pages
    base_scraped_content_dir = os.path.join(output_dir_for_run, config_instance.scraped_content_subdir)
    individual_pages_storage_dir = os.path.join(base_scraped_content_dir, "individual_pages_raw_text") # Renamed for clarity
    os.makedirs(individual_pages_storage_dir, exist_ok=True)
    cleaned_pages_storage_dir = os.path.join(base_scraped_content_dir, "cleaned_pages_text") # New directory for cleaned text
    os.makedirs(cleaned_pages_storage_dir, exist_ok=True)
    
    company_safe_name = get_safe_filename(
        company_name_or_id,
        for_url=False,
        max_len=config_instance.filename_company_name_max_len # Use the new config value
    )
 
    scraped_page_details: List[Tuple[str, str]] = [] # To store (file_path, source_url)
    # processed_urls = set() # Removed: Will use globally_processed_urls
    urls_to_scrape = [(normalized_given_url, 0)] # Start with the normalized URL
    
    # Keep a local set for URLs processed *within this specific call* to scrape_website
    # to handle internal links of the *current* site efficiently if MAX_DEPTH > 0,
    # without repeatedly checking the potentially larger globally_processed_urls for every internal link consideration.
    # The globally_processed_urls is checked for the *landed URL* before saving/processing content.
    # Internal links found are checked against globally_processed_urls before adding to queue.
    
    browser = None # Initialize browser to None
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            context = await browser.new_context(
                user_agent=config_instance.user_agent,
                java_script_enabled=True,
                ignore_https_errors=True
            )
            page = await context.new_page()
            page.set_default_timeout(config_instance.default_page_timeout) # This method is synchronous
            
            # Using a while loop for potentially multiple pages (initial + sub-pages)
            while urls_to_scrape:
                current_url, current_depth = urls_to_scrape.pop(0)
                # current_url_from_queue is the URL we intended to visit (already normalized)
                current_url_from_queue = current_url
                
                # Log conditions for setting canonical URL
                logger.info(f"SCRAPER_DBG: Pre-check for setting canonical_url for {company_name_or_id} (depth {current_depth}): "
                            f"current_url_from_queue='{current_url_from_queue}'") # status_code and html_content logged after fetch
                
                logger.info(f"Attempting to scrape page (from queue): {current_url_from_queue} (Depth: {current_depth})")
                html_content, status_code = await fetch_page_content(page, current_url_from_queue)

                logger.info(f"SCRAPER_DBG: Post-fetch for {current_url_from_queue}: html_content_is_not_None='{html_content is not None}', status_code='{status_code}'")

                if html_content:
                    # IMPORTANT: Get the URL after any redirects. This is the actual page we landed on.
                    final_landed_url_raw = page.url
                    final_landed_url_normalized = normalize_url(final_landed_url_raw)
                    
                    logger.info(f"Page navigation report: Requested='{current_url_from_queue}', LandedRaw='{final_landed_url_raw}', LandedNormalized='{final_landed_url_normalized}'")

                    # Try to set the canonical entry URL on the first successful scrape of the *entry point*
                    if not final_canonical_entry_url and final_landed_url_normalized and current_depth == 0:
                        final_canonical_entry_url = final_landed_url_normalized
                        logger.info(f"SUCCESS: Canonical entry URL for {company_name_or_id} SET to: {final_canonical_entry_url} (at depth {current_depth})")
                    
                    # De-duplication logic now uses the final_landed_url_normalized against the global set
                    if final_landed_url_normalized in globally_processed_urls:
                        logger.info(f"Landed URL '{final_landed_url_normalized}' (from requested '{current_url_from_queue}') is in globally_processed_urls. Skipping content save and link finding.")
                        continue # Skip to the next URL in urls_to_scrape
                    
                    globally_processed_urls.add(final_landed_url_normalized) # Add to the *global* set

                    cleaned_text = extract_text_from_html(html_content)
                    
                    # Generate safe filename based on the final_landed_url_normalized
                    landed_url_safe_name = get_safe_filename(final_landed_url_normalized, for_url=True)
                    
                    cleaned_page_filename = f"{company_safe_name}__{landed_url_safe_name}_cleaned.txt"
                    cleaned_page_filepath = os.path.join(cleaned_pages_storage_dir, cleaned_page_filename)
                    
                    try:
                        with open(cleaned_page_filepath, 'w', encoding='utf-8') as f_cleaned_page:
                            f_cleaned_page.write(cleaned_text)
                        logger.info(f"Saved cleaned text from '{final_landed_url_normalized}' (requested as '{current_url_from_queue}') to {cleaned_page_filepath}")
                        # Store details using the final landed URL as the source_url
                        scraped_page_details.append((cleaned_page_filepath, final_landed_url_normalized))
                    except IOError as e:
                        logger.error(f"IOError saving cleaned text for '{final_landed_url_normalized}' to {cleaned_page_filepath}: {e}")

                    if current_depth < config_instance.max_depth_internal_links:
                        # Use final_landed_url_normalized as the base for finding internal links
                        internal_links = find_internal_links(html_content, final_landed_url_normalized)
                        logger.info(f"Found {len(internal_links)} relevant internal links on '{final_landed_url_normalized}'")
                        for link in internal_links: # 'link' here is already normalized by find_internal_links
                            is_globally_processed_check = link in globally_processed_urls # Use the global set
                            # Check if the *target* of the link (which is 'link') is already in the queue
                            is_in_queue = any(item[0] == link for item in urls_to_scrape)
                            
                            logger.info(f"scrape_website: Considering internal link '{link}'. Globally Processed: {is_globally_processed_check}. In queue: {is_in_queue}.")

                            if not is_globally_processed_check and not is_in_queue:
                                urls_to_scrape.append((link, current_depth + 1))
                                logger.info(f"Queued internal link: {link} (Depth: {current_depth + 1})")
                            else:
                                logger.info(f"scrape_website: Internal link '{link}' was NOT queued. Globally Processed: {is_globally_processed_check}, In queue: {is_in_queue}.") # Corrected variable name
                else:
                    # This 'current_url' is current_url_from_queue
                    logger.error(f"Failed to fetch content from '{current_url_from_queue}' (normalized, as requested), status: {status_code}")
                    # Check if it was the initial URL that failed (compare normalized versions)
                    if current_url_from_queue == normalized_given_url:
                        status_map = {
                            -1: "TimeoutError", -2: "DNSError", -3: "ConnectionRefused",
                            -4: "PlaywrightError", -5: "GenericScrapeError"
                        }
                        http_status_report = "UnknownScrapeError"
                        if status_code is not None:
                            if status_code > 0: http_status_report = f"HTTPError_{status_code}"
                            elif status_code in status_map: http_status_report = status_map[status_code]
                            else: http_status_report = "UnknownScrapeErrorCode"
                        else: http_status_report = "NoStatusFromServer"
                        return [], http_status_report, final_canonical_entry_url # Return with canonical URL (likely None here)

            # After the loop
            if scraped_page_details:
                logger.info(f"Successfully scraped {len(scraped_page_details)} page(s) for {company_name_or_id}.")
                total_time = time.time() - start_time
                logger.info(f"Total scraping for {company_name_or_id} took {total_time:.2f} seconds.")
                return scraped_page_details, "Success", final_canonical_entry_url
            else:
                # This case is reached if the initial URL was fine but yielded no content,
                # or if subpages were attempted but all failed or yielded no content.
                # If initial URL itself failed, it's handled inside the loop.
                logger.warning(f"No content successfully scraped and saved for {given_url} and its subpages.")
                return [], "NoContentScraped", final_canonical_entry_url

        except Exception as e:
            logger.error(f"General error during Playwright scraping process for {given_url}: {e}", exc_info=True)
            # Log before returning in this exception case
            logger.info(f"SCRAPER_DBG: Exiting scrape_website (Exception branch) for {company_name_or_id}. "
                        f"Returning: status='GeneralScrapingError_{type(e).__name__}', "
                        f"final_canonical_entry_url='{final_canonical_entry_url}'")
            return [], f"GeneralScrapingError_{type(e).__name__}", final_canonical_entry_url
        finally:
            if browser and browser.is_connected():
                logger.debug("Closing browser in finally block.")
                await browser.close()
    
    # This fallback should ideally not be reached if the logic above is complete.
    # It covers cases where the async with block might not even start or other pre-Playwright issues.
    logger.error(f"Scraping ended unexpectedly for {given_url}.")
    # Log before this final fallback return
    logger.info(f"SCRAPER_DBG: Exiting scrape_website (Fallback UnexpectedScraperFailure) for {company_name_or_id}. "
                f"Returning: status='UnexpectedScraperFailure', "
                f"final_canonical_entry_url='{final_canonical_entry_url}' (this should be None if this path is hit early)")
    return [], "UnexpectedScraperFailure", final_canonical_entry_url


# TODO: [FutureEnhancement] The _test_scraper function below was for demonstrating and testing
# the scrape_website functionality directly. It includes setup for logging and test output.
# Commented out as it's not part of the main pipeline execution.
# It can be uncommented for debugging or standalone testing of the scraper logic.
# async def _test_scraper():
#     """
#     An asynchronous test function to demonstrate and test the `scrape_website` functionality.
#
#     Sets up logging, defines a test URL and output directory, then calls
#     `scrape_website` and logs the result. This function is intended to be run
#     when the script is executed directly (`if __name__ == "__main__":`).
#     """
#     setup_logging(logging.DEBUG) # Setup logging for test
#     logger.info("Starting test scraper...") # Use the module logger
#
#     test_url = "https://www.example.com" # A simple, reliable URL for testing
#     # test_url = "https://www.python.org" # Another option
#     # test_url = "https://nonexistent-domain-for-testing123.com" # To test DNS error
#
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     project_root = os.path.dirname(os.path.dirname(script_dir))
#     test_output_base = os.path.join(project_root, "test_output_data")
#     # test_run_id = datetime.now().strftime("%Y%m%d_%H%M%S") # Unique test run - requires datetime import
#     test_run_id = "test_run_manual" # Using a fixed ID as datetime is commented out
#     test_run_output_dir = os.path.join(test_output_base, test_run_id)
#     os.makedirs(os.path.join(test_run_output_dir, config_instance.scraped_content_subdir), exist_ok=True)
#
#     logger.info(f"Test output directory: {test_run_output_dir}")
#
#     file_path, status = await scrape_website(test_url, test_run_output_dir, "example_company_test")
#
#     if file_path:
#         logger.info(f"Test successful: Content saved to {file_path}, Status: {status}")
#     else:
#         logger.error(f"Test failed: Status: {status}")

# TODO: [FutureEnhancement] The __main__ block below allowed direct execution of _test_scraper.
# Commented out as it's not intended for execution during normal library use.
# if __name__ == "__main__":
#     if not logger.hasHandlers(): # Ensure logger is configured if run directly
#         setup_logging(logging.INFO) # Use the setup_logging function
#         # logger = logging.getLogger(__name__) # Not needed, setup_logging configures root or named loggers if adapted
#     asyncio.run(_test_scraper())