import pandas as pd
import re
from urllib.parse import urlparse

def extract_base_domain(company_name_field):
    """
    Extracts the base domain from a company name field that might contain a URL.
    Example: "https://wolterskluwer.com - AnNoText" -> "wolterskluwer"
    """
    if pd.isna(company_name_field):
        return None
    # Find the first part that looks like a URL
    url_match = re.search(r'https?://[^\s]+', str(company_name_field))
    if url_match:
        url_str = url_match.group(0)
        try:
            parsed_url = urlparse(url_str)
            domain = parsed_url.netloc
            # Remove www. if present
            if domain.startswith('www.'):
                domain = domain[4:]
            # Split by dot and take the part before the TLD (e.g., .com, .de)
            # This is a simplification and might need adjustment for complex TLDs (e.g., .co.uk)
            domain_parts = domain.split('.')
            if len(domain_parts) > 1:
                # Handle cases like 'example.com' -> 'example', 'example.co.uk' -> 'example'
                # This logic might need refinement for more robust TLD stripping.
                # For now, it assumes common TLDs are single parts like .com, .de, .org
                # or double like .co.uk (where we'd want 'co' if not careful)
                # A more robust way would be a list of TLDs.
                # Let's try to get the part before the last part if it's a common TLD.
                if domain_parts[-1] in ['com', 'de', 'org', 'net', 'uk', 'io', 'co']: # Add more common TLDs
                    if len(domain_parts) > 2 and domain_parts[-2] in ['co']: # for .co.uk etc.
                         return domain_parts[-3] if len(domain_parts) > 2 else domain_parts[0]
                    return domain_parts[-2] if len(domain_parts) > 1 else domain_parts[0]
                return domain_parts[0] # Fallback if TLD not in simple list
            return domain # If only one part (e.g. localhost)
        except Exception:
            return None # Or handle error appropriately
    return None # If no URL found

def extract_phone_number(phone_field):
    """
    Extracts the numerical phone number from a string.
    Example: "+4922332055000 (Main Line) [AnNoText]" -> "+4922332055000"
    """
    if pd.isna(phone_field):
        return None
    match = re.search(r'([+\d\s()-]+)', str(phone_field)) # Looser regex to capture numbers, spaces, hyphens, parens
    if match:
        # Further clean to get mostly digits and +
        phone_num = re.sub(r'[^\d+]', '', match.group(1).split('(')[0].strip())
        return phone_num
    return None

def extract_number_type(phone_field):
    """
    Extracts the number type from parentheses in a phone string.
    Example: "+4922332055000 (Main Line) [AnNoText]" -> "Main Line"
    """
    if pd.isna(phone_field):
        return None
    match = re.search(r'\((.*?)\)', str(phone_field))
    if match:
        return match.group(1).strip()
    return None # Or "N/A" as per plan

def main():
    source_file = 'Top_Contacts_Report_20250520_171540.xlsx'
    output_file = 'Final_Processed_Contacts.xlsx'

    try:
        df_source = pd.read_excel(source_file)
    except FileNotFoundError:
        print(f"Error: Source file '{source_file}' not found.")
        return
    except Exception as e:
        print(f"Error reading source file: {e}")
        return

    processed_data = []

    for index, row in df_source.iterrows():
        company_name = extract_base_domain(row.get('CompanyName'))
        url = row.get('CanonicalEntryURL')
        number = extract_phone_number(row.get('PhoneNumber_1'))
        number_type = extract_number_type(row.get('PhoneNumber_1'))
        number_found_at = row.get('SourceURL_1')

        processed_data.append({
            'Company Name': company_name,
            'URL': url,
            'Number': number,
            'Number Type': number_type,
            'Number Found At': number_found_at
        })

    df_output = pd.DataFrame(processed_data)

    try:
        df_output.to_excel(output_file, index=False)
        print(f"Successfully processed data and saved to '{output_file}'")
    except Exception as e:
        print(f"Error writing output file: {e}")

if __name__ == '__main__':
    main()