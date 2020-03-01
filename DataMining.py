from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import asyncio
import pandas as pd
import os
import time



#options = webdriver.ChromeOptions() 
#driver = webdriver.Chrome(chrome_options=options)
#options = Options()
#options.add_argument('--headless')
#options.add_argument('--disable-gpu')  # Last I checked this was necessary.
dirname = os.path.dirname(__file__)
downloadPath = os.path.join(dirname, 'stockPrice').replace("/","\\")

## Function to find the key of KLCI Stocks 
async def crawKLCIList():
    KLCIList = {}
    options = webdriver.ChromeOptions()
    ## Hide browser
    options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)

    ## Load Site
    url = "https://www.malaysiastock.biz/Market-Watch.aspx?type=C&value=KLCI"
    driver.get(url)

    ## Get all stock id and Name
    allRows = driver.find_elements(By.XPATH, '//*[@id="MainContent_tbStockWithAlphabet"]/tbody/tr')
    for row in allRows[1:]:
        code = row.find_elements(By.TAG_NAME,'td')[0].text
        name = row.find_elements(By.TAG_NAME,'td')[1].text
        KLCIList[code] = name
    driver.quit()
    return(KLCIList)

#Function to download historical stock price from yahoo finance
async def crawStockPrice(key,filePath):
    options = webdriver.ChromeOptions() 
    ## Do not show browser   
    options.add_argument('--headless')
    ## handle ssl error msg in console
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    ## To change default download path & allowed download with headless
    prefs = {"download.default_directory" : filePath,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing_for_trusted_sources_enabled": False,
            "safebrowsing.enabled": False}
    options.add_experimental_option("prefs",prefs)
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    
    ## load site 
    url = "https://finance.yahoo.com/quote/" + key +".KL/history"
    driver.get(url)
    ## filter time = max
    driver.find_element(By.XPATH, '//*[@id="Col1-1-HistoricalDataTable-Proxy"]/section/div[1]/div[1]/div[1]/div/div/div/span').click()
    driver.find_element(By.XPATH, '//*[@id="dropdown-menu"]/div/ul[2]/li[4]/button').click()
    
    ## if same file name exist, remove it -- remove old data
    fileName = filePath+ "\\" + key+".KL.csv"
    if (os.path.exists(fileName)):
        os.remove(fileName)
    
    ## Download File
    link = driver.find_element(By.XPATH,'//*[@id="Col1-1-HistoricalDataTable-Proxy"]/section/div[1]/div[2]/span[2]/a')
    link.click()

    #Wait for complete download before quit
    while not os.path.exists(fileName):
        time.sleep(1)
    driver.quit()
    return({})
    
async def main():
    stocks = await crawKLCIList()
    stockKeys = list (stocks.keys())
    print(stockKeys)
    for key in stockKeys:
        await crawStockPrice(key,downloadPath)


asyncio.run(main())




