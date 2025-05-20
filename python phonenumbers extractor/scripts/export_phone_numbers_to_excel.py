#!/usr/bin/env python3
"""
This script provides functionality to query phone numbers and related company
information from the database and export it to an Excel file.
"""
import os
import psycopg2
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional

# Attempt to import from src, assuming script is run from project root
# or src is in PYTHONPATH
try:
    from src.db.utils import get_db_connection
    from src.utils.logging_config import get_logger
except ImportError:
    # Fallback for direct execution or if src is not in path yet
    # This might require adjusting PYTHONPATH when running
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from src.db.utils import get_db_connection
    from src.utils.logging_config import get_logger


log = get_logger(__name__)

# Define the SQL query to fetch the required data
SQL_QUERY = """
SELECT
    cpn.phone_number,
    c.company_name,
    c.website,
    cpn.sources,
    cpn.phone_status
FROM
    cleaned_phone_numbers cpn
JOIN
    companies c ON cpn.client_id = c.client_id;
"""

DEFAULT_REPORTS_DIR = os.path.join("data", "reports")

def format_sources(sources_array: Optional[List[str]]) -> str:
    """Converts a list of sources into a comma-separated string."""
    if sources_array is None:
        return ""
    return ", ".join(sources_array)

def generate_phone_numbers_excel_report(output_dir: str = DEFAULT_REPORTS_DIR) -> Optional[str]:
    """
    Queries the database for phone numbers and company information,
    then exports this data to an Excel file.

    Args:
        output_dir (str): The directory where the Excel file will be saved.
                          Defaults to "data/reports".

    Returns:
        Optional[str]: The path to the generated Excel file if successful, None otherwise.
    """
    log.info("Starting generation of phone numbers Excel report.")
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            log.error("Failed to establish database connection for report generation.")
            return None

        log.info("Database connection established. Executing query...")
        with conn.cursor() as cur:
            cur.execute(SQL_QUERY)
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]

        if not rows:
            log.info("No data found to export.")
            return None

        log.info(f"Fetched {len(rows)} records from the database.")

        # Process data for DataFrame
        processed_data = []
        for row_tuple in rows:
            row_dict = dict(zip(colnames, row_tuple))
            # Format the 'sources' array into a string
            if 'sources' in row_dict:
                row_dict['sources'] = format_sources(row_dict['sources'])
            processed_data.append(row_dict)

        df = pd.DataFrame(processed_data)

        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)
        log.info(f"Ensured output directory exists: {output_dir}")

        # Generate a timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"phone_numbers_export_{timestamp}.xlsx"
        filepath = os.path.join(output_dir, filename)

        # Export DataFrame to Excel
        df.to_excel(filepath, index=False, engine='openpyxl')
        log.info(f"Successfully exported data to Excel file: {filepath}")
        return filepath

    except psycopg2.Error as db_err:
        log.error(f"Database error during report generation: {db_err}", exc_info=True)
        return None
    except pd.errors.PandasError as pd_err:
        log.error(f"Pandas error during report generation: {pd_err}", exc_info=True)
        return None
    except IOError as io_err:
        log.error(f"File I/O error during report generation: {io_err}", exc_info=True)
        return None
    except Exception as e:
        log.error(f"An unexpected error occurred during report generation: {e}", exc_info=True)
        return None
    finally:
        if conn:
            conn.close()
            log.info("Database connection closed.")

if __name__ == '__main__':
    log.info("Running phone numbers export script directly.")
    # Example: Configure logging if running standalone
    # from src.utils.logging_config import setup_logging
    # setup_logging() # Call this if you have a global setup function

    report_path = generate_phone_numbers_excel_report()
    if report_path:
        print(f"Report generated successfully: {report_path}")
    else:
        print("Failed to generate report.")