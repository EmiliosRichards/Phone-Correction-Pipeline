# 1

Step one for tomorrow/today test issue 2 and merge, finish issue 3 and merge, modulize the project, continue with additional tasks. issue 4? then phase two? think about benchmarks

Also in the last run I noticed a Rows Failed During Processing (Pass 1): 1

what does that mean? 

also i saw Scraping Failures (Other Errors): 1



and in Errors Encountered During Pipeline:
No significant errors recorded.

yet we did have errors

what does LLM_Not_Run_Or_NoOutput_For_Canonical and LLM_OutputEmpty_Or_NoRelevant_For_Canonical mean 

make a md file, have error metric, number of errors per type

delete intermediate data folder 

try .com when composing urls //

Did the original url amount to nothing, did the page fail, did the scraper or other part fail, what exactly happened so we can figure out if its fixable or out of our hands, We want to improve the system and know how its performing for clarity

Modulize and create tests for all pieces of the project


Make logs clearer? maybe include line reference for the .log or something for the errors so we can find and pinpoint them ? 

 - __main__ - WARNING - Spaces found in domain part 'DATEV Anwalt' for DATEV Anwalt. Removing them. for instance doesnt need to be in the console but it could appear in the error list. 
- main log should keep everything for debug and investigation. eroor list points us to main errors etc, console clean unless setting a log level

Effort 2: Strategize Testing for LLM Retry Logic.

# PHASE 1 -------------- COMPLETED

Enable header selection and working with the range config. // 

Test 2.5 Flash - 1.5 Flash - // 1.5 flash almost identical. //

Check the logs for failures and improve. <--------<

Add a logging to see which urls failed, perhaps so we can rerun them <--------<

Understand info/warning/ log levels

Add a final deliverable report for kevin Company name, URL, Number, Number Type, Note/Additional-info, number-found-at, Description? //

And metadata logging, Time spent, Accuracy etc - look at old system reports for ideas. //

Can we get a token count. Yes //

check usage and see how much it costs. //

Should we increase the snippet char size? avaraging 3000 tokens per api call (costs approx. 0.0005 dollars) 10000 api calls = 5 usd //

# PHASE 2 ----------------------

Modulise Phone Project <---------<

Set up the next project. 

HANDLED BY FUTURE ENHANCEMENT ----------------

Think about how we will eventually house and store all our data - companies and other. 

How will we handle duplicates in the input files?
We will want to eventually use the sql database for checking if we have already got this company in the system.
And store them correctly as unique records. 

Perhaps a seperate module for preprocessing/ storage? or All-in-One
Check with chat for the best way. 

Add async capabilities
Use the multiple instances of the system. Sql writes/ duplicate checking, passing args for input specification.
Adding pipeline usage monitoring and management. 
Check the workers/monitoring software from v1. CPU, Memory, and Disk assessmennt. 


Async:
Scraping Calls: asyncio.run() is called inside the loop. This starts and stops an asyncio event loop for each URL. For many URLs, this is inefficient. A single event loop managing concurrent scraping tasks for multiple URLs would be better.

---> CHECK docs\pipeline_scalability_enhancement_plan_20250521_105900.md

Can we benchmark accuracy and compare. Models/other <-----<

Add the upgrade? Big Enancement chat. Issue 3 Profile with webpage summerisation <------<


Setup system on contabo, <--------<









Time stamps in the attrition file are not useful, they are all the same, they are created when the file is created not when the error happens, this will be hard to check with the logs.


Obviously need to fix the rows being run to 1m - DONE

need to understand the files better, theres 1000 row in attrition. But many are the same company? 

Investigate if these are dupes 

Need to handle input data cleaning - jpynb

failed rows we have 2k+ - investigate. o

The metrics is good - but how can I found out how many urls were excluded due to leading to the same canonical



One day I will have to come back to where the rows begin when using range, and check that the exact numbers match the input and we are not losing track or 5+rows randomly when checking reports.