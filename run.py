import os
from flask import Flask, render_template, g, request, redirect, flash, send_file, session, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

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
app.config["MONGO_CLUSTER"] = os.environ.get("MONGO_CLUSTER")
app.config["MONGO_DB_NAME"] = os.environ.get("MONGO_DB_NAME")
app.config["MONGO_URI"] = f"mongodb+srv:" + \
                          f"//{os.environ.get('MONGO_DB_USER')}" + \
                          f":{os.environ.get('MONGO_DB_PASS')}" + \
                          f"@{app.config['MONGO_CLUSTER']}" + \
                          f".ueffo.mongodb.net" + \
                          f"/{app.config['MONGO_DB_NAME']}" + \
                          f"?retryWrites=true&w=majority"

app.config["MONGO_COLLECTIONS"] = {
    "categories": {
        "entity_name":"category",
        "title":"Task Categories",
        "fields":["description","icon"] # get icon names from https://fonts.google.com/icons?query=icon
    },
    "countries": {
        "entity_name":"country",
        "title":"Countries",
        "fields":["countryId","name","currencySign"]
    }
}

app.config["MONGO_COLLECTION_USERS"] = {
        "name":"users",
        "title":"Users",
        "fields":["username","password"] # field "user_is_admin" is absent for security reason, can be set in the DB only!
}
app.config["MONGO_COLLECTION_IMAGES"] = {
        "name":"images",
        "title":"Task Images",
        "fields":["source","image"]
}
app.config["MONGO_COLLECTION_TASKS"] = {
        "name":"tasks",
        "title":"Task Master",
        "fields":["name","description","is_urgent","due_date","is_complete","date_time_insert","date_time_update",
                  "category_id","image_id","user_id"]
}
app.config["MONGO_CONTENT"] = os.environ.get("MONGO_CONTENT","./static/data/mongo_content.json")
app.config["MONGO_INIT"]    = os.environ.get("MONGO_INIT",   "False").lower() in {'1','true','t','yes','y'}# => Heroku Congig Vars


# App routes
#==============
@app.route("/")  # trigger point through webserver: "/"= root directory
def index():
    return render_template("index.html", page_title="Home")


@app.route("/register", methods=['GET','POST'])
def register():
    if request.method == "GET":
        return render_template("reglog.html", register=True)
        
    # POST
    username_field = app.config["MONGO_COLLECTION_USERS"]['fields'][0]
    username = request.form.get(username_field).lower()
    password_field = app.config["MONGO_COLLECTION_USERS"]['fields'][1]
    # check if username already exists in db
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_USERS"]['name'])
    user_old = coll.find_one({username_field: username}, {'_id': 1})
    if user_old:
        flash("Username already exists", 'danger')
        return redirect(url_for("register"))

    user_new = {
        username_field: username,
        password_field: generate_password_hash(request.form.get(password_field))
    }
    # put the new user_id into 'session' cookie
    session['user_id'] = str(coll.insert_one(user_new).inserted_id)
    flash("Registration Successful!", "success")
    return redirect(url_for("tasks"))


@app.route("/login", methods=['GET','POST'])
def login():
    if request.method == "GET":
        return render_template("reglog.html", register=False)

    # POST    
    username_field = app.config["MONGO_COLLECTION_USERS"]['fields'][0]
    password_field = app.config["MONGO_COLLECTION_USERS"]['fields'][1]
    # check if username already exists in db
    username = request.form.get(username_field).lower()
    password = request.form.get(password_field)
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_USERS"]['name'])
    user_old = coll.find_one({username_field: username}, {password_field: 1, 'user_is_admin':1})
    if not user_old or not check_password_hash(user_old[password_field], password):
        flash("Incorrect Username and/or Password", 'danger')
        return redirect(url_for("login"))

    # put the user_id into session cookie
    session['user_id'] = str(user_old["_id"])
    if user_old.get('user_is_admin', None):
        session['user_is_admin'] = user_old["user_is_admin"]
    flash(f"Welcome, {username}", "success")
    return redirect(url_for("tasks"))


@app.route("/profile")
def profile():
    if request.method == "GET":
        if not session.get('user_id', None):
            return redirect(url_for("login"))
        coll = get_mongo_coll(app.config["MONGO_COLLECTION_USERS"]['name'])
        user = coll.find_one({'_id': ObjectId(session['user_id'])})
        return render_template("profile.html", user=user)


@app.route("/logout")
def logout():
    if session.get('user_id', None):
        session.pop('user_id')
        flash("You have been logged out", "info")
    if session.get('user_is_admin', None):
        session.pop('user_is_admin')
    return redirect(url_for("login"))


@app.route("/categories", methods=['GET','POST'])
def categories():
    return redirect(url_for('entities', collection_name=request.path.strip('/')))

@app.route("/countries", methods=['GET','POST'])
def countries():
    return redirect(url_for('entities', collection_name=request.path.strip('/')))

@app.route("/entities/<collection_name>", methods=['GET','POST'])
def entities(collection_name):
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    if not session.get('user_is_admin', None):
        return redirect(url_for("index"))
    # create an empty entity
    entity = {}
    if request.method == 'POST':
        entity = save_entity_to_db(request, collection_name, entity)
        if not entity:
            return redirect(url_for(collection_name))

    coll = get_mongo_coll(collection_name)
    entities = list(coll.find())
    if not entities:
        flash("There are no entities. Create one below!", 'info')
    return render_template("entities.html", 
        collection_name=collection_name,
        collection_meta=app.config["MONGO_COLLECTIONS"][collection_name],
        entities=entities, 
        last_entity=entity)


def save_entity_to_db(request, collection_name, entity_old):
    fields = app.config["MONGO_COLLECTIONS"][collection_name]['fields']
    entity_new = {f:request.form.get(f) for f in fields if request.form.get(f,None) is not None and request.form.get(f) != entity_old.get(f,None)}
    coll = get_mongo_coll(collection_name)
    try:
        if entity_old:
            # update existing entity
            coll.update_one({'_id':entity_old['_id']}, {"$set":entity_new})
        else:
            coll.insert_one(entity_new)
        # create empty entity - this clears the input fields, because the update was OK
        entity_new = {}
        flash(f"One entity successfully {'updated' if entity_old else 'added'}", "success")
    except:
        flash(f"Error in {'update' if entity_old else 'insert'} operation!", "danger")
    return entity_new


@app.route("/update/<collection_name>/<entity_id>", methods=['GET','POST'])
def update_entity(collection_name, entity_id):
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    if not session.get('user_is_admin', None):
        return redirect(url_for("index"))
    coll = get_mongo_coll(collection_name)
    entity = coll.find_one({"_id":ObjectId(entity_id)})
    if not entity:
        flash(f"{app.config['MONGO_COLLECTIONS'][collection_name]['entity_name']} {entity_id} does not exist", "danger")
        return redirect(url_for(collection_name))

    if request.method == 'POST':
        entity = save_entity_to_db(request, collection_name, entity)
        # if entity is empty, then the update was successful
        if not entity:
            return redirect(url_for(collection_name))

    entities = coll.find()
    return render_template("entities.html",
        page_title=app.config['MONGO_COLLECTIONS'][collection_name]["title"],
        collection_name=collection_name,
        entities=entities, 
        last_entity=entity)


@app.route("/delete/<collection_name>/<entity_id>", methods=['POST'])
def delete_entity(collection_name, entity_id):
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    if not session.get('user_is_admin', None):
        return redirect(url_for("index"))
    coll = get_mongo_coll(collection_name)
    entity = coll.find_one({"_id":ObjectId(entity_id)})
    if not entity:
        flash(f"Entity {entity_id} does not exist", "danger")
    else:
        # delete entity
        coll.delete_one({"_id":entity["_id"]})
        flash(f"Deleted entity {entity['description']}", "info")
    return redirect(url_for(collection_name))


@app.route("/tasks", methods=['GET','POST'])
def tasks():
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    # create an empty task
    task = {}
    if request.method == 'POST':
        task = save_task_to_db(request, task)
        # if task is empty, then the update was successful
        if not task:
            return redirect(url_for('tasks'))

    coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
    tasks = list(coll.find({'user_id':ObjectId(session['user_id'])}))
    if not tasks:
        flash("There are no tasks. Create one below!", "info")
    return render_template("tasks.html", 
        page_title=app.config["MONGO_COLLECTION_TASKS"]["title"],
        categories=get_entities('categories'),
        query="",
        tasks=tasks, 
        last_task=task)


@app.route("/search", methods=["GET", "POST"])
def search():
    query = request.form.get("query")
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
    tasks = list(coll.find({"$text": {"$search": query}}))
    if not tasks:
        flash("No results found", "warning")
    return render_template("tasks.html", 
        page_title=app.config["MONGO_COLLECTION_TASKS"]["title"],
        categories=get_entities('categories'),
        query=query,
        tasks=tasks, 
        last_task={})


@app.route("/tasks/update/<task_id>", methods=['GET','POST'])
def update_task(task_id):
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
    task = coll.find_one({"_id":ObjectId(task_id), "user_id":ObjectId(session["user_id"])})
    if not task:
        flash(f"Task {task_id} does not exist", "danger")
        return redirect(url_for('tasks'))

    if request.method == 'POST':
        task = save_task_to_db(request, task)
        # if task is empty, then the update was successful
        if not task:
            return redirect(url_for('tasks'))

    tasks = coll.find()
    return render_template("tasks.html", 
        page_title=app.config["MONGO_COLLECTION_TASKS"]["title"],
        categories=get_entities('categories'),
        query="",
        tasks=tasks, 
        last_task=task)


@app.route("/tasks/delete/<task_id>", methods=['POST'])
def delete_task(task_id):
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
    task = coll.find_one({"_id":ObjectId(task_id), "user_id":ObjectId(session["user_id"])})
    if not task:
        flash(f"Task {task_id} does not exist", "danger")
    else:
        # delete task
        coll.delete_one({"_id":task["_id"]})
        # delete image
        if task.get("image_id",None) is not None:
            coll = get_mongo_coll(app.config["MONGO_COLLECTION_IMAGES"]['name'])
            coll.delete_one({"_id":task["image_id"]})
    return redirect(url_for('tasks'))


@app.route("/tasks/image/<image_id>")
def serve_image(image_id):
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_IMAGES"]['name'])
    image = coll.find_one({"_id":ObjectId(image_id)})
    if image:
        return send_file(BytesIO(image['image']), mimetype='application/octet-stream')


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
        # initialize collections on DB from JSON file
        with open(app.config["MONGO_CONTENT"], mode='r', encoding="utf-8") as f:
            collections = json.loads(f.read())
            for coll_name,coll_docs in collections.items():
                coll = get_mongo_coll(coll_name)
                coll.delete_many({})
                if coll_docs:
                    coll.insert_many(coll_docs)
        # encrypt password in Users
        coll = get_mongo_coll(app.config["MONGO_COLLECTION_USERS"]['name'])
        users = list(coll.find())
        for user in users:
            password = generate_password_hash(user['password'])
            coll.update_one({'_id':user['_id']}, {"$set":{'password':password}})
        # get all categories from Categories
        coll = get_mongo_coll('categories')
        categories = list(coll.find())
        # in Tasks
        coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
        tasks = coll.find()
        for task in tasks:
            # add timestamp
            timestamp = datetime.utcnow().timestamp()
            # convert category description to _id in Tasks
            category_id = next((c['_id'] for c in categories if c['description'] == task['category_id']), '')
            # convert category description to _id in Tasks
            user_id = next((u['_id'] for u in users if u['username'] == task['user_id']), '')
            # convert due_date isodatestring to datetime
            due_date = datetime.strptime(task['due_date'], '%Y-%m-%d')
            # update a task in Tasks
            coll.update_one({'_id':task['_id']}, {"$set":{
                'date_time_insert': timestamp,
                'category_id':      category_id,
                'user_id':          user_id,
                'due_date':         due_date
                }})

        # create search index in Tasks
        coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
        coll.drop_indexes()
        coll.create_index([("name",pymongo.TEXT), 
                           ("description",pymongo.TEXT)], name='name_description')
        #print(coll.index_information())
 

def save_task_to_db(request, task_old):
    fields = app.config["MONGO_COLLECTION_TASKS"]['fields']
    task_new = {f:request.form.get(f) for f in fields if request.form.get(f,None) is not None and request.form.get(f) != task_old.get(f,None)}
    task_new['user_id'] = ObjectId(session['user_id'])
    due_date = request.form.get('due_date',None)
    if due_date == '':
        del task_new['due_date']
    elif due_date is not None:
        task_new['due_date'] = datetime.fromisoformat(due_date)
        print(task_new['due_date'],type(task_new['due_date']))

    category_id = task_new.get('category_id', None)
    if category_id:
        task_new['category_id'] = ObjectId(category_id)

    task_new['is_complete'] = True if task_new.get('is_complete', None)=='on' else False
    task_new['is_urgent']   = True if task_new.get('is_urgent',   None)=='on' else False
    # following instructions from https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
    data = request.files['SourceFileName']
    if data:
        filename_source = secure_filename(data.filename)
        extension = filename_source.rsplit('.', 1)[1] if '.' in filename_source else ''
        if extension in app.config["UPLOAD_EXTENSIONS"]:
            # store image
            image_new = {}
            image_new['source'] = filename_source
            image_new['image'] = Binary(data.read())
            coll = get_mongo_coll(app.config["MONGO_COLLECTION_IMAGES"]['name'])
            task_new["image_id"] = coll.insert_one(image_new).inserted_id
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
    try:
        if task_old:
            task_new['date_time_update'] = datetime.utcnow().timestamp()
            # update existing task
            coll.update_one({'_id':task_old['_id']}, {"$set":task_new})
            # delete old image
            if task_new.get("image_id", False) and task_old.get("image_id", False):
                coll = get_mongo_coll(app.config["MONGO_COLLECTION_IMAGES"]['name'])
                coll.delete_one({"_id":task_old["image_id"]})
        else:
            task_new['date_time_insert'] = datetime.utcnow().timestamp()
            coll.insert_one(task_new)
        # create empty task - this clears the input fields, because the update was OK
        task_new = {}
        flash(f"One task successfully {'updated' if task_old else 'added'}", "success")
    except:
        flash(f"Error in {'update' if task_old else 'insert'} operation!", "danger")
    return task_new


# inspired by https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
@app.template_filter('datetime_to_str')
def _jinja2_filter_datetime_to_str(dt, format):
    if dt:
        return dt.strftime(format)
    else:
        return str()


def get_entities(collection_name):
    if not getattr(g, "_collections", None):
        g._collections = {}
    entities = getattr(g._collections, collection_name, None)
    if entities is None:
        coll = get_mongo_coll(collection_name)
        if coll:
            entities = g._collections[collection_name] = { c['_id']:c for c in coll.find()}
    return entities


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
