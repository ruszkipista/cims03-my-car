import os
from flask import Flask, render_template, g, request, redirect, flash, send_from_directory, send_file
from werkzeug.utils import secure_filename
import time

# Support for mongodb+srv:// URIs requires dnspython:
#!pip install dnspython pymongo
import pymongo
from bson.objectid import ObjectId
from bson.binary import Binary
from io import BytesIO
import json
from datetime import date, datetime
from math import floor
from itertools import zip_longest

# Support for Google Drive and Google Sheets API
#!pip install gspread google-auth
from google.oauth2.service_account import Credentials
import gspread

# env.py should exist only in Development
if os.path.exists("env.py"):
    import env


app = Flask(__name__)

# take app configuration from OS environment variables
app.secret_key               = os.environ.get("FLASK_SECRET_KEY")            # => Heroku Congig Vars
app.config["FLASK_IP"]       = os.environ.get("FLASK_IP",      "0.0.0.0")
# the source 'PORT' name is mandated by Heroku app deployment
app.config["FLASK_PORT"]     = int(os.environ.get("PORT"))
app.config["FLASK_DEBUG"]    = os.environ.get("FLASK_DEBUG",   "False").lower() in {'1','true','t','yes','y'}
app.config["UPLOAD_FOLDER"]  = os.environ.get("UPLOAD_FOLDER", "./data/")
app.config["UPLOAD_EXTENSIONS"] = set(['png', 'jpg', 'jpeg', 'gif'])
# SQLite parameters
app.config["SQLITE_INIT"]    = os.environ.get("SQLITE_INIT",   "False").lower() in {'1','true','t','yes','y'}# => Heroku Congig Vars
app.config["SQLITE_DB"]      = os.environ.get("SQLITE_DB",     "./data/taskmaster.sqlite") 
app.config["SQLITE_SCHEMA"]  = os.environ.get("SQLITE_SCHEMA", "./data/sqlite_schema.sql")
app.config["SQLITE_CONTENT"] = os.environ.get("SQLITE_CONTENT","./data/sqlite_content.sql")
app.config["SQLITE_TABLE_TODOS"] = "Todos"
app.config["COLUMNS_TODOS"]  = ('TaskId','Content','Completed','SourceFileName','LocalFileName','DatTimIns', 'DatTimUpd')
# MongoDB parameters
app.config["MONGO_INIT"]       = os.environ.get("MONGO_INIT",   "False").lower() in {'1','true','t','yes','y'}# => Heroku Congig Vars
app.config["MONGO_CONTENT"]    = os.environ.get("MONGO_CONTENT","./data/mongo_content.json")
app.config["MONGO_DB_NAME"]    = os.environ.get("MONGO_DB_NAME")
app.config["MONGO_CLUSTER"]    = os.environ.get("MONGO_CLUSTER")
app.config["MONGO_COLLECTION_CELEBS"] = 'celebrities'
app.config["MONGO_URI"] = f"mongodb+srv:" + \
                          f"//{os.environ.get('MONGO_DB_USER')}" + \
                          f":{os.environ.get('MONGO_DB_PASS')}" + \
                          f"@{app.config['MONGO_CLUSTER']}" + \
                          f".ueffo.mongodb.net" + \
                          f"/{app.config['MONGO_DB_NAME']}" + \
                          f"?retryWrites=true&w=majority"
# Google Sheets parameters
app.config["GSHEETS_SCOPE"] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
    ]

app.config["GSHEETS_CREDITS"] = json.loads(os.environ.get("GSHEETS_CREDITS"))
app.config["GSHEETS_SHEETS"]  = "Python CodeInstitute-love_sandwiches"
app.config["GSHEETS_PAGE"] = {
        "title":"Opening Stock - Sold = Surplus sandwiches on market days",
        "columns":['sale'+str(i) for i in range(6)]
}
app.config["GSHEETS_SALES_LOOKBACK"] = 5
app.config["GSHEETS_SALES_MARKUP"] = 1.1

# SQLite3 DB helpers
#=====================
import sqlite3
# SQLite pattern from https://flask.palletsprojects.com/en/1.1.x/patterns/sqlite3/
def get_sqlite_db():
    db = getattr(g, '_database_sqlite', None)
    if db is None:
        db = g._database_sqlite = sqlite3.connect(app.config["SQLITE_DB"])
        # use built-in row translator
        db.row_factory = sqlite3.Row
    return db


# inspired by SQLite pattern from https://flask.palletsprojects.com/en/1.1.x/patterns/sqlite3/
def init_sqlite_db(load_content=False):
    with app.app_context():
        db = get_sqlite_db()
        with app.open_resource(app.config["SQLITE_SCHEMA"], mode='r') as f:
            db.cursor().executescript(f.read())
        with app.open_resource(app.config["SQLITE_CONTENT"], mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


# inspired by SQLite pattern from https://flask.palletsprojects.com/en/1.1.x/patterns/sqlite3/        
def query_db(query, args=(), one=False):
    cur = get_sqlite_db().execute(query, args)
    rv = cur.fetchone() if one else cur.fetchall()
    cur.close()
    return (rv[0] if type(rv)==list else rv) if one else rv


# inspired by Example 1 from https://www.programcreek.com/python/example/3926/sqlite3.Row
def create_row(columns, values):
    """ convert column names and corresponding values into sqlite3.Row type object """
    cur = get_sqlite_db().cursor()
    if not cur:
        return None
    # generate "? AS <column>, ..."
    col_list = ", ".join([f"? AS '{col}'" for col in columns])
    query=f"SELECT {col_list};"
    return cur.execute(query, values).fetchone()


def insert_row(table:str, row:sqlite3.Row):
    """ insert one row into given table """
    cur = get_sqlite_db().cursor()
    if not cur:
        return 0
    try:
        columns = row.keys()
        values  = tuple(row[key] for key in columns)
        # generate list of column names
        col_list = ",".join(columns)
        # generate list of question marks
        qmark_list = ','.join('?'*len(columns))
        query=f"INSERT INTO {table} ({col_list}) VALUES ({qmark_list});"
        cur.execute(query, values)
        cur.connection.commit()
        return cur.lastrowid
    except sqlite3.Error as error:
        cur.connection.rollback()
        return error
 

def delete_row(table:str, id:int):
    """ delete one row by <rowid> from given table """
    cur = get_sqlite_db().cursor()
    if not cur:
        return ""
    try:
        query=f"DELETE FROM {table} WHERE rowid=?;"
        cur.execute(query, (id,))
        cur.connection.commit()
        return cur.rowcount
    except sqlite3.Error as error:
        cur.connection.rollback()
        return error


def update_row(table:str, row:sqlite3.Row, id:int):
    """ update one row by <rowid> from given table """
    cur = get_sqlite_db().cursor()
    if not cur:
        return ""
    try:
        columns = row.keys()
        values  = tuple([row[column] for column in columns]+[id])
        # generate "<column>=?,..." list
        set_list = ",".join([column+"=? " for column in columns])
        cur.execute(f"UPDATE {table} SET {set_list} WHERE rowid=?;", values)
        cur.connection.commit()
        return cur.rowcount
    except sqlite3.Error as error:
        cur.connection.rollback()
        return error

# inspired by https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
@app.template_filter('unix_time_ago')
def _jinja2_filter_time_ago(unix_timestamp:int):
    time_formats = (
        (60, 'seconds', 1),                           # 60
        (120, '1 minute ago', '1 minute from now'),   # 60*2
        (3600, 'minutes', 60),                        # 60*60, 60
        (7200, '1 hour ago', '1 hour from now'),      # 60*60*2
        (86400, 'hours', 3600),                       # 60*60*24, 60*60
        (172800, 'Yesterday', 'Tomorrow'),            # 60*60*24*2
        (604800, 'days', 86400),                      # 60*60*24*7, 60*60*24
        (1209600, 'Last week', 'Next week'),          # 60*60*24*7*4*2
        (2419200, 'weeks', 604800),                   # 60*60*24*7*4, 60*60*24*7
        (4838400, 'Last month', 'Next month'),        # 60*60*24*7*4*2
        (29030400, 'months', 2419200),                # 60*60*24*7*4*12, 60*60*24*7*4
        (58060800, 'Last year', 'Next year'),         # 60*60*24*7*4*12*2
        (2903040000, 'years', 29030400),              # 60*60*24*7*4*12*100, 60*60*24*7*4*12
        (5806080000, 'Last century', 'Next century'), # 60*60*24*7*4*12*100*2
        (58060800000, 'centuries', 2903040000)        # 60*60*24*7*4*12*100*20, 60*60*24*7*4*12*100
    )
    seconds = datetime.utcnow().timestamp() - unix_timestamp
    if 0 <= seconds < 1:
        return 'Just now'
    if seconds < 0 :
        seconds = abs(seconds)
        token = 'from now'
        list_choice = 2
    else:
        token = 'ago'
        list_choice = 1

    for format in time_formats:
        if seconds < format[0]:
            if type(format[2]) == str:
                return format[list_choice]
            else:
                return f"{floor(seconds / format[2])} {format[1]} {token}"
    return time


# App routing
#==============
@app.route("/")  # trigger point through webserver: "/"= root directory
def index():
    return render_template("index.html", page_title="Home")


@app.route("/about")
def about():
    return render_template("about.html", page_title="About")


@app.route("/todos", methods=['GET','POST'])
def todos():
    if request.method == 'POST':
        task = save_task_to_db(request, None)
    else:
        # create an empty task
        task = {}
    # get all tasks from DB
    tasks = query_db(f"SELECT * FROM {app.config['SQLITE_TABLE_TODOS']} ORDER BY Completed;")
    if not tasks:
        flash("There are no tasks. Create one above!")
    return render_template("todos.html", page_title="Task Master", request_path=request.path, tasks=tasks, last_task=task)


@app.route("/todos/update/<int:task_id>", methods=['GET','POST'])
def update_task(task_id):
    task = query_db(f"SELECT * FROM {app.config['SQLITE_TABLE_TODOS']} WHERE rowid=?;", (task_id,), one=True)
    if task is None:
        flash(f"Task {task_id} does not exist")
        return redirect("/todos")

    if request.method == 'POST':
        task = save_task_to_db(request, task)
        return redirect("/todos")

    tasks = query_db(f"SELECT * FROM {app.config['SQLITE_TABLE_TODOS']} ORDER BY Completed;")
    return render_template("todos.html", page_title="Task Master", tasks=tasks, last_task=task)


def save_task_to_db(request, task_old):
    columns = ['Content','Completed']
    values  = [request.form.get(column,'') for column in columns]
    # checkbox value conversion to integer
    values[1] = 1 if values[1]=="on" else 0

    # following instructions from https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
    data = request.files['SourceFileName']
    if data:
        filename_source = secure_filename(data.filename)
        extension = filename_source.rsplit('.', 1)[1] if '.' in filename_source else ''
        if extension in app.config["UPLOAD_EXTENSIONS"]:
            # generate a new image file name
            filename_local = str(time.time()).replace('.','')+'.'+extension
            columns += ['SourceFileName','LocalFileName']
            values  += [filename_source, filename_local]

    task_new = create_row(columns, values)
    if task_old:
        row_id = update_row(app.config["SQLITE_TABLE_TODOS"], task_new, task_old['TaskId'])
    else:
        row_id = insert_row(app.config["SQLITE_TABLE_TODOS"], task_new)
    # update was successful
    if type(row_id) == int:
        # save new file
        if data:
            data.save(os.path.join(app.config["UPLOAD_FOLDER"], filename_local))
            # delete old file
            if task_old and task_old['LocalFileName']:
                try:
                    os.remove(os.path.join(app.config["UPLOAD_FOLDER"], task_old['LocalFileName']))
                except FileNotFoundError as error:
                    flash(f"Could not delete {task_old['SourceFileName']}: {error}")

        # create empty task - this will be displayed, because the update was OK
        task_new = {}
        flash(f"One record successfully {'updated' if task_old else 'added'}")
    else:
        flash(f"Error in {'update' if task_old else 'insert'} operation: {row_id}")
    return task_new


@app.route("/todos/delete/<int:task_id>")
def delete_task(task_id):
    task = query_db(f"SELECT SourceFileName, LocalFileName FROM {app.config['SQLITE_TABLE_TODOS']} WHERE TaskId=?;", (task_id,), one=True)
    if task is None:
        flash(f"Task {task_id} does not exist")
    else:
        result = delete_row(app.config['SQLITE_TABLE_TODOS'], task_id)
        if type(result) == int:
            filename_local = task['LocalFileName']
            if filename_local:
                try:
                    os.remove(os.path.join(app.config["UPLOAD_FOLDER"], filename_local))
                except FileNotFoundError as error:
                    flash(f"Could not delete {task['SourceFileName']}: {error}")
            flash(f"{result} Record deleted")
        else:
            flash(f"Error in delete operation: {result}")
    return redirect('/todos')


@app.route("/uploads/<filename_local>")
def uploads(filename_local):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename_local)


@app.route("/contact", methods=['GET','POST'])
def contact():
    if request.method == 'POST':
        flash(f"Thanks {request.form.get('name')}, we have received your message!")
    return render_template("contact.html", page_title="Contact")


# MongoDB helpers
#=================
def get_mongo_coll(collection):
    conn = getattr(g, '_database_mongo', None)
    if conn is None:
        try:
            conn = g._database_mongo = pymongo.MongoClient(app.config["MONGO_URI"])
        except pymongo.errors.ConnectionFailure as e:
            print(f"Could not connect to MongoDB {app.config['MONGO_DB_NAME']}: {e}")
            return None
    return conn[app.config["MONGO_DB_NAME"]][collection]


def init_mongo_db(load_content=False):
    with app.app_context():
        with app.open_resource(app.config["MONGO_CONTENT"], mode='r') as f:
            collections = json.loads(f.read())
            for coll_name,coll_docs in collections.items():
                coll = get_mongo_coll(coll_name)
                coll.delete_many({})
                coll.insert_many(coll_docs)
 

def save_celeb_to_db(request, celeb_old):
    columns = ('first','last','dob','gender','hair_color','occupation','nationality')
    celeb_new  = {column:request.form.get(column,'') for column in columns if request.form.get(column,'') != celeb_old.get(column,'')}
    # following instructions from https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
    data = request.files['SourceFileName']
    if data:
        filename_source = secure_filename(data.filename)
        extension = filename_source.rsplit('.', 1)[1] if '.' in filename_source else ''
        if extension in app.config["UPLOAD_EXTENSIONS"]:
            # print(data)
            # store image
            celeb_new['Image'] = Binary(data.read())
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_CELEBS"])
    try:
        if celeb_old:
            coll.update_one({'_id':celeb_old['_id']}, {"$set":celeb_new})
        else:
            coll.insert_one(celeb_new)
        # create empty celeb - clear the input fields, because the update was OK
        celeb_new = {}
        flash(f"One document successfully {'updated' if celeb_old else 'added'}")
    except:
        flash(f"Error in {'update' if celeb_old else 'insert'} operation!")
    return celeb_new

# inspired by https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
@app.template_filter('isodate_to_str')
def _jinja2_filter_isodate_to_str(isodatestr, format):
    if isodatestr:
        return date.fromisoformat(isodatestr).strftime(format)
    else:
        return str()


# MongoDB routes
#=================
@app.route("/celebs", methods=['GET','POST'])
def celebs():
    if request.method == 'POST':
        celeb = save_celeb_to_db(request, {})
    else:
        celeb = {}
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_CELEBS"])
    celebs = coll.find()
    return render_template("celebs.html", page_title="Celebrities", celebs=celebs, last_celeb=celeb)


@app.route("/celebs/update/<celeb_id>", methods=['GET','POST'])
def update_celeb(celeb_id):
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_CELEBS"])
    celeb = coll.find_one({"_id":ObjectId(celeb_id)})
    if not celeb:
        flash(f"Document {celeb_id} does not exist")
        return redirect("/celebs")

    if request.method == 'POST':
        celeb = save_celeb_to_db(request, celeb)
        return redirect("/celebs")

    celebs = coll.find()
    return render_template("celebs.html", page_title="Celebrities", celebs=celebs, last_celeb=celeb)


@app.route("/celebs/delete/<celeb_id>")
def delete_celeb(celeb_id):
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_CELEBS"])
    celeb = coll.find_one({"_id":ObjectId(celeb_id)})
    if not celeb:
        flash(f"Document {celeb_id} does not exist")
        return redirect("/celebs")
    coll.delete_one({"_id":celeb["_id"]})
    celebs = coll.find()
    return render_template("celebs.html", page_title="Celebrities", celebs=celebs, last_celeb={})


@app.route("/celebs/image/<celeb_id>")
def image_celeb(celeb_id):
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_CELEBS"])
    celeb = coll.find_one({"_id":ObjectId(celeb_id)})
    if celeb and celeb['Image']:
        return send_file(BytesIO(celeb['Image']), mimetype='application/octet-stream')

# Google Sheets helpers
#=======================
def get_gsheet(sheet):
    sheets = getattr(g, '_database_gsheets', None)
    if sheets is None:
        try:
            CREDS = Credentials.from_service_account_info(app.config["GSHEETS_CREDITS"])
            SCOPED_CREDS = CREDS.with_scopes(app.config["GSHEETS_SCOPE"])
            GSPREAD_CLIENT = gspread.authorize(SCOPED_CREDS)
            sheets = GSPREAD_CLIENT.open(app.config["GSHEETS_SHEETS"])
        except:
            print(f"Could not connect to Google Sheets {app.config['GSHEETS_SHEETS']}")
            return None
    return sheets.worksheet(sheet)


def save_formdata_to_sheet(request, sheet, page):
    row  = [int(request.form.get(column,0)) for column in page['columns']]
    try:
        gsheet = get_gsheet(sheet)
        gsheet.append_row(row)
        flash(f"One row successfully added to {sheet}")
    except:
        flash(f"Error in append operation!")


# GoogleSheets routes
#=====================
@app.route("/sandwiches", methods=['GET','POST'])
def sandwiches():
    SHEET_SALES = 'sales'
    SHEET_STOCK = 'stock'
    if request.method == 'POST':
        save_formdata_to_sheet(request, request.form['submit'], app.config['GSHEETS_PAGE'])
        # stock_data = get_gsheet(SHEET_STOCK).get_all_values()
        # stock_row = stock_data[-1]
        # surplus_row = [int(stock)-sales for stock,sales in zip(stock_row,sales_row)]
        # print(surplus_row)

    stock_data = get_gsheet(SHEET_STOCK).get_all_values()
    sales_data = get_gsheet(SHEET_SALES).get_all_values()
    surplus_data = [[int(st)-int(sl) for st,sl in zip(stock,sales)] if i>0 else stock for i,(stock,sales) in enumerate(zip(stock_data,sales_data))]
    lookback = app.config["GSHEETS_SALES_LOOKBACK"]
    sales_lookback = [ [int(sales_data[row][col]) for row in range(-lookback, 0) ] for col in range(len(app.config["GSHEETS_PAGE"]["columns"]))]
    stock_suggest = [round(sum(col)/lookback*app.config["GSHEETS_SALES_MARKUP"]) for col in sales_lookback]
    return render_template("sandwiches.html", 
                            page_title="Love Sandwiches",
                            page_subtitle=app.config["GSHEETS_PAGE"]["title"],
                            request_path=request.path,
                            columns=app.config["GSHEETS_PAGE"]["columns"], 
                            data=zip_longest(stock_data,sales_data,surplus_data, fillvalue=[]),
                            suggest=stock_suggest
                        )


# Flask pattern from https://flask.palletsprojects.com/en/1.1.x/patterns/sqlite3/
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database_sqlite', None)
    if db is not None:
        db.close()

    db = getattr(g, '_database_mongo', None)
    if db is not None:
        db.close()

# Run the App
#=================
if __name__ == "__main__":
    if app.config["SQLITE_INIT"]:
        init_sqlite_db()

    if app.config["MONGO_INIT"]:
        init_mongo_db()

    app.run(
        host  = app.config["FLASK_IP"],
        port  = app.config["FLASK_PORT"],
        debug = app.config["FLASK_DEBUG"])