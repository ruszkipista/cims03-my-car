import os
import certifi
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

app.config["OS_DATA_PATH"] = os.environ.get("OS_DATA_PATH","./static/data/")
app.config["MONGO_BASE"] = os.environ.get("MONGO_BASE","db_base.json")
app.config["MONGO_DEMO"] = os.environ.get("MONGO_DEMO","db_demo.json")
app.config["MONGO_INIT"] = os.environ.get("MONGO_INIT",   "False").lower() in {'1','true','t','yes','y'}# => Heroku Congig Vars
app.config["MONGO_IMAGES"]            = 'images'
app.config["MONGO_USERS"]             = 'users'
app.config["MONGO_CARS"]              = 'cars'
app.config["MONGO_FIELDCATALOG"]      = 'fieldcatalog'
app.config["MONGO_CURRENCIES"]        = 'currencies'
app.config["MONGO_COUNTRIES"]         = 'countries'
app.config["MONGO_MEASURE_TYPES"]     = 'measure_types'
app.config["MONGO_UNIT_OF_MEASURES"]  = 'unit_of_measures'
app.config["MONGO_UNIT_CONVERSIONS"]  = 'unit_conversions'
app.config["MONGO_EXPENDITURE_TYPES"] = 'expenditure_types'
app.config["MONGO_MATERIAL_TYPES"]    = 'material_types'
app.config["MONGO_RELATIONSHIP_TYPES"]= 'relationship_types'
app.config["MONGO_MATERIALS"]         = 'materials'


# inspired by https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
from math import floor
def translate_unix_timestamp_to_time_ago_text(unix_timestamp:int):
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
    seconds = get_utc_timestamp() - unix_timestamp
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


def get_utc_timestamp():
    return datetime.utcnow().timestamp()

    
def get_form_reglog_field_username(request):
    return request.form.get('username', None)


def get_form_reglog_field_password(request):
    return request.form.get('password', None)


def get_form_reglog_field_is_admin(request):
    return request.form.get('user_is_admin', None)


def get_form_profile_field_password_old(request):
    return request.form.get('password_old', None)


def get_form_profile_field_password_new(request):
    return request.form.get('password_new', None)


def get_form_search_field_query(request):
    return request.form.get("query")


# MongoDB
#=========
def get_db_collection(collection):
    conn = getattr(g, '_database_mongo', None)
    if conn is None:
        try:
            conn = g._database_mongo = pymongo.MongoClient(app.config["MONGO_URI"], tlsCAFile=certifi.where())
        except pymongo.errors.ConnectionFailure as e:
            print(f"Could not connect to MongoDB {app.config['MONGO_DB_NAME']}: {e}")
            return None
    return conn[app.config["MONGO_DB_NAME"]][collection]


def insert_db_user(username, password, is_admin):
    user_new = {
        "username": username,
        "is_admin": is_admin,
        "password": generate_password_hash(password),
        "date_time_insert": get_utc_timestamp()
    }
    loggedin_user = get_db_user_id()
    if loggedin_user:
        user_new["changed_by"] = loggedin_user
    return insert_db_record(app.config["MONGO_USERS"], user_new)


def get_db_user_by_name(username):
    coll = get_db_collection(app.config["MONGO_USERS"])
    user = coll.find_one({"username": username.lower()}, {"password": 1, 'user_is_admin':1})
    return user


def get_db_user_by_id(user_id):
    return get_db_record_by_id(app.config["MONGO_USERS"], user_id)


def get_db_user_id(user=None):
    if user:
        return user.get('_id', None)
    user_id = session.get('user_id', None)
    if user_id:
        return ObjectId(user_id)
    else:
        return user_id


def get_db_user_password(record):
    return record.get('password', None)


def get_db_user_is_admin(user=None):
    if user:
        return user.get('user_is_admin', None)
    else:
        return session.get('user_is_admin', None)


def login_db_user(user):
    session['user_id'] = str(get_db_user_id(user))
    session['user_is_admin'] = get_db_user_is_admin(user)


def logout_db_user():
    if session.get('user_id', None):
        session.pop('user_id')
        session.pop('user_is_admin')


def set_db_user_password(user_id, password_new):
    user_update = {
        "password":         generate_password_hash(password_new),
        "changed_by":       ObjectId(session['user_id']),
        "date_time_update": get_utc_timestamp()
    }
    coll = get_db_collection(app.config["MONGO_USERS"])
    result = coll.update_one({'_id':user_id}, {"$set":user_update})
    return result.modified_count == 1


def get_db_image_by_id(image_id):
    return get_db_record_by_id(app.config["MONGO_IMAGES"], image_id)


def get_db_all_records(collection_name):
    coll = get_db_collection(collection_name)
    return list(coll.find())


def get_db_records(collection_name):
    if not getattr(g, "_collections", None):
        g._collections = {}
    records = getattr(g._collections, collection_name, None)
    if records is None:
        coll = get_db_collection(collection_name)
        if coll:
            if collection_name==app.config["MONGO_FIELDCATALOG"]:
                records = g._collections[collection_name] = {doc["collection_name"]:doc for doc in coll.find()}
            else:
                records = g._collections[collection_name] = { c['_id']:c for c in coll.find()}
    return records


def get_db_select_field_lookup(collection_name):
    if not getattr(g, "_lookups", None):
        g._lookups = {}
    records = getattr(g._lookups, collection_name, None)
    if records is None:
        coll = get_db_collection(collection_name)
        if coll:
            fieldcatalog = get_db_fieldcatalog(collection_name)
            select_field = fieldcatalog.get('select_field', None)
            if select_field:
                records = g._lookups[collection_name] = { c[select_field]:c['_id'] for c in coll.find()}
            else:
                records = g._lookups[collection_name] = {}
    return records


def get_db_filtered_records(collection_name, query):
    coll = get_db_collection(collection_name)
    return list(coll.find({"$text": {"$search": query}}))


def get_db_entity_name(collection_name):
    coll_fieldcatalog = get_db_fieldcatalog(collection_name)
    return coll_fieldcatalog["entity_name"]


def get_db_fieldcatalog(collection_name=None):
    fieldcatalog = get_db_records(app.config["MONGO_FIELDCATALOG"])
    if collection_name:
        return fieldcatalog[collection_name]
    else:
        return fieldcatalog


def get_db_record_by_id(collection_name, record_id):
    coll = get_db_collection(collection_name)
    return coll.find_one({"_id":ObjectId(record_id)})


def get_db_field_lookup_pairs(collection_name, field_names):
    return [ (f, get_db_lookup_collection_name(collection_name, f)) for f in field_names ]


def insert_db_record(collection_name, record):
    coll = get_db_collection(collection_name)
    record["_id"] = coll.insert_one(record).inserted_id
    return record


def update_db_record(collection_name, record_old, record_new):
    coll = get_db_collection(collection_name)
    coll.update_one({"_id":record_old["_id"]}, {"$set":record_new})


def delete_db_record(collection_name, record):
    coll = get_db_collection(collection_name)
    coll.delete_one({"_id":record["_id"]})


def get_db_is_admin_maintainable(collection_name):
    coll_fieldcatalog = get_db_fieldcatalog(collection_name)
    return coll_fieldcatalog.get('admin', None)


def insert_db_many_records(collection_name, records):
    coll = get_db_collection(collection_name)
    coll.insert_many(records)


def delete_db_all_records(collection_name):
    coll = get_db_collection(collection_name)
    coll.delete_many({})


def get_db_lookup_collection_name(source_collection_name, source_field_name):
    coll_fields = get_db_fieldcatalog(source_collection_name)['fields']
    field_def = next((f for f in coll_fields if f['name']==source_field_name), '')
    lookup_collection_name = field_def.get('values', None)
    return lookup_collection_name


def translate_db_password_to_hash(source_field_name, record):
    record[source_field_name] = generate_password_hash(record[source_field_name])


def translate_db_value_to_id(source_field_name, lookup_collection_name, record):
    lookup = get_db_select_field_lookup(lookup_collection_name)
    lookup_value = lookup.get(record[source_field_name], None)
    if lookup_value:
        record[source_field_name] = lookup_value


def translate_db_image_to_id(source_field_name, record):
    filename = record[source_field_name]
    if filename:
        with open(os.path.join(app.config["OS_DATA_PATH"], filename), mode='rb') as image_file:
            # read file into memory
            image_binary = Binary(image_file.read())
            # insert image into DB, update the record with new ID
            record[source_field_name] = insert_db_image(filename, image_binary)


def insert_db_image(filename, image_binary):
    image_new = { 
        'source': filename, 
        'image':  image_binary
    }
    image_new = insert_db_record(app.config["MONGO_IMAGES"], image_new)
    return image_new['_id']


def init_db_mongo(file_name, clear_content=False):
    with app.app_context():
        # initialize collections on DB from JSON file
        with open(file_name, mode='r', encoding="utf-8") as f:
            collections = json.loads(f.read())

            if clear_content:
                fieldcatalog = []
                for coll_name,coll_docs in collections.items():
                    # filter fieldcatalog records
                    for doc in coll_docs:
                        if doc.get("entity_name", False):
                            doc["collection_name"] = coll_name
                            fieldcatalog.append(doc)
                # write out Fieldcatalog
                coll_fieldcatalog = get_db_collection(app.config["MONGO_FIELDCATALOG"])
                if fieldcatalog:
                    coll_fieldcatalog.delete_many({})
                    coll_fieldcatalog.insert_many(fieldcatalog)

            for coll_name,coll_docs in collections.items():
                if clear_content:
                    delete_db_all_records(coll_name)
                # filter data records
                coll_records = []
                for doc in coll_docs:
                    if not doc.get("entity_name", False):
                        coll_records.append(doc)

                if coll_name=="users":
                    coll_records = init_db_users(coll_name, coll_records)
                elif coll_name=="currency_conversions":
                    coll_records = init_db_currency_conversions(coll_name, coll_records)
                elif coll_name=="countries":
                    coll_records = init_db_countries(coll_name, coll_records)
                elif coll_name=="unit_of_measures":
                    coll_records = init_db_unit_of_measures(coll_name, coll_records)
                elif coll_name=="unit_conversions":
                    coll_records = init_db_unit_conversions(coll_name, coll_records)
                elif coll_name=="material_types":
                    coll_records = init_db_material_types(coll_name, coll_records)
                elif coll_name=="materials":
                    coll_records = init_db_materials(coll_name, coll_records)
                elif coll_name=="cars":
                    coll_records = init_db_cars(coll_name, coll_records)
                elif coll_name=="users_cars":
                    coll_records = init_db_users_cars(coll_name, coll_records)

                if coll_records:
                    insert_db_many_records(coll_name, coll_records)

            if clear_content:
                # create index for unique field(s)
                for coll_def in fieldcatalog:
                    unique_fields = [ (field["name"], pymongo.ASCENDING) 
                                        for field in coll_def["fields"] if field.get("unique", False)]
                    if unique_fields:
                        coll = get_db_collection(coll_def["collection_name"])
                        coll.create_index(unique_fields, unique=True)


def init_db_users(collection_name, records):
    for record in records:
        # encrypt password in user
        translate_db_password_to_hash('password', record)
        # set time stamp
        record['date_time_insert'] = get_utc_timestamp()
    return records


def init_db_images(coll_name, coll_records):
    pass


def init_db_currency_conversions(collection_name, records):
    field_names = ['currency_id_from','currency_id_to']
    field_lookup_pairs = get_db_field_lookup_pairs(collection_name, field_names)
    for record in records:
        # convert From Date isodatestring to datetime
        record['from_date'] = datetime.strptime(record['from_date'], '%Y-%m-%d')
        # convert Currency ID to _id
        for field, lookup in field_lookup_pairs:
            translate_db_value_to_id(field, lookup, record)
    return records


def init_db_countries(collection_name, records):
    field_names = ['currency_id']
    field_lookup_pairs = get_db_field_lookup_pairs(collection_name, field_names)
    for record in records:
        # convert Currency ID to _id
        for field, lookup in field_lookup_pairs:
            translate_db_value_to_id(field, lookup, record)
    return records


def init_db_unit_of_measures(collection_name, records):
    field_names = ['measure_type_id']
    field_lookup_pairs = get_db_field_lookup_pairs(collection_name, field_names)
    for record in records:
        # convert Measure Type ID to _id
        for field, lookup in field_lookup_pairs:
            translate_db_value_to_id(field, lookup, record)
    return records


def init_db_unit_conversions(collection_name, records):
    field_names = ['uom_id_from','uom_id_to']
    field_lookup_pairs = get_db_field_lookup_pairs(collection_name, field_names)
    for record in records:
        # convert Unit of Measure ID to _id
        for field, lookup in field_lookup_pairs:
            translate_db_value_to_id(field, lookup, record)
    return records


def init_db_material_types(collection_name, records):
    field_names = ['measure_type_id','expenditure_type_id']
    field_lookup_pairs = get_db_field_lookup_pairs(collection_name, field_names)
    for record in records:
        # convert Measure Type ID and Expenditure Type ID to _id
        for field, lookup in field_lookup_pairs:
            translate_db_value_to_id(field, lookup, record)
    return records


def init_db_materials(collection_name, records):
    field_names = ['material_type_id']
    field_lookup_pairs = get_db_field_lookup_pairs(collection_name, field_names)
    for record in records:
        # convert Material Type ID to _id
        for field, lookup in field_lookup_pairs:
            translate_db_value_to_id(field, lookup, record)
    return records


def init_db_cars(collection_name, records):
    field_names = ['reg_country_id','distance_unit_id', 'odometer_unit_id', 'fuel_material_id',
                   'fuel_unit_id', 'fuel_economy_unit_id', 'currency_id']
    field_lookup_pairs = get_db_field_lookup_pairs(collection_name, field_names)
    for record in records:
        # save image to images collection and reference the _id
        translate_db_image_to_id('car_image_id', record)
        # convert Registration Country, Distance Unit, Odometer Unit, Fuel Material ID,
        # Fuel Unit, Fuel Economy Unit, Currency ID, Image FileName to _id
        for field, lookup in field_lookup_pairs:
            translate_db_value_to_id(field, lookup, record)
    return records


def init_db_users_cars(collection_name, records):
    field_names = ['user_id', 'car_id', 'relationship_id']
    field_lookup_pairs = get_db_field_lookup_pairs(collection_name, field_names)
    for record in records:
        # convert User Name, Car ID, Relationship ID to _id
        for field, lookup in field_lookup_pairs:
            print(field, lookup, record)
            translate_db_value_to_id(field, lookup, record)
    return records


# App routes
#==============
@app.route("/")  # trigger point through webserver: "/"= root directory
def index():
    # is logged in user valid?
    loggedin_user = get_loggedin_user()
    return render_template("index.html", page_title="Home")


@app.route("/register", methods=['GET','POST'])
def register():
    if request.method == "GET":
        return render_template("reglog.html", register=True)
        
    # request.method == POST
    username_entered = get_form_reglog_field_username(request)
    # check if username already exists in db
    user_old = get_db_user_by_name(username_entered)
    if user_old:    
        flash(f"Username already exists", 'danger')
        return redirect(url_for("register"))

    password_entered = get_form_reglog_field_password(request)
    is_admin_entered = get_form_reglog_field_is_admin(request)
    user_new = insert_db_user(username_entered, password_entered, is_admin_entered)

    # put the new user_id into 'session' cookie
    login_db_user(user_new)
    flash("Registration Successful!", "success")
    return redirect(url_for("index"))


@app.route("/login", methods=['GET','POST'])
def login():
    if request.method == "GET":
        return render_template("reglog.html", register=False)

    # request.method == POST
    username_entered = get_form_reglog_field_username(request)
    password_entered = get_form_reglog_field_password(request)
    user_old = get_db_user_by_name(username_entered)
    if user_old:
        password_stored = get_db_user_password(user_old)
    # check if username does not exist in db
    # or stored and entered passwords differ
    if not user_old or not check_password_hash(password_stored, password_entered):
        flash(f"Incorrect Username and/or Password", 'danger')
        return redirect(url_for("login"))

    # put the user_id into session cookie
    login_db_user(user_old)
    flash(f"Welcome, {username_entered}", "success")
    # different landing page for Administrator and Normal users
    if get_db_user_is_admin():
        return redirect(url_for("index"))
    else:
        return redirect(url_for("maintain", collection_name=app.config["MONGO_CARS"]))


@app.route("/logout")
def logout():
    # is a user logged in?
    loggedin_user_id = get_db_user_id()
    if loggedin_user_id:
        logout_db_user()
        flash("You have been logged out", "info")       
    return redirect(url_for("index"))


@app.route("/profile", methods=['GET','POST'])
def profile():
    loggedin_user = get_loggedin_user()
    if not loggedin_user:
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("profile.html", user=loggedin_user)

    # request.method == POST
    password_old = get_form_profile_field_password_old(request)
    password_stored = get_db_user_password(loggedin_user)
    if not check_password_hash(password_stored, password_old):
        flash("Wrong old password", 'danger')
        return redirect(url_for("profile"))

    password_new = get_form_profile_field_password_new(request)
    if check_password_hash(password_stored, password_new):
        flash("Old and New passwords are the same, not changed!", "warning")
        return redirect(url_for("profile"))

    # update password in DB
    is_update_ok = set_db_user_password(get_db_user_id(), password_new)
    if is_update_ok:
        flash("Your password has been changed", "success")
    return render_template("profile.html", user=loggedin_user)


def get_loggedin_user():
    loggedin_user = {}
    # is a user logged in?
    loggedin_user_id = get_db_user_id()
    if loggedin_user_id:
        # get user record from DB
        loggedin_user = get_db_user_by_id(loggedin_user_id)
        if not loggedin_user:
            logout_db_user()
            flash("Invalid logged in user has been logged out!", 'danger')
    return loggedin_user


@app.route("/maintain/<collection_name>", methods=['GET','POST'])
def maintain(collection_name):
    # validate logged in user
    loggedin_user = get_loggedin_user()
    if not loggedin_user:
        return redirect(url_for("login"))
    # is collection maintanable by admin only and user is not logged in as admin?
    if get_db_is_admin_maintainable(collection_name) and not get_db_user_is_admin():
        return redirect(url_for("index"))

    # create an empty record
    record = {}
    if request.method == 'POST':
        record = save_record_to_db(request, collection_name, {})
        if not record:
            return redirect(url_for('maintain', collection_name=collection_name))

    records = get_db_all_records(collection_name)
    if not records:
        flash("There are no records. Create one below!", 'info')
    return render_template("maintain.html",
        collection_name=collection_name,
        records=records, 
        last_record=record)
    

def save_record_to_db(request, collection_name, record_old):
    coll_fieldcatalog = get_db_fieldcatalog(collection_name)

    fields = [field['name'] for field in coll_fieldcatalog['fields']]
    record_new = {f:request.form.get(f) for f in fields if request.form.get(f,None) is not None and request.form.get(f) != record_old.get(f,None)}
    if not record_new:
        flash(f"Did not {'update' if record_old else 'add'} record", "info")
        return {}
    
    images_old = []
    for field in coll_fieldcatalog['fields']:
        field_name = field['name']
        field_input_type = field.get('input_type', False)
        if not field_input_type:
            continue
        field_value = record_new.get(field_name, None)
        # store logged in user as last updater
        if field_input_type=='changedby':
            record_new[field_name] = ObjectId(session['user_id'])
        # convert date value to datetime object
        elif field_input_type=='date':
            date_value = request.form.get(field_name,None)
            if date_value == '':
                del record_new[field_name]
            elif date_value is not None:
                record_new[field_name] = datetime.fromisoformat(date_value)
        # store foreign key from select-option
        elif field_input_type=='select':
            # get foreign key of selected value
            record_id = field_value
            if record_id:
                # insert foreing key as object into field
                record_new[field_name] = ObjectId(record_id)
        # store foreign key from lookup
        elif field_input_type=='lookup':
            # get foreign key of text value
            translate_db_value_to_id(field_name, field['values'], record_new)
        # store check box as boolean
        elif field_input_type=='checkbox':
            record_new[field_name] = True if field_value=='on' else False
        # store password
        elif field_input_type=='password':
            if field_value and len(field_value)>0:
                translate_db_password_to_hash(field_name, record_new)
            else:
                record_new.pop(field_name)
        # store timestamp
        elif field_input_type=='timestamp_update' and record_old:
            record_new[field_name] = get_utc_timestamp()
        elif field_input_type=='timestamp_insert' and not record_old:
            record_new[field_name] = get_utc_timestamp()
        # store image
        elif field_input_type=='imageid':
            # following instructions from https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
            image = request.files[field_name]
            if image:
                filename_source = secure_filename(image.filename)
                extension = filename_source.rsplit('.', 1)[1] if '.' in filename_source else ''
                if extension in app.config["UPLOAD_EXTENSIONS"]:
                    # store image
                    image_new = {'source': filename_source, 'image': Binary(image.read())}
                    coll_images = get_db_collection(app.config["MONGO_IMAGES"])
                    record_new[field_name] = coll_images.insert_one(image_new).inserted_id
                    if record_old.get(field_name, False):
                        images_old.append(record_old[field_name])

    if record_old:
        try:
            update_db_record(collection_name, record_old, record_new)
            flash(f"Successfully updated one {get_db_entity_name(collection_name)} record", "success")
        except:
            flash(f"Error in update operation!", "danger")        
        # delete old images if new got uploaded
        coll_images = get_db_collection(app.config["MONGO_IMAGES"])
        for image_old in images_old:
            coll_images.delete_one({"_id":image_old})
    else:
        try:
            record_new = insert_db_record(collection_name, record_new)
            # create empty record - this clears the input fields, because the update was OK
            record_new = {}
            flash(f"Successfully added one {get_db_entity_name(collection_name)} record", "success")
        except:
            flash(f"Error in insert operation!", "danger")
    return record_new


@app.route("/update/<collection_name>/<record_id>", methods=['GET','POST'])
def update_record(collection_name, record_id):
    # validate logged in user
    loggedin_user = get_loggedin_user()
    if not loggedin_user:
        return redirect(url_for("login"))
    # is collection maintanable by admin only and user is not logged in as admin?
    if get_db_is_admin_maintainable(collection_name) and not get_db_user_is_admin():
        return redirect(url_for("index"))
    
    record = get_db_record_by_id(collection_name, record_id)
    if not record:
        flash(f"{get_db_entity_name(collection_name)} {record_id} does not exist", "danger")
        return redirect(url_for('maintain', collection_name=collection_name))

    if request.method == 'POST':
        record = save_record_to_db(request, collection_name, record)
        # if record is empty, then the update was successful
        if not record:
            return redirect(url_for('maintain', collection_name=collection_name))

    return render_template("maintain.html",
        collection_name=collection_name,
        records=get_db_all_records(collection_name), 
        last_record=record)


@app.route("/delete/<collection_name>/<record_id>", methods=['POST'])
def delete_record(collection_name, record_id):
    # validate logged in user
    loggedin_user = get_loggedin_user()
    if not loggedin_user:
        return redirect(url_for("login"))
    # is collection maintanable by admin only and user is not logged in as admin?
    if get_db_is_admin_maintainable(collection_name) and not get_db_user_is_admin():
        return redirect(url_for("index"))

    if not session.get('user_is_admin', None):
        return redirect(url_for("index"))
    record = get_db_record_by_id(collection_name, record_id)
    if not record:
        flash(f"Record {record_id} does not exist", "danger")
    else:
        # delete record
        delete_db_record(collection_name, record)
        flash(f"Deleted one {get_db_entity_name(collection_name)} record", "info")
    return redirect(url_for('maintain', collection_name=collection_name))


@app.route("/search", methods=["GET", "POST"])
def search(collection_name):
    # validate logged in user
    loggedin_user = get_loggedin_user()
    if not loggedin_user:
        return redirect(url_for("login"))
     # is collection maintanable by admin only and user is not logged in as admin?
    if get_db_is_admin_maintainable(collection_name) and not get_db_user_is_admin():
        return redirect(url_for("index"))

    query = get_form_search_field_query(request)
    records = get_db_filtered_records(collection_name, query)
    if not records:
        records = get_db_all_records(collection_name)
        if records:
            flash("No results found", "warning")
        else:
            flash("There are no records.", 'info')
    return render_template("maintain.html",
        collection_name=collection_name,
        records=records, 
        last_record={})


@app.route("/serve/image/<image_id>")
def serve_image(image_id):
    # validate logged in user
    loggedin_user = get_loggedin_user()
    if not loggedin_user:
        return redirect(url_for("login"))
    image = get_db_image_by_id(image_id)
    if image:
        return send_file(BytesIO(image['image']), mimetype='application/octet-stream')


# inspired by https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
@app.template_filter('datetime_to_str')
def _jinja2_filter_datetime_to_str(dt, format):
    if dt:
        return dt.strftime(format)
    else:
        return str()

# learnt about calling functions from jinja template from here https://stackoverflow.com/a/22966127/8634389
@app.context_processor
def context_variables():
    return dict(
        fieldcatalog = get_db_fieldcatalog(),
        buffer       = {coll:get_db_records(coll) for coll in get_db_buffered_collections() }
    )

def get_db_buffered_collections():
    coll_fieldcatalogs = get_db_fieldcatalog()
    return [ coll for coll,fcat in coll_fieldcatalogs.items() if fcat.get('buffered', None)]


@app.template_filter('get_entity_select_field')
def _jinja2_filter_get_entity_select_field(entity_id, collection_name):
    fieldcatalog = get_db_fieldcatalog(collection_name)
    select_field_name = fieldcatalog['select_field']
    coll = get_db_collection(collection_name)
    try:
        entity_old = coll.find_one({'_id': entity_id}, {select_field_name: 1})
        if entity_old:
            return entity_old[select_field_name]
    except:
        pass
    return ""


@app.template_filter('unix_time_ago')
def _jinja2_filter_time_ago(unix_timestamp:int):
    translate_unix_timestamp_to_time_ago_text(unix_timestamp)


# Flask pattern from https://flask.palletsprojects.com/en/1.1.x/patterns/sqlite3/
@app.teardown_appcontext
def close_db_connection(exception):
    db = getattr(g, '_database_mongo', None)
    if db is not None:
        db.close()


# Run the App
#=================
if __name__ == "__main__":
    if app.config["MONGO_INIT"]:
        init_db_mongo(os.path.join(app.config["OS_DATA_PATH"], app.config["MONGO_BASE"]), True)
        init_db_mongo(os.path.join(app.config["OS_DATA_PATH"], app.config["MONGO_DEMO"]), False)

    app.run(
        host  = app.config["FLASK_IP"],
        port  = app.config["FLASK_PORT"],
        debug = app.config["FLASK_DEBUG"],
        use_reloader = False
    )
