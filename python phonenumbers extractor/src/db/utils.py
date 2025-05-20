#!/usr/bin/env python3
"""
Database utility functions for the Phone Extraction project.
Handles PostgreSQL database connections and operations.
"""
import os
import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from src.utils.logging_config import get_logger

# Get logger for this module
log = get_logger(__name__)

# Load environment variables from .env file
# Load environment variables from .env file
load_dotenv()

# Database configuration with defaults for graceful fallback
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "phone_extraction")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Log level is handled by the centralized logging configuration

def get_db_connection():
    """
    Establishes a connection to the PostgreSQL database.
    
    Returns:
        psycopg2.connection: A connection object to the database
        
    Raises:
        ValueError: If required environment variables are missing
        psycopg2.Error: If connection to the database fails
    """
    # Check if required DB_PASSWORD is set
    if not DB_PASSWORD:
        log.error("DB_PASSWORD environment variable is not set")
        raise ValueError("Database password is required. Please set DB_PASSWORD environment variable.")
    
    # Log connection attempt with sanitized information
    log.info(f"Attempting to connect to database {DB_NAME} at {DB_HOST}:{DB_PORT}")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        log.info("Successfully connected to the database.")
        return conn
    except psycopg2.Error as e:
        # Provide more helpful error message based on error type
        if "could not connect to server" in str(e):
            log.error(f"Could not connect to database server at {DB_HOST}:{DB_PORT}. "
                     "Please check if the server is running and accessible.")
        elif "password authentication failed" in str(e):
            log.error("Password authentication failed. Please check your DB_USER and DB_PASSWORD.")
        elif "database" in str(e) and "does not exist" in str(e):
            log.error(f"Database '{DB_NAME}' does not exist. Please create it first.")
        else:
            log.error(f"Error connecting to the database: {e}", exc_info=True)
        raise

def insert_raw_phone_number(conn, phone_data: Dict[str, Any]) -> str:
    """
    Inserts a single raw phone number occurrence into the raw_phone_numbers table.
    Returns the generated raw_phone_id.
    """
    query = sql.SQL("""
        INSERT INTO raw_phone_numbers (
            raw_phone_id, client_id, page_id, log_id, phone_number,
            url, source_page, scrape_run_timestamp, notes,
            extracted_at, confidence_score
        ) VALUES (
            gen_random_uuid(), %(client_id)s, %(page_id)s, %(log_id)s, %(phone_number)s,
            %(url)s, %(source_page)s, %(scrape_run_timestamp)s, %(notes)s,
            NOW(), %(confidence_score)s
        ) RETURNING raw_phone_id;
    """)
    try:
        # Log the data being prepared for insertion
        log.info(f"Attempting to insert raw phone number with data: {phone_data}") # Changed to info for visibility

        # Prepare a copy of phone_data for DB insertion to avoid modifying original dict
        # and to ensure 'url' is a string.
        phone_data_for_db = phone_data.copy()
        current_url_val = phone_data_for_db.get('url')

        if isinstance(current_url_val, dict):
            # Prefer 'parsed' URL, fallback to 'original', then to empty string if not found
            phone_data_for_db['url'] = current_url_val.get('parsed', current_url_val.get('original', ''))
            log.debug(f"Extracted string URL for DB insertion: {phone_data_for_db['url']} from dict {current_url_val}")
        elif current_url_val is None:
            phone_data_for_db['url'] = '' # Ensure it's not None for DB, provide an empty string
        # If it's already a string, it will be used as is.

        with conn.cursor() as cur:
            cur.execute(query, phone_data_for_db) # Use the modified copy
            raw_phone_id = cur.fetchone()[0]
            conn.commit()
            log.info(f"Successfully inserted raw phone number, ID: {raw_phone_id}")
            return raw_phone_id
    except psycopg2.Error as e:
        log.error(f"Error inserting raw phone number {phone_data.get('phone_number')}: {e}", exc_info=True)
        conn.rollback()
        raise

def upsert_cleaned_phone_number(conn, phone_data: Dict[str, Any]):
    """
    Inserts or updates a cleaned phone number in the cleaned_phone_numbers table.
    """
    query = sql.SQL("""
        INSERT INTO cleaned_phone_numbers (
            cleaned_phone_id, client_id, phone_number, sources,
            occurrence_count, phone_status, confidence_score,
            last_validated, created_at, updated_at
        ) VALUES (
            gen_random_uuid(), %(client_id)s, %(phone_number)s, ARRAY[%(source_page)s],
            1, 'pending_validation', %(confidence_score)s,
            NOW(), NOW(), NOW()
        )
        ON CONFLICT (client_id, phone_number) DO UPDATE SET
            sources = CASE
                WHEN NOT (%(source_page)s = ANY(cleaned_phone_numbers.sources))
                THEN array_append(cleaned_phone_numbers.sources, %(source_page)s)
                ELSE cleaned_phone_numbers.sources END,
            occurrence_count = cleaned_phone_numbers.occurrence_count + 1,
            confidence_score = GREATEST(cleaned_phone_numbers.confidence_score, %(confidence_score)s),
            updated_at = NOW();
    """)
    try:
        with conn.cursor() as cur:
            cur.execute(query, phone_data)
            conn.commit()
            log.info(f"Successfully upserted cleaned phone number: {phone_data.get('phone_number')} for client {phone_data.get('client_id')}")
    except psycopg2.Error as e:
        log.error(f"Error upserting cleaned phone number {phone_data.get('phone_number')}: {e}", exc_info=True)
        conn.rollback()
        raise

def update_scraping_log_error(conn, log_id: Any, error_message: str):
    """
    Updates the error_message in the scraping_logs table for a given log_id.
    """
    query = sql.SQL("""
        UPDATE scraping_logs
        SET error_message = %(error_message)s, status = 'failed'
        WHERE log_id = %(log_id)s;
    """)
    try:
        with conn.cursor() as cur:
            cur.execute(query, {'log_id': log_id, 'error_message': error_message})
            conn.commit()
            log.info(f"Successfully updated scraping_log for log_id {log_id} with error.")
    except psycopg2.Error as e:
        log.error(f"Error updating scraping_log for log_id {log_id}: {e}", exc_info=True)
        conn.rollback()
        raise

def check_db_tables_exist(conn) -> bool:
    """
    Check if the required database tables exist.
    
    Args:
        conn: Database connection object
        
    Returns:
        bool: True if all required tables exist, False otherwise
    """
    required_tables = ['raw_phone_numbers', 'cleaned_phone_numbers',
                      'scraped_pages', 'scraping_logs']
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
            existing_tables = [row[0] for row in cur.fetchall()]
            
            missing_tables = [table for table in required_tables
                             if table not in existing_tables]
            
            if missing_tables:
                log.warning(f"Missing required tables: {', '.join(missing_tables)}")
                return False
            return True
    except psycopg2.Error as e:
        log.error(f"Error checking database tables: {e}", exc_info=True)
        return False

def get_client_id_by_url(conn, url: str) -> Optional[str]:
    """
    Fetches client_id from scraping_logs table based on the URL.
    """
    if not conn:
        log.warning("get_client_id_by_url: Database connection is None. Skipping query.")
        return None
    if not url:
        log.warning("get_client_id_by_url: URL is None or empty. Skipping query.")
        return None

    query = sql.SQL("SELECT client_id FROM scraping_logs WHERE url_scraped = %s;")
    try:
        with conn.cursor() as cur:
            cur.execute(query, (url,))
            result = cur.fetchone()
            if result and result[0]:
                client_id = str(result[0]) # Ensure it's a string
                log.info(f"Found client_id '{client_id}' for URL '{url}' in scraping_logs.")
                return client_id
            else:
                log.warning(f"No client_id found for URL '{url}' in scraping_logs.")
                return None
    except psycopg2.Error as e:
        log.error(f"Error fetching client_id for URL '{url}': {e}", exc_info=True)
        # Do not rollback here as it's a read operation and might be part of a larger transaction
        return None
    except Exception as e:
        log.error(f"Unexpected error in get_client_id_by_url for URL '{url}': {e}", exc_info=True)
        return None

def get_log_id_by_url(conn, url: str) -> Optional[Any]:
    """
    Fetches log_id from scraping_logs table based on the URL.
    """
    if not conn:
        log.warning("get_log_id_by_url: Database connection is None. Skipping query.")
        return None
    if not url:
        log.warning("get_log_id_by_url: URL is None or empty. Skipping query.")
        return None

    query = sql.SQL("SELECT log_id FROM scraping_logs WHERE url_scraped = %s;")
    try:
        with conn.cursor() as cur:
            cur.execute(query, (url,))
            result = cur.fetchone()
            if result and result[0] is not None: # Check if result[0] is not None
                log_id = result[0]
                log.info(f"Found log_id '{log_id}' for URL '{url}' in scraping_logs.")
                return log_id
            else:
                log.warning(f"No log_id found for URL '{url}' in scraping_logs, or log_id is NULL.")
                return None
    except psycopg2.Error as e:
        log.error(f"Error fetching log_id for URL '{url}': {e}", exc_info=True)
        # Do not rollback here as it's a read operation
        return None
    except Exception as e:
        log.error(f"Unexpected error in get_log_id_by_url for URL '{url}': {e}", exc_info=True)
        return None

def get_page_id_by_url(conn, url: str) -> Optional[Any]:
    """
    Fetches page_id from scraped_pages table based on the URL.
    """
    if not conn:
        log.warning("get_page_id_by_url: Database connection is None. Skipping query.")
        return None
    if not url:
        log.warning("get_page_id_by_url: URL is None or empty. Skipping query.")
        return None

    query = sql.SQL("SELECT page_id FROM scraped_pages WHERE url = %s;")
    try:
        with conn.cursor() as cur:
            cur.execute(query, (url,))
            result = cur.fetchone()
            if result and result[0] is not None: # Check if result[0] is not None
                page_id = result[0]
                log.info(f"Found page_id '{page_id}' for URL '{url}' in scraped_pages.")
                return page_id
            else:
                log.warning(f"No page_id found for URL '{url}' in scraped_pages, or page_id is NULL.")
                return None
    except psycopg2.Error as e:
        log.error(f"Error fetching page_id for URL '{url}': {e}", exc_info=True)
        # Do not rollback here as it's a read operation
        return None
    except Exception as e:
        log.error(f"Unexpected error in get_page_id_by_url for URL '{url}': {e}", exc_info=True)
        return None
if __name__ == '__main__':
    # Example usage (for testing connection)
    try:
        connection = get_db_connection()
        if connection:
            log.info("Database connection test successful.")
            
            # Check if required tables exist
            if check_db_tables_exist(connection):
                log.info("All required database tables exist.")
            else:
                log.warning("Some required database tables are missing. "
                           "Run scripts/init_db.py to initialize the database.")
            
            # Test get_client_id_by_url
            # test_url = "http://example.com" # Replace with a URL you expect to be in your scraping_logs
            # log.info(f"Testing get_client_id_by_url with URL: {test_url}")
            # client_id_from_db = get_client_id_by_url(connection, test_url)
            # if client_id_from_db:
            #     log.info(f"Test get_client_id_by_url returned: {client_id_from_db}")
            # else:
            #     log.warning(f"Test get_client_id_by_url did not find client_id for {test_url}")

            connection.close()
        else:
            log.error("Database connection test failed.")
    except ValueError as e:
        log.error(f"Configuration error: {e}")
    except Exception as e:
        log.error(f"An error occurred during database connection test: {e}", exc_info=True)