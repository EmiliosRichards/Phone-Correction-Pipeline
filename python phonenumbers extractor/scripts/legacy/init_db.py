#!/usr/bin/env python3
"""
Database initialization script for the Phone Extraction project.
Creates the required database tables if they don't exist.

Usage:
    python scripts/init_db.py

Environment variables:
    DB_HOST: Database host (default: localhost)
    DB_PORT: Database port (default: 5432)
    DB_NAME: Database name (default: phone_extraction)
    DB_USER: Database user (default: postgres)
    DB_PASSWORD: Database password (required)
"""
import os
import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.db.utils import get_db_connection
from src.utils.logging_config import get_logger

# Get logger for this module
log = get_logger(__name__)

def create_tables(conn):
    """
    Create the required database tables if they don't exist.
    
    Args:
        conn: Database connection object
    """
    # Define the SQL statements to create the tables
    create_companies_table = """
    CREATE TABLE IF NOT EXISTS companies (
        client_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        company_name TEXT NOT NULL,
        domain TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    """
    
    create_scraped_pages_table = """
    CREATE TABLE IF NOT EXISTS scraped_pages (
        page_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        client_id UUID REFERENCES companies(client_id),
        url TEXT NOT NULL,
        page_type TEXT, -- homepage, support, linkedin, about, etc.
        scraped_at TIMESTAMP DEFAULT NOW(),
        raw_html_path TEXT,
        plain_text_path TEXT,
        summary TEXT,
        extraction_notes TEXT
    );
    """
    
    create_scraping_logs_table = """
    CREATE TABLE IF NOT EXISTS scraping_logs (
        log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        client_id UUID REFERENCES companies(client_id),
        source TEXT, -- homepage, about, linkedin
        url_scraped TEXT,
        status TEXT, -- pending, completed, failed
        scraping_date TIMESTAMP DEFAULT NOW(),
        error_message TEXT
    );
    """
    
    create_raw_phone_numbers_table = """
    CREATE TABLE IF NOT EXISTS raw_phone_numbers (
        raw_phone_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        client_id UUID REFERENCES companies(client_id),
        page_id UUID REFERENCES scraped_pages(page_id),
        log_id UUID REFERENCES scraping_logs(log_id),
        phone_number TEXT NOT NULL,
        url TEXT,
        source_page TEXT, -- e.g., homepage, contact page, linkedin
        scrape_run_timestamp TIMESTAMP,
        notes TEXT,
        extracted_at TIMESTAMP DEFAULT NOW(),
        confidence_score NUMERIC DEFAULT 0.0
    );
    """
    
    create_cleaned_phone_numbers_table = """
    CREATE TABLE IF NOT EXISTS cleaned_phone_numbers (
        cleaned_phone_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        client_id UUID REFERENCES companies(client_id),
        phone_number TEXT NOT NULL,
        sources TEXT[], -- e.g., ['homepage', 'linkedin', 'about']
        occurrence_count INTEGER DEFAULT 1,
        phone_status TEXT, -- valid, invalid, pending_validation, needs_review
        confidence_score NUMERIC DEFAULT 0.0,
        last_validated TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(client_id, phone_number)
    );
    """
    
    # Create the tables in the correct order (respecting foreign key constraints)
    tables = [
        ("companies", create_companies_table),
        ("scraped_pages", create_scraped_pages_table),
        ("scraping_logs", create_scraping_logs_table),
        ("raw_phone_numbers", create_raw_phone_numbers_table),
        ("cleaned_phone_numbers", create_cleaned_phone_numbers_table)
    ]
    
    try:
        # Enable the uuid-ossp extension for gen_random_uuid()
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
            conn.commit()
            log.info("Enabled uuid-ossp extension")
        
        # Create each table
        for table_name, create_statement in tables:
            with conn.cursor() as cur:
                cur.execute(create_statement)
                conn.commit()
                log.info(f"Created or verified table: {table_name}")
        
        log.info("All database tables have been created successfully")
        return True
    except Exception as e:
        conn.rollback()
        log.error(f"Error creating database tables: {e}", exc_info=True)
        return False

def check_tables_exist(conn):
    """
    Check if all required tables exist in the database.
    
    Args:
        conn: Database connection object
        
    Returns:
        bool: True if all required tables exist, False otherwise
    """
    required_tables = ['companies', 'scraped_pages', 'scraping_logs', 
                      'raw_phone_numbers', 'cleaned_phone_numbers']
    
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
                log.info(f"Missing tables: {', '.join(missing_tables)}")
                return False
            return True
    except Exception as e:
        log.error(f"Error checking tables: {e}", exc_info=True)
        return False

def main():
    """Main function to initialize the database."""
    log.info("Starting database initialization")
    
    try:
        # Connect to the database
        conn = get_db_connection()
        
        # Check if tables already exist
        if check_tables_exist(conn):
            log.info("All required tables already exist in the database")
        else:
            # Create the tables
            if create_tables(conn):
                log.info("Database initialization completed successfully")
            else:
                log.error("Failed to initialize database")
        
        # Close the connection
        conn.close()
        
    except ValueError as e:
        log.error(f"Configuration error: {e}")
        log.error("Please check your .env file and ensure all required environment variables are set")
        sys.exit(1)
    except Exception as e:
        log.error(f"An error occurred during database initialization: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()