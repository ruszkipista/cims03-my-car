import os
from flask import Flask, render_template, g, request, redirect, flash, send_file
from werkzeug.utils import secure_filename

# Support for mongodb+srv:// URIs requires dnspython:
#!pip install dnspython pymongo
import pymongo
from bson.objectid import ObjectId
from bson.binary import Binary
from io import BytesIO
import json
import time
from datetime import date, datetime

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
app.config["UPLOAD_EXTENSIONS"] = set(['png', 'jpg', 'jpeg', 'gif'])

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

# MongoDB routes
#=================
@app.route("/tasks", methods=['GET','POST'])
def tasks():
    if request.method == 'POST':
        task = save_task_to_db(request, {})
    else:
        task = {}
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_taskS"])
    tasks = coll.find()
    return render_template("tasks.html", page_title="taskrities", tasks=tasks, last_task=task)


@app.route("/tasks/update/<task_id>", methods=['GET','POST'])
def update_task(task_id):
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_taskS"])
    task = coll.find_one({"_id":ObjectId(task_id)})
    if not task:
        flash(f"Document {task_id} does not exist")
        return redirect("/tasks")

    if request.method == 'POST':
        task = save_task_to_db(request, task)
        return redirect("/tasks")

    tasks = coll.find()
    return render_template("tasks.html", page_title="taskrities", tasks=tasks, last_task=task)


@app.route("/tasks/delete/<task_id>")
def delete_task(task_id):
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_taskS"])
    task = coll.find_one({"_id":ObjectId(task_id)})
    if not task:
        flash(f"Document {task_id} does not exist")
        return redirect("/tasks")
    coll.delete_one({"_id":task["_id"]})
    tasks = coll.find()
    return render_template("tasks.html", page_title="taskrities", tasks=tasks, last_task={})


@app.route("/tasks/image/<task_id>")
def image_task(task_id):
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKSS"])
    task = coll.find_one({"_id":ObjectId(task_id)})
    if task and task['Image']:
        return send_file(BytesIO(task['Image']), mimetype='application/octet-stream')


# App routing
#==============
@app.route("/")  # trigger point through webserver: "/"= root directory
def index():
    return render_template("index.html", page_title="Home")


@app.route("/tasks", methods=['GET','POST'])
def tasks():
    if request.method == 'POST':
        task = save_task_to_db(request, None)
    else:
        # create an empty task
        task = {}
    # get all tasks from DB
    tasks = query_db(f"SELECT * FROM {app.config['SQLITE_TABLE_TODOS']} ORDER BY Completed;")
    if not tasks:
        flash("There are no tasks. Create one above!")
    return render_template("tasks.html", page_title="Task Master", request_path=request.path, tasks=tasks, last_task=task)


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
    return render_template("tasks.html", page_title="Task Master", tasks=tasks, last_task=task)


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
 

def save_task_to_db(request, task_old):
    columns = ('first','last','dob','gender','hair_color','occupation','nationality')
    task_new  = {column:request.form.get(column,'') for column in columns if request.form.get(column,'') != task_old.get(column,'')}
    # following instructions from https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
    data = request.files['SourceFileName']
    if data:
        filename_source = secure_filename(data.filename)
        extension = filename_source.rsplit('.', 1)[1] if '.' in filename_source else ''
        if extension in app.config["UPLOAD_EXTENSIONS"]:
            # print(data)
            # store image
            task_new['Image'] = Binary(data.read())
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"])
    try:
        if task_old:
            coll.update_one({'_id':task_old['_id']}, {"$set":task_new})
        else:
            coll.insert_one(task_new)
        # create empty task - clear the input fields, because the update was OK
        task_new = {}
        flash(f"One document successfully {'updated' if task_old else 'added'}")
    except:
        flash(f"Error in {'update' if task_old else 'insert'} operation!")
    return task_new

# inspired by https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
@app.template_filter('isodate_to_str')
def _jinja2_filter_isodate_to_str(isodatestr, format):
    if isodatestr:
        return date.fromisoformat(isodatestr).strftime(format)
    else:
        return str()

# inspired by https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
from math import floor
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


# Flask pattern from https://flask.palletsprojects.com/en/1.1.x/patterns/sqlite3/
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database_mongo', None)
    if db is not None:
        db.close()

# Run the App
#=================
if __name__ == "__main__":
    if app.config["MONGO_INIT"]:
        init_mongo_db()

    app.run(
        host  = app.config["FLASK_IP"],
        port  = app.config["FLASK_PORT"],
        debug = app.config["FLASK_DEBUG"])
