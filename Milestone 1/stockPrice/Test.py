import mysql.connector


mydb = mysql.connector.connect(
  host="localhost",
  user="root",
  passwd="B3g00d!!"
)


mycursor = mydb.cursor()

mycursor.execute("USE hive")
sql = "INSERT INTO customers (name, address) VALUES (%s, %s)"
val = ("John", "Highway 21")
mycursor.execute(sql, val)
mycursor.execute("SELECT * FROM customers")

myresult = mycursor.fetchall()

for x in myresult:
  print(x)

