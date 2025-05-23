(.venv) PS C:\Users\EmiliosRichards\Projects\Phone Extraction\6 - Phone-Correction-Pipeline> python main_pipeline.py
INFO: Resolved relative INPUT_FILE_PATH to absolute: C:\Users\EmiliosRichards\Projects\Phone Extraction\6 - Phone-Correction-Pipeline\data\data_to_be_inputed.xlsx
DEBUG: main_pipeline.py - Effective console_log_level_int: 30 (WARNING)
DEBUG: main_pipeline.py - AppConfig console_log_level raw value: 'WARNING'
2025-05-23 15:32:18 - src.scraper.scraper_logic - WARNING - [RowID: 6, Company: Hartmann International] HTTP error for http://hartmann-international.de/: Status 403 . No content fetched.
2025-05-23 15:32:18 - src.scraper.scraper_logic - WARNING - [RowID: 6, Company: Hartmann International] Failed to fetch content from 'http://hartmann-international.de/' (normalized from original input). Status code: 403. This URL will not be processed further.
2025-05-23 15:32:18 - src.scraper.scraper_logic - ERROR - [RowID: 6, Company: Hartmann International] Critical failure on initial URL 'http://hartmann-international.de/'. Scraper status: HTTPError_403. No canonical URL determined.
2025-05-23 15:32:18 - __main__ - ERROR - CRITICAL: Failed to write to failure_log_csv: I/O operation on closed file.. Row ID: 6, Stage: Scraping_HTTPError_403, Timestamp: 2025-05-23T15:32:18.305781
Traceback (most recent call last):
  File "C:\Users\EmiliosRichards\Projects\Phone Extraction\6 - Phone-Correction-Pipeline\main_pipeline.py", line 100, in log_row_failure
    failure_log_writer.writerow(row_to_write)
ValueError: I/O operation on closed file.
2025-05-23 15:34:18 - src.scraper.scraper_logic - ERROR - [RowID: 17, Company: DHL Global Forwarding] Playwright error during navigation to http://dhl.com/: Page.goto: net::ERR_HTTP2_PROTOCOL_ERROR at http://dhl.com/
Call log:
  - navigating to "http://dhl.com/", waiting until "domcontentloaded"

2025-05-23 15:34:18 - src.scraper.scraper_logic - WARNING - [RowID: 17, Company: DHL Global Forwarding] Failed to fetch content from 'http://dhl.com/' (normalized from original input). Status code: -4. This URL will not be processed further.
2025-05-23 15:34:18 - src.scraper.scraper_logic - ERROR - [RowID: 17, Company: DHL Global Forwarding] Critical failure on initial URL 'http://dhl.com/'. Scraper status: PlaywrightError. No canonical URL determined.
2025-05-23 15:34:18 - __main__ - ERROR - CRITICAL: Failed to write to failure_log_csv: I/O operation on closed file.. Row ID: 17, Stage: Scraping_PlaywrightError, Timestamp: 2025-05-23T15:34:18.252918
Traceback (most recent call last):
  File "C:\Users\EmiliosRichards\Projects\Phone Extraction\6 - Phone-Correction-Pipeline\main_pipeline.py", line 100, in log_row_failure
    failure_log_writer.writerow(row_to_write)
ValueError: I/O operation on closed file.




Adding the rotating thing tls


Okay, some of the things that we need to do is check the TLD rotating thing. We also need to go and, I guess, check a whole bunch of other log things, failures, so many things that we can update. I guess, let me have a look at the note start day. I think everything looks pretty good for now. Everything I needed to do for now, at least. But there's so many updates and stuff that we can investigate and look further.


SHOULD PROBABLY MODULISE SOOON 