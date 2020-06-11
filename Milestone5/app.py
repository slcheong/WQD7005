import requests
import pandas as pd
import re
import numpy as np
import math
import statistics 
import pytz
import gc
from sklearn.externals.joblib import load
from sklearn.metrics import mean_squared_error
from keras.models import Sequential
from keras.layers import Dense
from tensorflow.keras.models import model_from_json
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc
from flask_moment import Moment
from datetime import date,datetime, timedelta
from bs4 import BeautifulSoup


app = Flask(__name__)
moment = Moment(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///klci.db'
db = SQLAlchemy(app)
tz = pytz.timezone('Asia/Kuala_Lumpur')




class hp(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    date = db.Column(db.DateTime)
    openPrice = db.Column(db.Numeric(10,2))
    closePrice = db.Column(db.Numeric(10,2))
    high = db.Column(db.Numeric(10,2))
    low = db.Column(db.Numeric(10,2))

    def __repr__(self):
        return "<Task %r>" % self.date

class pred(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    date = db.Column(db.DateTime)
    closePrice = db.Column(db.Numeric(10,2))

    def __repr__(self):
        return "<Task %r>" % self.date

def isDataUpdated():
    lastUpdatedDate = hp.query.order_by(desc(hp.date)).first().date
    lastUpdatedDay = lastUpdatedDate.date().isoweekday()
    now = datetime.now(tz)
    today530pm = now.replace(hour=17, minute=30, second=0, microsecond=0)
    diff = now.date() - lastUpdatedDate.date()
    dayDiff = diff.days
    if (dayDiff > 3 ):
        return False
    elif (dayDiff == 3):
        if(lastUpdatedDay < 5):
            return False
        elif(now > today530pm):
            return False
        else:
            return True
    elif (dayDiff == 2 ):
        if(lastUpdatedDay < 5):
            return False
        else:
            return True
    elif(dayDiff == 1):
        if(now > today530pm):
            return False
        else:
            return True
    else:
        return True

def getHoliday():
    try:
        browserHeaders = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X '
            '10_14_3) AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/72.0.3626.109 Safari/537.36'}

        url = "https://www.bursamalaysia.com/about_bursa/about_us/calendar"

        #Go to the website
        respond = requests.get(url,headers=browserHeaders)

        # convert respond to soup
        soup = BeautifulSoup(respond.text, 'html.parser')

        # find desired table
        table = soup.find_all("div",{"class":"outer-wrap"})

        date = []
        # insert data row into data array
        for row in table[0:5]: ## first row is not data
            date.append(datetime.strptime(row.find("span",{"class":"ir_date"}).text,'%d %b %Y'))
    except:
        date = [datetime(2020,5,1,0,0),datetime(2020,5,7,0,0),datetime(2020,5,10,0,0),datetime(2020,5,24,0,0),datetime(2020,5,25,0,0),
            datetime(2020,6,1,0,0),datetime(2020,6,2,0,0),datetime(2020,6,8,0,0),datetime(2020,7,31,0,0)]
    
    return date

def nextTradingDay():
    lastUpdatedDate = hp.query.order_by(desc(hp.date)).first().date
    lastUpdatedDay = lastUpdatedDate.date().isoweekday()
    holiday = getHoliday()
    if(lastUpdatedDay < 5):
        nextDate = lastUpdatedDate + timedelta(days=1)
    else:
        nextDate = lastUpdatedDate + timedelta(days=3)
    while (nextDate in holiday or nextDate.isoweekday() > 5):
        nextDate += timedelta(days=1)
    return nextDate

def getData():
    # browser header setup 
    browserHeaders = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X '
                '10_14_3) AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/72.0.3626.109 Safari/537.36'}

    url = "https://finance.yahoo.com/quote/%5EKLSE%3FP%3D%5EKLSE/history"

    #Go to the website
    respond = requests.get(url,headers=browserHeaders)

    # convert respond to soup
    soup = BeautifulSoup(respond.text, 'html.parser')

    # find desired table
    table = soup.find("table")

    # find all rows
    allrow = table.find_all("tr")

    #initiate empty data array
    data = []

    # insert data row into data array
    for row in allrow[1:60]: ## first row is not data
        dataDetails = []
        cell = row.find_all("td")
        for i in range(len(cell)-2):
            if ( cell[i].text == "-"):
                continue
            elif (i == 0):
                dataDetails.append(cell[i].text)
            else:
                dataDetails.append(float(re.sub('[\,]', '',cell[i].text)))
        if (dataDetails[1] == "-"):
            continue
        else:
            data.insert(0,dataDetails)

    df = pd.DataFrame(data,columns = ["Date","Open","High","Low","Close"]) 
    df["Date"] = pd.to_datetime(df["Date"])

    return df


def updateDB(df):
    date = hp.query.order_by(desc(hp.date)).first().date
    for i in range(df.shape[0]):
        if (df.iloc[i,0] > date):
           data = hp(date = df.iloc[i,0], openPrice = df.iloc[i,1], closePrice = df.iloc[i,4], low = df.iloc[i,3], high = df.iloc[i,2])
           db.session.add(data)
           db.session.commit()
        else:
            continue

def isPredUpdated():
    lastPredDate = pred.query.order_by(desc(pred.date)).first().date
    if (lastPredDate == nextTradingDay()):
        return True
    else:
        return False

def getPriceFromDB():
    actualData = hp.query.order_by(desc(hp.date)).limit(60).all()
    closePrice = []
    for p in actualData:
        closePrice.insert(0,p.closePrice)
    return closePrice

def getPredFromDB():
    predData = pred.query.order_by(desc(pred.date)).limit(61).all()
    date, predPrice = [] , []
    for i in predData:
        date.insert(0,i.date)
        predPrice.insert(0,i.closePrice)
    closePrice = getPriceFromDB()
    return (date, closePrice, predPrice)

def prediction():
    # load model
    json_file = open('model.json', 'r')
    loaded_model_json = json_file.read()
    json_file.close()
    loaded_model = model_from_json(loaded_model_json)
    # load weights into new model
    loaded_model.load_weights("model.h5")

    # Get Latest Historical Data
    testData = hp.query.order_by(desc(hp.date)).limit(121).all()

    # get only close price 
    date, testPrice = [] , []
    for i in testData:
        date.insert(0,i.date)
        testPrice.insert(0,i.closePrice)
    date.append(nextTradingDay())

    # Change to np array to reshape
    testPrice = np.asarray(testPrice)

    # reshape array to apply sc transform
    testPrice = testPrice.reshape(-1,1)
    sc=load('std_scaler.bin')
    testPrice = sc.transform(testPrice)

    # prepare data for prediction
    X_test = []
    for i in range(60, testPrice.shape[0]):
        X_test.append(testPrice[i-60:i, 0])
    X_test = np.array(X_test)
    X_test = np.reshape(X_test, (X_test.shape[0], X_test.shape[1], 1))

    # perform prediction
    result = loaded_model.predict(X_test)

    # Return actual result
    normal_result = sc.inverse_transform(result)
    normal_result = np.array(normal_result).tolist()
    predPrice = []
    for i in normal_result:
        predPrice.append(round(i[0],4))
    return (date[61:122], predPrice)


def updatePredDB(date, prediction):
    lastPredDate = pred.query.order_by(desc(pred.date)).first().date
    if (lastPredDate == []):
        row=pred(date=date[i], closePrice = prediction[i])
        db.session.add(row)
        db.session.commit()
    else:    
        for i in range(len(date)):
            if(date[i] > lastPredDate):
                row=pred(date=date[i], closePrice = prediction[i])
                db.session.add(row)
                db.session.commit()
    
def calResult(closePrice, predPrice):
    rmse = math.sqrt(mean_squared_error(closePrice,predPrice[0:60]))
    mean = statistics.mean(closePrice)
    nrmse = rmse/float(mean)
    rmse = "%.4f" % round(rmse, 4)
    nrmse = "%.4f" % round(nrmse, 4)
    return rmse, nrmse


def defaultData():
    if (hp.query.all() == []):
        print("Loading Historical Data")
        df = pd.read_csv('KLCI.csv')
        df["Date"] = pd.to_datetime(df["Date"], format='%d/%m/%Y')
        for i in range(1,df.shape[0]-1):
           data = hp(date = df.iloc[i,0], openPrice = df.iloc[i,1], closePrice = df.iloc[i,2], low = df.iloc[i,3], high = df.iloc[i,4])
           db.session.add(data)
           db.session.commit()
    
    if (pred.query.all() == []):
        date, predictPrice = prediction()
        for i in range(len(date)):
            row=pred(date=date[i], closePrice = predictPrice[i])
            db.session.add(row)
            db.session.commit()


@app.route('/', methods=['GET', 'POST'])
def index(): 
    gc.collect()
    if request.method == "POST" :
        defaultData()
        if(isPredUpdated() == True and isDataUpdated() == True):
            date, closePrice, predictPrice = getPredFromDB()
            print("using db value")
        elif(isDataUpdated() == True):
            date, predictPrice = prediction()
            updatePredDB(date, predictPrice)
            closePrice = getPriceFromDB()
            print("update actual price db value")
        else:
            newData = getData()
            updateDB(newData)
            date, predictPrice = prediction()
            updatePredDB(date, predictPrice)
            closePrice = getPriceFromDB()
            print("update actual price & pred price db value")
        rmse, nrmse = calResult(closePrice, predictPrice)
        return render_template('index.html',close = closePrice, predictPrice = predictPrice, date = date, rmse = rmse, nrmse = nrmse)
    else:
        return render_template('loading.html')

if __name__ == "__main__":
    app.run(debug=True)
    # serve(app, host='0.0.0.0', port=8000)
