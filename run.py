import os
from flask import Flask, render_template, request, redirect, flash, send_file, session, url_for
from io import BytesIO
import formdb

# envWS.py should exist only in Development
if os.path.exists("envWS.py"):
    import envWS

app = Flask(__name__)

# take app configuration from OS environment variables
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY")            # => Heroku Config Vars
app.config["FLASK_IP"] = os.environ.get("FLASK_IP",   "0.0.0.0")
# the source 'PORT' name is mandated by Heroku app deployment
app.config["FLASK_PORT"] = int(os.environ.get("PORT"))
app.config["FLASK_DEBUG"] = os.environ.get("FLASK_DEBUG", "False").lower() in {
    '1', 'true', 't', 'yes', 'y'}

# App routes
# ==============


@app.route("/")  # trigger point through webserver: "/"= root directory
def index():
    cars = None
    # is logged in user valid?
    loggedin_user = get_loggedin_user()
    if loggedin_user:
        cars = formdb.get_db_cars_for_user()
        if not cars:
            flash(f"You have no car assigned, ask the administrator for one!", 'info')
    return render_template(
        "index.html",
        collection_name=formdb.get_db_coll_name_cars(),
        records=cars
    )


@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == "GET":
        return render_template("reglog.html", register=True)

    # request.method == POST
    username_entered = formdb.get_form_reglog_field_username(request)
    # check if username already exists in db
    user_old = formdb.get_db_user_by_name(username_entered)
    if user_old:
        flash(f"Username already exists", 'danger')
        return redirect(url_for("register"))

    password_entered = formdb.get_form_reglog_field_password(request)
    user_new = formdb.insert_db_user(username_entered, password_entered)

    # put the new user_id into 'session' cookie
    formdb.login_db_user(user_new)
    flash("Registration Successful!", "success")
    return redirect(url_for("index"))


@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == "GET":
        return render_template("reglog.html", register=False)

    # request.method == POST
    username_entered = formdb.get_form_reglog_field_username(request)
    password_entered = formdb.get_form_reglog_field_password(request)
    user_old = formdb.get_db_user_by_name(username_entered)
    if user_old:
        password_stored = formdb.get_db_user_password(user_old)
    # check if username does not exist in db
    # or stored and entered passwords differ
    if not user_old or not formdb.is_password_hash_correct(password_stored, password_entered):
        flash(f"Incorrect Username and/or Password", 'danger')
        return redirect(url_for("login"))

    # put the User ID / Car IDs into session cookie
    formdb.login_db_user(user_old)
    flash(f"Welcome, {username_entered}", "success")
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    # is a user logged in?
    loggedin_user_id = formdb.get_db_user_id()
    if loggedin_user_id:
        formdb.logout_db_user()
        flash("You have been logged out", "info")
    return redirect(url_for("login"))


@app.route("/profile", methods=['GET', 'POST'])
def profile():
    loggedin_user = get_loggedin_user()
    if not loggedin_user:
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("profile.html", user=loggedin_user)

    # request.method == POST
    password_old = formdb.get_form_profile_field_password_old(request)
    password_stored = formdb.get_db_user_password(loggedin_user)
    if not formdb.is_password_hash_correct(password_stored, password_old):
        flash("Wrong old password", 'danger')
        return redirect(url_for("profile"))

    password_new = formdb.get_form_profile_field_password_new(request)
    if formdb.is_password_hash_correct(password_stored, password_new):
        flash("Old and New passwords are the same, not changed!", "warning")
        return redirect(url_for("profile"))

    # update password in DB
    is_update_ok = formdb.set_db_user_password(
        formdb.get_db_user_id(), password_new)
    if is_update_ok:
        flash("Your password has been changed", "success")
    return render_template("profile.html", user=loggedin_user)


def get_loggedin_user():
    loggedin_user = {}
    # is a user logged in?
    loggedin_user_id = formdb.get_db_user_id()
    if loggedin_user_id:
        # get user record from DB
        loggedin_user = formdb.get_db_user_by_id(loggedin_user_id)
        if not loggedin_user:
            formdb.logout_db_user()
            flash("Invalid logged in user has been logged out!", 'danger')
    return loggedin_user


@app.route("/maintain/<collection_name>", methods=['GET', 'POST'])
def maintain(collection_name):
    # validate logged in user
    loggedin_user = get_loggedin_user()
    if not loggedin_user:
        return redirect(url_for("login"))
    # is collection maintanable by admin only and user is not logged in as admin?
    if formdb.get_db_is_admin_maintainable(collection_name) and not formdb.get_db_user_is_admin():
        return redirect(url_for("index"))
    cars = formdb.get_db_cars_for_user()
    if not cars:
        return redirect(url_for("index"))

    # create an empty record
    record = {}
    if request.method == 'POST':
        result = formdb.save_record_to_db(request, collection_name, record)
        for m in result.messages:
            flash(*m)
        if not result.record:
            return redirect(url_for('maintain', collection_name=collection_name))

    records = formdb.get_db_all_records(collection_name)
    if not records:
        flash("There are no records. Create one below!", 'info')
    return render_template(
        "maintain.html",
        collection_name=collection_name,
        records=records,
        last_record=record
    )


@app.route("/update/<collection_name>/<record_id>", methods=['GET', 'POST'])
def update_record(collection_name, record_id):
    # validate logged in user
    loggedin_user = get_loggedin_user()
    if not loggedin_user:
        return redirect(url_for("login"))
    # is collection maintanable by admin only and user is not logged in as admin?
    if formdb.get_db_is_admin_maintainable(collection_name) and not formdb.get_db_user_is_admin():
        return redirect(url_for("index"))

    record = formdb.get_db_record_by_id(collection_name, record_id)
    if not record:
        entity_name = formdb.get_db_entity_name(collection_name)
        flash(f"{entity_name} {record_id} does not exist", "danger")
        return redirect(url_for('maintain', collection_name=collection_name))

    if request.method == 'POST':
        result = formdb.save_record_to_db(request, collection_name, record)
        print(*result.messages[0])
        for m in result.messages:
            flash(*m)
        # if record is empty, then the update was successful
        if not result.record:
            return redirect(url_for('maintain', collection_name=collection_name))

    return render_template(
        "maintain.html",
        collection_name=collection_name,
        records=[],
        last_record=record
    )


@app.route("/delete/<collection_name>/<record_id>", methods=['POST'])
def delete_record(collection_name, record_id):
    # validate logged in user
    loggedin_user = get_loggedin_user()
    if not loggedin_user:
        return redirect(url_for("login"))
    # is collection maintanable by admin only and user is not logged in as admin?
    if formdb.get_db_is_admin_maintainable(collection_name) and not formdb.get_db_user_is_admin():
        return redirect(url_for("index"))

    record = formdb.get_db_record_by_id(collection_name, record_id)
    if not record:
        flash(f"Record {record_id} does not exist", "danger")
    else:
        # delete record
        formdb.delete_db_record(collection_name, record)
        entity_name = formdb.get_db_entity_name(collection_name)
        flash(f"Deleted one {entity_name} record", "info")
    return redirect(url_for('maintain', collection_name=collection_name))


@app.route("/serve/image/<image_id>")
def serve_image(image_id):
    # validate logged in user
    loggedin_user = get_loggedin_user()
    if not loggedin_user:
        return redirect(url_for("login"))
    image = formdb.get_db_image_by_id(image_id)
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
        fieldcatalog=formdb.get_db_fieldcatalog(),
        buffer={coll: formdb.get_db_records(coll)
                for coll in formdb.get_db_buffered_collections()}
    )


@app.template_filter('filter_records')
def _jinja2_filter_filter_records(records: dict, field_details: dict):
    return formdb.filter_db_records(records, field_details)


@app.template_filter('create_data_attributes')
def _jinja2_filter_create_data_attributes(coll_fieldcat: dict, record: dict, filter_postfix: str):
    return formdb.create_form_data_attributes(coll_fieldcat, record, filter_postfix)


@app.template_filter('get_entity_select_field')
def _jinja2_filter_get_entity_select_field(entity_id, collection_name):
    return formdb.get_db_entity_select_field(entity_id, collection_name)


@app.template_filter('ObjectId')
def _jinja2_filter_objectid(id: str):
    field_name = "id"
    record = {field_name: id}
    formdb.translate_db_external_to_internal(
        field_name, "ObjectId", None, record)
    return record[field_name]


@app.template_filter('unix_time_ago')
def _jinja2_filter_time_ago(unix_timestamp: int):
    return formdb.translate_unix_timestamp_to_time_ago_text(unix_timestamp)


# Flask pattern from https://flask.palletsprojects.com/en/1.1.x/patterns/sqlite3/
@app.teardown_appcontext
def close_db_connection(exception):
    formdb.close_db_connection(exception)


# Run the App
# =================
if __name__ == "__main__":
    with app.app_context():
        formdb.init_db()

    app.run(
        host=app.config["FLASK_IP"],
        port=app.config["FLASK_PORT"],
        debug=app.config["FLASK_DEBUG"],
        use_reloader=False
    )
