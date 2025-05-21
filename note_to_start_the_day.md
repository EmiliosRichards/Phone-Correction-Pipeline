Enable header selection and working with the range config. // 

Test 2.5 Flash - 1.5 Flash - // 1.5 flash almost identical. //

Check the logs for failures and improve.

Add a final deliverable report for kevin Company name, URL, Number, Number Type, Note/Additional-info, number-found-at, Description?

And metadata logging, Time spent, Accuracy etc - look at old system reports for ideas. 

Add a logging to see which urls failed, perhaps so we can rerun them

Can we get a token count. 

Setup system on contabo, check usage and see how much it costs. 

Add the upgrade? Big Enancement chat.  

Set up the next project. 

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