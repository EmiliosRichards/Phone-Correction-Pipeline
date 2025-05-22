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

# Assuming config.py is in src.core
from ..core.config import AppConfig
from ..core.logging_config import setup_logging # For main app setup, or test setup

# Instantiate AppConfig for scraper_logic
config_instance = AppConfig()

# Setup logger for this module
logger = logging.getLogger(__name__)

def normalize_url(url: str) -> str:
    """
    Normalizes a URL to a canonical form.
    """
    try:
        url_no_frag, _ = urldefrag(url)
        parsed = urlparse(url_no_frag)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = parsed.path
        common_indexes = ['index.html', 'index.htm', 'index.php', 'default.html', 'default.htm', 'index.asp', 'default.asp']
        for index_file in common_indexes:
            if path.endswith(f'/{index_file}'):
                path = path[:-len(index_file)]
                break
        if netloc and path and not path.startswith('/'):
            path = '/' + path
        if path != '/' and path.endswith('/'):
            path = path[:-1]
        if not path and netloc:
            path = '/'
        query = ''
        if parsed.query:
            params = parsed.query.split('&')
            ignored_params = {'fallback'}
            filtered_params = [p for p in params if (p.split('=')[0].lower() if '=' in p else p.lower()) not in ignored_params]
            if filtered_params:
                query = '&'.join(sorted(filtered_params))
        return urlparse('')._replace(scheme=scheme, netloc=netloc, path=path, params=parsed.params, query=query, fragment='').geturl()
    except Exception as e:
        logger.error(f"Error normalizing URL '{url}': {e}. Returning original URL.", exc_info=True)
        return url

def get_safe_filename(name_or_url: str, for_url: bool = False, max_len: int = 100) -> str:
    if for_url:
        logger.info(f"get_safe_filename (for_url=True): Input for filename generation='{name_or_url}'")
    original_input = name_or_url
    if for_url:
        parsed_original_url = urlparse(original_input)
        domain_part = re.sub(r'^www\.', '', parsed_original_url.netloc)
        domain_part = re.sub(r'[^\w-]', '', domain_part)[:15] # Ensure domain_prefix is defined before use
        url_hash = hashlib.sha256(original_input.encode('utf-8')).hexdigest()[:16]
        safe_name = f"{domain_part}_{url_hash}" # Use the sanitized domain_part
        logger.info(f"DEBUG PATH: get_safe_filename (for_url=True) output: '{safe_name}' from input '{original_input}'") # DEBUG PATH LENGTH
        return safe_name
    else:
        name_or_url = re.sub(r'^https?://', '', name_or_url)
        safe_name = re.sub(r'[^\w.-]', '_', name_or_url)
        safe_name_truncated = safe_name[:max_len]
        logger.info(f"DEBUG PATH: get_safe_filename (for_url=False) output: '{safe_name_truncated}' (original sanitized: '{safe_name}', max_len: {max_len}) from input '{original_input}'") # DEBUG PATH LENGTH
        return safe_name_truncated

async def fetch_page_content(page, url: str, input_row_id: Any, company_name_or_id: str) -> Tuple[Optional[str], Optional[int]]:
    logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Navigating to URL: {url}")
    try:
        response = await page.goto(url, timeout=config_instance.default_navigation_timeout, wait_until='domcontentloaded')
        if response:
            logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Navigation to {url} successful. Status: {response.status}")
            if response.ok:
                if config_instance.scraper_networkidle_timeout_ms > 0:
                    logger.debug(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Waiting for networkidle on {url} (timeout: {config_instance.scraper_networkidle_timeout_ms}ms)...")
                    try:
                        await page.wait_for_load_state('networkidle', timeout=config_instance.scraper_networkidle_timeout_ms)
                        logger.debug(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Networkidle achieved for {url}.")
                    except PlaywrightTimeoutError:
                        logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Timeout waiting for networkidle on {url} after {config_instance.scraper_networkidle_timeout_ms}ms. Proceeding with current DOM content.")
                content = await page.content()
                logger.debug(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Content fetched successfully for {url}.")
                return content, response.status
            else:
                logger.warning(f"[RowID: {input_row_id}, Company: {company_name_or_id}] HTTP error for {url}: Status {response.status} {response.status_text}. No content fetched.")
                return None, response.status
        else:
            logger.error(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Failed to get a response object for {url}. Navigation might have failed silently.")
            return None, None
    except PlaywrightTimeoutError:
        logger.error(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Playwright navigation timeout for {url} after {config_instance.default_navigation_timeout / 1000}s.")
        return None, -1 # Specific code for timeout
    except PlaywrightError as e:
        error_message = str(e)
        logger.error(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Playwright error during navigation to {url}: {error_message}")
        if "net::ERR_NAME_NOT_RESOLVED" in error_message: return None, -2 # DNS error
        elif "net::ERR_CONNECTION_REFUSED" in error_message: return None, -3 # Connection refused
        elif "net::ERR_ABORTED" in error_message: return None, -6 # Request aborted, often due to navigation elsewhere
        return None, -4 # Other Playwright error
    except Exception as e:
        logger.error(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Unexpected error fetching page {url}: {type(e).__name__} - {e}", exc_info=True)
        return None, -5 # Generic exception

def extract_text_from_html(html_content: str) -> str:
    if not html_content: return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    text = soup.get_text(separator=' ', strip=True)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def find_internal_links(html_content: str, base_url: str, input_row_id: Any, company_name_or_id: str) -> List[Tuple[str, int]]:
    if not html_content: return []
    scored_links: List[Tuple[str, int]] = []
    soup = BeautifulSoup(html_content, 'html.parser')
    normalized_base_url_str = normalize_url(base_url)
    parsed_base_url = urlparse(normalized_base_url_str)

    for link_tag in soup.find_all('a', href=True):
        if not isinstance(link_tag, Tag): continue
        href_attr = link_tag.get('href')
        current_href: Optional[str] = None
        if isinstance(href_attr, str): current_href = href_attr.strip()
        elif isinstance(href_attr, list) and href_attr and isinstance(href_attr[0], str): current_href = href_attr[0].strip()
        if not current_href: continue

        absolute_url_raw = urljoin(base_url, current_href)
        normalized_link_url = normalize_url(absolute_url_raw)
        parsed_normalized_link = urlparse(normalized_link_url)

        if parsed_normalized_link.scheme not in ['http', 'https']: continue
        if parsed_normalized_link.netloc != parsed_base_url.netloc: continue

        link_text = link_tag.get_text().lower().strip()
        link_href_lower = normalized_link_url.lower()
        initial_keyword_match = False
        if config_instance.target_link_keywords:
            if any(kw in link_text for kw in config_instance.target_link_keywords) or \
               any(kw in link_href_lower for kw in config_instance.target_link_keywords):
                initial_keyword_match = True
        if not initial_keyword_match: continue

        if config_instance.scraper_exclude_link_path_patterns:
            path_lower = parsed_normalized_link.path.lower()
            if any(p and p in path_lower for p in config_instance.scraper_exclude_link_path_patterns):
                logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Link '{normalized_link_url}' hard excluded by pattern in path: '{path_lower}'.")
                continue
        
        score = 0
        path_segments = [seg for seg in parsed_normalized_link.path.lower().strip('/').split('/') if seg]
        num_segments = len(path_segments)

        if config_instance.scraper_critical_priority_keywords:
            for crit_kw in config_instance.scraper_critical_priority_keywords:
                if any(seg == crit_kw for seg in path_segments):
                    current_score_val = 100
                    if num_segments > config_instance.scraper_max_keyword_path_segments:
                        current_score_val -= min(20, (num_segments - config_instance.scraper_max_keyword_path_segments) * 5)
                    score = max(score, current_score_val)
                    if score >= 100: break
            if score >= 100: pass

        if score < 90 and config_instance.scraper_high_priority_keywords:
            for high_kw in config_instance.scraper_high_priority_keywords:
                if any(seg == high_kw for seg in path_segments):
                    current_score_val = 90
                    if num_segments > config_instance.scraper_max_keyword_path_segments:
                        current_score_val -= min(20, (num_segments - config_instance.scraper_max_keyword_path_segments) * 5)
                    score = max(score, current_score_val)
                    if score >= 90: break
            if score >= 90: pass
        
        if score < 80:
            combined_keywords = list(set(config_instance.scraper_critical_priority_keywords + config_instance.scraper_high_priority_keywords))
            if combined_keywords:
                for p_kw in combined_keywords:
                    for i, seg in enumerate(path_segments):
                        if seg == p_kw:
                            current_score_val = 80 - (i * 5)
                            if num_segments > config_instance.scraper_max_keyword_path_segments:
                                current_score_val -= min(15, (num_segments - config_instance.scraper_max_keyword_path_segments) * 5)
                            score = max(score, current_score_val)
                            break 
                    if score >= 80: break
        
        if score < 50 and config_instance.target_link_keywords:
            if any(tk in seg for tk in config_instance.target_link_keywords for seg in path_segments):
                score = max(score, 50)
        
        if score < 40 and config_instance.target_link_keywords:
            if any(tk in link_text for tk in config_instance.target_link_keywords):
                score = max(score, 40)

        if score >= config_instance.scraper_min_score_to_queue:
            log_text_snippet = link_text[:50].replace('\n', ' ')
            logger.debug(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Link '{normalized_link_url}' scored: {score} (Text: '{log_text_snippet}...', Path: '{parsed_normalized_link.path}') - Adding to potential queue.")
            scored_links.append((normalized_link_url, score))
        else:
            log_text_snippet = link_text[:50].replace('\n', ' ')
            logger.debug(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Link '{normalized_link_url}' (score {score}) below min_score_to_queue ({config_instance.scraper_min_score_to_queue}). Path: '{parsed_normalized_link.path}', Text: '{log_text_snippet}...'. Discarding.")
            
    logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] From page {base_url}, found {len(scored_links)} internal links meeting score criteria.")
    return scored_links

async def is_allowed_by_robots(url: str, client: httpx.AsyncClient, input_row_id: Any, company_name_or_id: str) -> bool:
    if not config_instance.respect_robots_txt:
        logger.debug(f"[RowID: {input_row_id}, Company: {company_name_or_id}] robots.txt check is disabled.")
        return True
    parsed_url = urlparse(url)
    robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        logger.debug(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Fetching robots.txt from: {robots_url}")
        response = await client.get(robots_url, timeout=10, headers={'User-Agent': config_instance.robots_txt_user_agent})
        if response.status_code == 200:
            logger.debug(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Successfully fetched robots.txt for {url}, status: {response.status_code}")
            rp.parse(response.text.splitlines())
        elif response.status_code == 404:
            logger.debug(f"[RowID: {input_row_id}, Company: {company_name_or_id}] robots.txt not found at {robots_url} (status 404), assuming allowed.")
            return True
        else:
            logger.warning(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Failed to fetch robots.txt from {robots_url}, status: {response.status_code}. Assuming allowed.")
            return True
    except httpx.RequestError as e:
        logger.warning(f"[RowID: {input_row_id}, Company: {company_name_or_id}] httpx.RequestError fetching robots.txt from {robots_url}: {e}. Assuming allowed.")
        return True
    except Exception as e:
        logger.error(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Unexpected error processing robots.txt for {robots_url}: {e}. Assuming allowed.", exc_info=True)
        return True
    allowed = rp.can_fetch(config_instance.robots_txt_user_agent, url)
    if not allowed:
        logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Scraping disallowed by robots.txt for URL: {url} (User-agent: {config_instance.robots_txt_user_agent})")
    else:
        logger.debug(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Scraping allowed by robots.txt for URL: {url}")
    return allowed

def _classify_page_type(url_str: str, config: AppConfig) -> str:
    """Classifies a URL based on keywords in its path."""
    if not url_str:
        return "unknown"
    
    url_lower = url_str.lower()
    # Check for specific page types based on keywords in URL path
    # Order matters if keywords overlap; more specific should come first if necessary.
    # For now, assuming simple first-match.
    
    # Path-based classification
    parsed_url = urlparse(url_lower)
    path_lower = parsed_url.path

    if any(kw in path_lower for kw in config.page_type_keywords_contact):
        return "contact"
    if any(kw in path_lower for kw in config.page_type_keywords_imprint):
        return "imprint"
    if any(kw in path_lower for kw in config.page_type_keywords_legal):
        return "legal"
    
    # Fallback if no path keywords match, check full URL for very generic terms
    # (less reliable, path is usually better indicator)
    if any(kw in url_lower for kw in config.page_type_keywords_contact): # broader check on full URL
        return "contact"
    if any(kw in url_lower for kw in config.page_type_keywords_imprint):
        return "imprint"
    if any(kw in url_lower for kw in config.page_type_keywords_legal):
        return "legal"

    # If it's just the base domain (e.g., http://example.com or http://example.com/)
    if not path_lower or path_lower == '/':
        return "homepage" # Could be a specific type or general_content

    return "general_content"


async def scrape_website(
    given_url: str,
    output_dir_for_run: str,
    company_name_or_id: str, # This is the CompanyName
    globally_processed_urls: Set[str],
    input_row_id: Any # This is the InputRowID
) -> Tuple[List[Tuple[str, str, str]], str, Optional[str]]:
    start_time = time.time()
    final_canonical_entry_url: Optional[str] = None
    pages_scraped_for_this_domain_count = 0
    high_priority_pages_scraped_after_limit = 0 # New counter
    logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Starting scrape for URL: {given_url}")

    normalized_given_url = normalize_url(given_url)
    logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Original given_url: '{given_url}', Normalized to: '{normalized_given_url}'")

    if not normalized_given_url or not isinstance(normalized_given_url, str) or \
       not normalized_given_url.startswith(('http://', 'https://')):
        logger.warning(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Scraper received an invalid URL after normalization: {normalized_given_url}")
        return [], "InvalidURL", None

    async with httpx.AsyncClient(follow_redirects=True, verify=False) as http_client:
        if not await is_allowed_by_robots(normalized_given_url, http_client, input_row_id, company_name_or_id):
            return [], "RobotsDisallowed", None

    base_scraped_content_dir = os.path.join(output_dir_for_run, config_instance.scraped_content_subdir)
    cleaned_pages_storage_dir = os.path.join(base_scraped_content_dir, "cleaned_pages_text")
    os.makedirs(cleaned_pages_storage_dir, exist_ok=True)
    
    company_safe_name = get_safe_filename(
        company_name_or_id,
        for_url=False,
        max_len=config_instance.filename_company_name_max_len
    )
 
    scraped_page_details: List[Tuple[str, str, str]] = [] # Modified type
    
    # Queue stores: (url_string, depth_int, score_int)
    # Initial URL gets a high score (e.g., 100) to ensure it's processed first.
    urls_to_scrape: List[Tuple[str, int, int]] = [(normalized_given_url, 0, 100)] 
    
    processed_urls_this_call: Set[str] = {normalized_given_url}

    browser = None
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
            page.set_default_timeout(config_instance.default_page_timeout)
            
            while urls_to_scrape:
                urls_to_scrape.sort(key=lambda x: (-x[2], x[1])) 
                
                current_url_from_queue, current_depth, current_score = urls_to_scrape.pop(0)
                
                logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Dequeuing URL: '{current_url_from_queue}' (Depth: {current_depth}, Score: {current_score}, Queue size: {len(urls_to_scrape)})")

                if config_instance.scraper_max_pages_per_domain > 0 and \
                   pages_scraped_for_this_domain_count >= config_instance.scraper_max_pages_per_domain:
                    if current_score < config_instance.scraper_score_threshold_for_limit_bypass:
                        logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Domain page limit ({config_instance.scraper_max_pages_per_domain}) reached. "
                                    f"Skipping '{current_url_from_queue}' (score {current_score} < "
                                    f"bypass threshold {config_instance.scraper_score_threshold_for_limit_bypass}).")
                        continue
                    else:
                        if high_priority_pages_scraped_after_limit >= config_instance.scraper_max_high_priority_pages_after_limit:
                            logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Domain page limit ({config_instance.scraper_max_pages_per_domain}) AND "
                                        f"max high-priority pages after limit ({config_instance.scraper_max_high_priority_pages_after_limit}) reached. "
                                        f"Skipping '{current_url_from_queue}' (score {current_score}).")
                            continue
                        else:
                            logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Domain page limit reached, but '{current_url_from_queue}' (score {current_score}) "
                                        f"meets bypass threshold. Processing as high-priority page "
                                        f"({high_priority_pages_scraped_after_limit + 1}/{config_instance.scraper_max_high_priority_pages_after_limit}).")
                
                html_content, status_code = await fetch_page_content(page, current_url_from_queue, input_row_id, company_name_or_id)

                if html_content:
                    pages_scraped_for_this_domain_count += 1
                    if pages_scraped_for_this_domain_count > config_instance.scraper_max_pages_per_domain and \
                       current_score >= config_instance.scraper_score_threshold_for_limit_bypass:
                        high_priority_pages_scraped_after_limit += 1
                    
                    final_landed_url_raw = page.url
                    final_landed_url_normalized = normalize_url(final_landed_url_raw)
                    
                    logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Page fetch report: Requested='{current_url_from_queue}', LandedRaw='{final_landed_url_raw}', LandedNormalized='{final_landed_url_normalized}', Status: {status_code}")

                    if not final_canonical_entry_url and current_depth == 0: # Set canonical entry URL from the first successfully fetched page
                        final_canonical_entry_url = final_landed_url_normalized
                        logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Canonical entry URL for this scrape set to: '{final_canonical_entry_url}' (from initial URL '{given_url}')")
                    
                    if final_landed_url_normalized in globally_processed_urls:
                        logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Landed URL '{final_landed_url_normalized}' (from requested '{current_url_from_queue}') has already been globally processed. Skipping content save and further link extraction from this instance.")
                        continue
                    
                    globally_processed_urls.add(final_landed_url_normalized) # Add to global set to prevent re-processing across different scrape_website calls
                    processed_urls_this_call.add(final_landed_url_normalized) # Add to local set for this specific scrape_website call

                    cleaned_text = extract_text_from_html(html_content)
                    parsed_landed_url = urlparse(final_landed_url_normalized)
                    source_domain = parsed_landed_url.netloc
                    safe_source_name = re.sub(r'^www\.', '', source_domain)
                    safe_source_name = re.sub(r'[^\w.-]', '_', safe_source_name)
                    source_specific_output_dir = os.path.join(cleaned_pages_storage_dir, safe_source_name)
                    os.makedirs(source_specific_output_dir, exist_ok=True)
                    logger.debug(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Ensured source-specific directory exists for saving content: {source_specific_output_dir}")

                    landed_url_safe_name = get_safe_filename(final_landed_url_normalized, for_url=True)
                    cleaned_page_filename = f"{company_safe_name}__{landed_url_safe_name}_cleaned.txt"
                    cleaned_page_filepath = os.path.join(source_specific_output_dir, cleaned_page_filename)
                    
                    try:
                        with open(cleaned_page_filepath, 'w', encoding='utf-8') as f_cleaned_page:
                            f_cleaned_page.write(cleaned_text)
                        logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Saved cleaned text from '{final_landed_url_normalized}' (requested as '{current_url_from_queue}') to {cleaned_page_filepath}")
                        page_type = _classify_page_type(final_landed_url_normalized, config_instance)
                        scraped_page_details.append((cleaned_page_filepath, final_landed_url_normalized, page_type))
                        logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Classified '{final_landed_url_normalized}' as page type: {page_type}. Total pages for this domain: {pages_scraped_for_this_domain_count}.")
                    except IOError as e:
                        logger.error(f"[RowID: {input_row_id}, Company: {company_name_or_id}] IOError saving cleaned text for '{final_landed_url_normalized}' to {cleaned_page_filepath}: {e}")

                    if current_depth < config_instance.max_depth_internal_links:
                        newly_found_links_with_scores = find_internal_links(html_content, final_landed_url_normalized, input_row_id, company_name_or_id)
                        added_to_queue_count = 0
                        for link_url, link_score in newly_found_links_with_scores:
                            if link_url not in globally_processed_urls and \
                               link_url not in processed_urls_this_call: # Check against this call's processed set too
                                urls_to_scrape.append((link_url, current_depth + 1, link_score))
                                processed_urls_this_call.add(link_url) # Add to local set to avoid re-adding in this same scrape call
                                added_to_queue_count +=1
                        
                        if added_to_queue_count > 0:
                            urls_to_scrape.sort(key=lambda x: (-x[2], x[1]))
                            logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] From '{final_landed_url_normalized}', added {added_to_queue_count} new unique links to queue. New queue size: {len(urls_to_scrape)}")
                        else:
                            logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] From '{final_landed_url_normalized}', no new unique links added to queue.")
                    else:
                        logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Reached max depth ({current_depth}) for link extraction from '{final_landed_url_normalized}'.")
                else:
                    logger.warning(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Failed to fetch content from '{current_url_from_queue}' (normalized from original input). Status code: {status_code}. This URL will not be processed further.")
                    if current_url_from_queue == normalized_given_url and current_depth == 0 : # Critical failure on the very first URL
                        status_map = {
                            -1: "TimeoutError", -2: "DNSError", -3: "ConnectionRefused",
                            -4: "PlaywrightError", -5: "GenericScrapeError", -6: "RequestAborted"
                        }
                        http_status_report = "UnknownScrapeError"
                        if status_code is not None:
                            if status_code > 0: http_status_report = f"HTTPError_{status_code}"
                            elif status_code in status_map: http_status_report = status_map[status_code]
                            else: http_status_report = "UnknownScrapeErrorCode"
                        else: http_status_report = "NoStatusFromServer" # Should not happen if fetch_page_content returns None for content
                        logger.error(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Critical failure on initial URL '{normalized_given_url}'. Scraper status: {http_status_report}. No canonical URL determined.")
                        return [], http_status_report, None # No canonical URL if initial fails

            # After loop finishes or breaks
            if scraped_page_details:
                logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Scraping completed. Successfully scraped and saved {len(scraped_page_details)} unique pages for domain derived from '{given_url}'. Total pages processed in this call: {pages_scraped_for_this_domain_count}.")
                total_time = time.time() - start_time
                logger.info(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Total scraping duration for this call: {total_time:.2f} seconds.")
                return scraped_page_details, "Success", final_canonical_entry_url # final_canonical_entry_url should be set if any page was successful
            else: # No pages were successfully scraped and saved
                logger.warning(f"[RowID: {input_row_id}, Company: {company_name_or_id}] No content was successfully scraped and saved for the domain derived from '{given_url}'. Total pages attempted in this call: {pages_scraped_for_this_domain_count}.")
                # Determine a more specific status if initial URL failed vs. sub-pages failed
                if pages_scraped_for_this_domain_count == 0 and not final_canonical_entry_url: # Implies initial URL itself failed critically
                    # The status from the initial URL failure would have been returned already if it was critical.
                    # This path suggests maybe the initial URL was disallowed by robots, or some other pre-fetch issue.
                    # If final_canonical_entry_url is None, it means the very first fetch failed to establish it.
                    logger.error(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Initial URL '{normalized_given_url}' failed to yield any content or establish a canonical URL.")
                    return [], "InitialURL_NoContentOrCanonical", None
                else: # Some pages might have been processed but none saved, or initial URL was fine but no sub-pages yielded content
                     return [], "NoContentScraped_Overall", final_canonical_entry_url # Use established canonical if available
        except Exception as e:
            logger.error(f"[RowID: {input_row_id}, Company: {company_name_or_id}] General error during Playwright scraping process for '{given_url}': {type(e).__name__} - {e}", exc_info=True)
            return [], f"GeneralScrapingError_{type(e).__name__}", final_canonical_entry_url # Return established canonical if any
        finally:
            if browser and browser.is_connected():
                logger.debug(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Closing browser in 'finally' block.")
                await browser.close()
    
    # This part should ideally not be reached if browser was initialized.
    # If it is, it means Playwright setup itself failed.
    logger.error(f"[RowID: {input_row_id}, Company: {company_name_or_id}] Scraping ended unexpectedly for '{given_url}' (e.g., Playwright launch failed).")
    return [], "ScraperSetupFailure", None # No canonical URL if setup failed

# TODO: [FutureEnhancement] The _test_scraper function below was for demonstrating and testing
# the scrape_website functionality directly. It includes setup for logging and test output.
# Commented out as it's not part of the main pipeline execution.
# It can be uncommented for debugging or standalone testing of the scraper logic.
async def _test_scraper():
    """
    An asynchronous test function to demonstrate and test the `scrape_website` functionality.

    Sets up logging, defines a test URL and output directory, then calls
    `scrape_website` and logs the result. This function is intended to be run
    when the script is executed directly (`if __name__ == "__main__":`).
    """
    # Ensure AppConfig is loaded with any .env overrides for testing
    global config_instance
    config_instance = AppConfig() 
    
    setup_logging(logging.DEBUG) 
    logger.info("Starting test scraper...")

    test_url = "https://www.example.com" 
    # test_url = "https://www.python.org"
    # test_url = "https://nonexistent-domain-for-testing123.com"

    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming this script is in 'src/scraper', project_root is 'src/'
    # For 'phone_validation_pipeline' as project root, adjust path.
    # If 'src' is directly under 'phone_validation_pipeline':
    project_root = os.path.dirname(os.path.dirname(script_dir)) # Goes up to phone_validation_pipeline
    
    test_output_base = os.path.join(project_root, "test_scraper_output_data")
    test_run_id = "test_run_manual_" + time.strftime("%Y%m%d_%H%M%S")
    test_run_output_dir = os.path.join(test_output_base, test_run_id)
    
    # Ensure the main output directory for the run exists
    os.makedirs(test_run_output_dir, exist_ok=True)
    # The scrape_website function will create subdirectories like 'scraped_content/cleaned_pages_text'

    logger.info(f"Test output directory for this run: {test_run_output_dir}")
    
    # Initialize a new set for globally_processed_urls for this test run
    globally_processed_urls_for_test: Set[str] = set()

    # Adjust to expect three values from scrape_website
    scraped_items_with_type, status, canonical_url = await scrape_website(
       test_url,
       test_run_output_dir, # This is the base for the run, scrape_website will make subdirs
       "example_company_test",
       globally_processed_urls_for_test,
       "TEST_ROW_ID_001" # Added placeholder for input_row_id
    )

    if scraped_items_with_type:
        logger.info(f"Test successful: {len(scraped_items_with_type)} page(s) scraped. Status: {status}. Canonical URL: {canonical_url}")
        # Adjust loop to handle the new tuple structure (path, url, type)
        for item_path, source_url, page_type in scraped_items_with_type:
            logger.info(f"  - Saved: {item_path} (from: {source_url}, type: {page_type})")
    else:
        logger.error(f"Test failed: Status: {status}. Canonical URL: {canonical_url}")

# TODO: [FutureEnhancement] The __main__ block below allowed direct execution of _test_scraper.
# Commented out as it's not intended for execution during normal library use.
if __name__ == "__main__":
    # This ensures that if the script is run directly, AppConfig is initialized
    # and logging is set up before _test_scraper is called.
    if not logger.hasHandlers(): 
        setup_logging(logging.INFO) 
    asyncio.run(_test_scraper())