"""Common text processing utilities."""

import re
from typing import List, Optional, Set

# Optional NLTK import
try:
    from nltk.tokenize import sent_tokenize
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and normalizing line endings.
    
    Args:
        text: Input text to clean
        
    Returns:
        Cleaned text with normalized whitespace
        
    Example:
        >>> text = "  Hello   world  \n\n  How are you?  "
        >>> clean_text(text)
        'Hello world How are you?'
    """
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    # Replace multiple newlines with single newline
    text = re.sub(r'\n+', '\n', text)
    # Strip leading/trailing whitespace
    return text.strip()

def deduplicate_lines(text: str) -> str:
    """
    Remove duplicate lines while preserving order.
    
    Args:
        text: Input text with potential duplicate lines
        
    Returns:
        Text with duplicates removed
        
    Example:
        >>> text = "Line 1\\nLine 2\\nLine 1\\nLine 3\\nLine 2"
        >>> deduplicate_lines(text)
        'Line 1\\nLine 2\\nLine 3'
    """
    seen: Set[str] = set()
    unique_lines: List[str] = []
    
    for line in text.splitlines():
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            unique_lines.append(line)
            
    return '\n'.join(unique_lines)

def split_text_into_paragraphs(text: str) -> List[str]:
    """
    Split text into paragraphs based on multiple newlines and clean each paragraph.
    
    Args:
        text: Input text to split into paragraphs
        
    Returns:
        List of cleaned paragraphs, with empty paragraphs removed
        
    Example:
        >>> text = "First paragraph\\n\\nSecond paragraph\\n\\n\\nThird paragraph"
        >>> split_text_into_paragraphs(text)
        ['First paragraph', 'Second paragraph', 'Third paragraph']
        >>> split_text_into_paragraphs("  Line 1  \\n\\n  Line 2  ")
        ['Line 1', 'Line 2']
    """
    # Split by two or more newlines
    paragraphs = re.split(r'\n{2,}', text)
    
    # Clean each paragraph and filter out empty ones
    cleaned_paragraphs = [
        clean_text(paragraph)
        for paragraph in paragraphs
        if paragraph.strip()
    ]
    
    return cleaned_paragraphs

def chunk_text(text: str, max_chunk_size: int = 1000, overlap: int = 100, use_nltk: bool = False) -> List[str]:
    """
    Split text into overlapping chunks of maximum size.
    Optionally uses NLTK for better sentence detection.
    
    Args:
        text: Input text to chunk
        max_chunk_size: Maximum size of each chunk
        overlap: Number of characters to overlap between chunks
        use_nltk: Whether to use NLTK for sentence detection (requires nltk package)
        
    Returns:
        List of text chunks
        
    Example:
        >>> text = "This is a long text. It has multiple sentences. " * 10
        >>> chunks = chunk_text(text, max_chunk_size=50, overlap=10)
        >>> len(chunks) > 1
        True
        >>> all(len(chunk) <= 50 for chunk in chunks)
        True
    """
    if len(text) <= max_chunk_size:
        return [text]
        
    chunks: List[str] = []
    start = 0
    last_end = 0  # Track the last end position to prevent endless reprocessing
    
    # Use NLTK for sentence detection if requested and available
    if use_nltk and NLTK_AVAILABLE:
        sentences = sent_tokenize(text)
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            # If adding this sentence would exceed max size, save current chunk
            if current_size + sentence_size > max_chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                # Start new chunk with overlap
                overlap_text = ' '.join(current_chunk[-3:])  # Use last 3 sentences for overlap
                current_chunk = [overlap_text] if overlap_text else []
                current_size = len(overlap_text)
            
            current_chunk.append(sentence)
            current_size += sentence_size
        
        # Add the last chunk if it exists
        if current_chunk:
            chunks.append(' '.join(current_chunk))
            
    else:
        # Original regex-based chunking
        while start < len(text):
            # Find the end of the chunk
            end = start + max_chunk_size
            
            # If this is not the last chunk, try to break at a sentence or paragraph
            if end < len(text):
                # Look for sentence endings
                sentence_end = text.rfind('. ', start, end)
                if sentence_end != -1:
                    end = sentence_end + 1
                else:
                    # Look for paragraph breaks
                    para_end = text.rfind('\n\n', start, end)
                    if para_end != -1:
                        end = para_end + 2
                    
            # Add the chunk
            chunks.append(text[start:end].strip())
            
            # Move start position, accounting for overlap and preventing negative values
            start = max(0, end - overlap)
            
            # Guard against endless reprocessing
            if start <= last_end:
                # If we're not making progress, force a step forward
                start = last_end + 1
            last_end = end
            
            # Safety check to prevent infinite loops
            if start >= len(text):
                break
            
    return chunks

def normalize_phone_number(raw: str) -> str:
    """
    Normalize a phone number to E.164 format.
    
    Args:
        raw: Raw phone number string to normalize
        
    Returns:
        Normalized phone number in E.164 format (+[country code][number])
        
    Example:
        >>> normalize_phone_number("(555) 555-5555")
        '+15555555555'
        >>> normalize_phone_number("+44 20 7123 4567")
        '+442071234567'
    """
    # Remove all non-digit characters except '+'
    number = re.sub(r'[^\d+]', '', raw)
    
    # Handle US/Canada numbers without country code
    if not number.startswith('+'):
        if len(number) == 10:
            number = '+1' + number
        elif len(number) == 11 and number.startswith('1'):
            number = '+' + number
        else:
            # For other numbers without country code, assume US/Canada
            number = '+1' + number[-10:]
            
    return number

def extract_phone_numbers(text: str, deduplicate: bool = True) -> List[str]:
    """
    Extract phone numbers from text using regex patterns and normalize to E.164 format.
    Handles international numbers, extensions, and various formatting patterns.
    
    Args:
        text: Input text to search
        deduplicate: If True, return unique numbers only. If False, return all numbers
                    including duplicates (useful for counting frequency).
        
    Returns:
        List of found phone numbers in E.164 format (+[country code][number]).
        If deduplicate is True, returns unique numbers. If False, returns all numbers
        in order of appearance.
        
    Example:
        >>> text = "Call us at (555) 555-5555 or +44 20 7123 4567 ext 123"
        >>> extract_phone_numbers(text)
        ['+15555555555', '+442071234567x123']
        >>> extract_phone_numbers("555-555-5555 555-555-5555", deduplicate=False)
        ['+15555555555', '+15555555555']
    """
    # Common phone number patterns with extensions
    patterns = [
        # International format with country code
        r'\+?[0-9]{1,3}[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,4}(?:[xX]|ext|extension)?[-.\s]?[0-9]{1,6}?',
        # US/Canada format with area code
        r'\+?1?\s*\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}(?:[xX]|ext|extension)?[-.\s]?[0-9]{1,6}?',
        # Basic format
        r'[0-9]{3}[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}(?:[xX]|ext|extension)?[-.\s]?[0-9]{1,6}?',
    ]
    
    if deduplicate:
        found: Set[str] = set()
    else:
        found: List[str] = []
    
    for pattern in patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            # Extract the base number and extension
            full_match = match.group()
            
            # Split number and extension
            ext_match = re.search(r'(?:[xX]|ext|extension)[-.\s]?([0-9]{1,6})', full_match)
            extension = ext_match.group(1) if ext_match else None
            
            # Clean up the base number
            base_number = re.sub(r'(?:[xX]|ext|extension)[-.\s]?[0-9]{1,6}$', '', full_match)
            
            # Normalize the base number
            base_number = normalize_phone_number(base_number)
            
            # Add extension if present
            if extension:
                base_number = f"{base_number}x{extension}"
                
            if deduplicate:
                found.add(base_number)
            else:
                found.append(base_number)
            
    if deduplicate:
        return sorted(list(found))
    else:
        return found 